"""Exercise production iOS navigation gates without a simulator."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
functions = []
for name in ('rotate', 'move'):
    source = (ROOT / f'source/blender/editors/space_view3d/view3d_navigate_view_{name}.cc').read_text()
    start = source.index(f'static wmOperatorStatus view{name}_invoke(bContext')
    end = source.index(f'\nvoid VIEW3D_OT_{name}', start)
    functions.append(source[start:end])

prelude = r'''
#include <cassert>
#define WITH_APPLE_CROSSPLATFORM
#define ELEM(value, a, b) ((value) == (a) || (value) == (b))
enum { LEFTMOUSE, MOUSEPAN, MOUSEROTATE, WM_EVENT_MULTITOUCH_TWO_FINGERS = 8 };
enum wmOperatorStatus { OPERATOR_FINISHED, OPERATOR_RUNNING_MODAL };
struct bContext {};
struct wmOperator {};
struct wmEvent { int type, flag; };
const int ViewOpsType_rotate = 0, ViewOpsType_move = 1;
static int invoked = 0;
static wmOperatorStatus view3d_navigate_invoke_impl(
    bContext *, wmOperator *, const wmEvent *, const int *)
{
  ++invoked;
  return OPERATOR_RUNNING_MODAL;
}
'''
main = r'''
int main()
{
  for (auto invoke : {viewrotate_invoke, viewmove_invoke}) {
    wmEvent pencil_or_mouse_drag{LEFTMOUSE, 0};
    assert(invoke(nullptr, nullptr, &pencil_or_mouse_drag) == OPERATOR_RUNNING_MODAL);
    wmEvent single_finger_scroll{MOUSEPAN, 0};
    int before = invoked;
    assert(invoke(nullptr, nullptr, &single_finger_scroll) == OPERATOR_FINISHED);
    assert(invoked == before);
    wmEvent two_finger_scroll{MOUSEPAN, WM_EVENT_MULTITOUCH_TWO_FINGERS};
    assert(invoke(nullptr, nullptr, &two_finger_scroll) == OPERATOR_RUNNING_MODAL);
  }
  wmEvent single_rotate{MOUSEROTATE, 0};
  assert(viewrotate_invoke(nullptr, nullptr, &single_rotate) == OPERATOR_FINISHED);
  wmEvent two_finger_rotate{MOUSEROTATE, WM_EVENT_MULTITOUCH_TWO_FINGERS};
  assert(viewrotate_invoke(nullptr, nullptr, &two_finger_rotate) == OPERATOR_RUNNING_MODAL);
}
'''
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source = root / 'navigation.cc'
    source.write_text('#include <initializer_list>\n' + prelude + '\n'.join(functions) + main)
    subprocess.run(['xcrun', '--sdk', 'macosx', 'clang++', '-std=c++20',
                    str(source), '-o', str(root / 'navigation')], check=True)
    subprocess.run([str(root / 'navigation')], check=True)
print('Direct navigation drags and two-finger gesture restrictions passed.')
