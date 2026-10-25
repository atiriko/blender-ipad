"""Check production iOS default paths and post-export sharing decisions."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
appdir = (ROOT / 'source/blender/blenkernel/intern/appdir.cc').read_text()
folders = appdir[appdir.index('const char *BKE_appdir_folder_default()'):
                 appdir.index('bool BKE_appdir_folder_documents(')]
events = (ROOT / 'source/blender/windowmanager/intern/wm_event_system.cc').read_text()
start = events.index('static void wm_operator_file_share(')
share = events[start:events.index('\n#endif', start)]
prelude = r'''
#include <cassert>
#include <cstring>
#include <optional>
#include <string>
#define WITH_APPLE_CROSSPLATFORM 1
#define FILE_MAX 1024
enum { GHOST_kUserSpecialDirDocuments, OPERATOR_FINISHED = 1, OPERATOR_CANCELLED = 2,
       GHOST_kSuccess = 0, GHOST_kFailure = 1, RPT_WARNING = 1 };
static const char *home = "/sandbox/home";
static std::optional<std::string> documents = "/sandbox/Documents/long-path-for-lifetime-check";
const char *BLI_dir_home() { return home; }
bool BLI_is_dir(const char *p) { return documents && *documents == p; }
struct GHOST_ISystemPaths {
  static GHOST_ISystemPaths *get() { static GHOST_ISystemPaths paths; return &paths; }
  std::optional<std::string> getUserSpecialDir(int) { return documents; }
};
using wmOperatorStatus = int;
struct PropertyRNA { bool default_value; };
struct PointerRNA { bool has_save = true, has_path = true; PropertyRNA save{true}, path{false}; };
struct wmOperator { PointerRNA *ptr; void *reports = nullptr; };
PropertyRNA *RNA_struct_find_property(PointerRNA *p, const char *name) {
  if (std::string(name) == "check_existing") return p->has_save ? &p->save : nullptr;
  return p->has_path ? &p->path : nullptr;
}
bool RNA_property_boolean_get_default(PointerRNA *, PropertyRNA *p) { return p->default_value; }
void RNA_property_string_get(PointerRNA *, PropertyRNA *, char *p) { strcpy(p, "//export.blend"); }
const char *BKE_main_blendfile_path_from_global() { return "/sandbox/Documents/scene.blend"; }
void BLI_path_abs(char *p, const char *) { assert(std::string(p) == "//export.blend"); strcpy(p, "/sandbox/Documents/export.blend"); }
static bool file_exists = true;
bool BLI_is_file(const char *) { return file_exists; }
static int warnings = 0, shares = 0, share_result = GHOST_kSuccess;
void BKE_report(void *, int, const char *) { ++warnings; }
int GHOST_shareFileIOS(const char *p) { assert(std::string(p) == "/sandbox/Documents/export.blend"); ++shares; return share_result; }
'''
main = r'''
int main() {
  const char *path = BKE_appdir_folder_default_or_root();
  assert(std::string(path) == *documents);
  std::string heap_noise(4096, 'x');
  assert(std::string(path) == *documents);
  assert(std::string(BKE_appdir_folder_home()) == home);
  documents.reset();
  assert(std::string(BKE_appdir_folder_default_or_root()) == home);
  home = nullptr;
  assert(std::string(BKE_appdir_folder_default_or_root()) == "/");
  PointerRNA props; wmOperator op{&props};
  wm_operator_file_share(&op, OPERATOR_FINISHED); assert(shares == 1);
  wm_operator_file_share(&op, OPERATOR_CANCELLED); assert(shares == 1);
  props.save.default_value = false; // Import: never share an opened file.
  wm_operator_file_share(&op, OPERATOR_FINISHED); assert(shares == 1);
  props.save.default_value = true;
  props.has_path = false;
  wm_operator_file_share(&op, OPERATOR_FINISHED); assert(shares == 1);
  props.has_path = true; file_exists = false;
  wm_operator_file_share(&op, OPERATOR_FINISHED); assert(shares == 1);
  file_exists = true; share_result = GHOST_kFailure;
  wm_operator_file_share(&op, OPERATOR_FINISHED);
  assert(shares == 2 && warnings == 1 && file_exists);
}
'''
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source = root / 'sharing.cc'
    source.write_text(prelude + folders + share + main)
    subprocess.run(['xcrun', '--sdk', 'macosx', 'clang++', '-std=c++20',
                    '-fsanitize=address', str(source), '-o', str(root / 'sharing')], check=True)
    subprocess.run([str(root / 'sharing')], check=True)
print('Writable default paths, lifetime, export/import gating, and share failure handling passed.')
