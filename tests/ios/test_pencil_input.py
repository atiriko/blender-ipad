"""Exercise production Pencil callbacks on macOS with lightweight UIKit doubles.

The separate iOS SDK syntax check validates UIKit compatibility. These doubles
exercise event ordering/state without requiring a simulator or Blender libraries.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'intern/ghost/intern/GHOST_WindowIOS.mm').read_text()
struct = source[source.index('typedef struct UserInputEvent'):source.index('/* GHOSTUITapGesture interface')]
generate = source[source.index('- (void)generateUserInputEvents:', source.index('@implementation GHOSTUIWindow')):source.index('/* Allow simultaneous gestures')]
callbacks = source[source.index('/* Cancel pending palm/finger gestures'):source.index('- (void)handleTap:', source.index('/* Cancel pending palm/finger gestures'))]
prelude = r'''
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#include <algorithm>
#include <cmath>
#include <cassert>
#include <memory>
#include <vector>
#define GHOST_ASSERT(c, m) assert(c)
#define BLI_assert_unreachable() assert(false)
#define IOS_INPUT_LOG(...)
enum { GHOST_kTabletModeStylus=1, GHOST_kEventCursorMove=2,
       GHOST_kEventButtonDown=3, GHOST_kEventButtonUp=4,
       GHOST_kButtonMaskLeft=5, GHOST_kButtonMaskRight=6,
       GHOST_kTrackpadEventScroll=7, GHOST_kTrackpadEventMagnify=8 };
struct GHOST_TabletData { int Active; float Pressure, Xtilt, Ytilt; };
const GHOST_TabletData GHOST_TABLET_DATA_NONE = {};
struct GHOST_WindowIOS {
  id getView() { return nil; }
  CGPoint scalePointToWindow(CGPoint p) { return CGPointMake(p.x*2, p.y*2); }
};
struct RecordedEvent {
  int type, button; double x, y; GHOST_TabletData tablet;
  virtual ~RecordedEvent() = default;
};
struct GHOST_EventCursor : RecordedEvent {
  GHOST_EventCursor(unsigned long long, int t, GHOST_WindowIOS*, double a, double b, GHOST_TabletData d)
  { type=t; button=0; x=a; y=b; tablet=d; }
};
struct GHOST_EventButton : RecordedEvent {
  GHOST_EventButton(unsigned long long, int t, GHOST_WindowIOS*, int b, GHOST_TabletData d)
  { type=t; button=b; x=y=0; tablet=d; }
};
struct GHOST_EventTrackpad : RecordedEvent {
  template<class... T> GHOST_EventTrackpad(T...) { type=7; }
};
struct GHOST_SystemIOS {
  std::vector<std::unique_ptr<RecordedEvent>> events;
  unsigned long long getMilliSeconds() { return 100; }
  template<class T> void pushEvent(std::unique_ptr<T> e) { events.push_back(std::move(e)); }
};
@interface UIGestureRecognizer : NSObject
@property BOOL enabled;
@end
@implementation UIGestureRecognizer
@end

enum { UITouchTypeDirect, UITouchTypePencil };
@interface UITouch : NSObject
@property int type;
@property CGFloat force, maximumPossibleForce, altitudeAngle;
@property CGPoint point;
- (CGFloat)azimuthAngleInView:(id)view;
- (CGPoint)preciseLocationInView:(id)view;
@end
@implementation UITouch
- (CGFloat)azimuthAngleInView:(id)view { return 0; }
- (CGPoint)preciseLocationInView:(id)view { return self.point; }
@end
@interface UIEvent : NSObject
@property NSArray<UITouch*> *samples;
- (NSArray<UITouch*>*)coalescedTouchesForTouch:(UITouch*)touch;
@end
@implementation UIEvent
- (NSArray<UITouch*>*)coalescedTouchesForTouch:(UITouch*)touch { return self.samples; }
@end
@interface UIWindow : NSObject
- (void)touchesBegan:(NSSet*)touches withEvent:(UIEvent*)event;
- (void)touchesMoved:(NSSet*)touches withEvent:(UIEvent*)event;
- (void)touchesEnded:(NSSet*)touches withEvent:(UIEvent*)event;
- (void)touchesCancelled:(NSSet*)touches withEvent:(UIEvent*)event;
@end
@implementation UIWindow
- (void)touchesBegan:(NSSet*)touches withEvent:(UIEvent*)event {}
- (void)touchesMoved:(NSSet*)touches withEvent:(UIEvent*)event {}
- (void)touchesEnded:(NSSet*)touches withEvent:(UIEvent*)event {}
- (void)touchesCancelled:(NSSet*)touches withEvent:(UIEvent*)event {}
@end
'''
interface = r'''
@interface GHOSTUIWindow : UIWindow {
@public
  GHOST_SystemIOS *system;
  GHOST_WindowIOS *window;
  UITouch *current_pencil_touch;
  GHOST_TabletData tablet_data;
  bool last_tap_with_pencil, finger_drag_active;
  UIGestureRecognizer *tap_gesture_recognizer, *tap2f_gesture_recognizer,
    *tap3f_gesture_recognizer, *tap4f_gesture_recognizer, *pan_gesture_recognizer,
    *pan2f_gesture_recognizer, *zoom_gesture_recognizer, *edge_swipe_left, *edge_swipe_right;
}
@end
@implementation GHOSTUIWindow
'''
main = r'''
@end
static UITouch *touch(int type, CGFloat force, CGFloat max, CGFloat x) {
  UITouch *t=[UITouch new]; t.type=type; t.force=force;
  t.maximumPossibleForce=max; t.point=CGPointMake(x, 10); t.altitudeAngle=M_PI_2;
  return t;
}
int main() { @autoreleasepool {
  GHOST_SystemIOS sys; GHOST_WindowIOS win;
  GHOSTUIWindow *ui=[GHOSTUIWindow new]; ui->system=&sys; ui->window=&win;
  ui->tap_gesture_recognizer=[UIGestureRecognizer new];
  ui->tap2f_gesture_recognizer=[UIGestureRecognizer new];
  ui->tap3f_gesture_recognizer=[UIGestureRecognizer new];
  ui->tap4f_gesture_recognizer=[UIGestureRecognizer new];
  ui->pan_gesture_recognizer=[UIGestureRecognizer new];
  ui->pan2f_gesture_recognizer=[UIGestureRecognizer new];
  ui->zoom_gesture_recognizer=[UIGestureRecognizer new];
  ui->edge_swipe_left=[UIGestureRecognizer new];
  ui->edge_swipe_right=[UIGestureRecognizer new];
  [ui setFingerGesturesEnabled:YES];
  UITouch *pen=touch(UITouchTypePencil,2,4,10);
  UITouch *finger=touch(UITouchTypeDirect,0,0,20);
  [ui touchesBegan:[NSSet setWithObject:pen] withEvent:nil];
  assert(!ui->tap_gesture_recognizer.enabled && !ui->pan_gesture_recognizer.enabled);
  assert(sys.events.size()==2 && sys.events[0]->type==GHOST_kEventCursorMove);
  assert(sys.events[0]->x==20 && sys.events[1]->tablet.Pressure==0.5f);
  assert(sys.events[1]->type==GHOST_kEventButtonDown);
  [ui touchesEnded:[NSSet setWithObject:finger] withEvent:nil];
  assert(ui->current_pencil_touch==pen && sys.events.size()==2);
  [ui touchesCancelled:[NSSet setWithObject:finger] withEvent:nil];
  assert(ui->current_pencil_touch==pen && sys.events.size()==2);
  UserInputEvent navigation(nullptr,nullptr,nullptr,false);
  navigation.add_event(UserInputEvent::CURSOR_MOVE);
  [ui generateUserInputEvents:navigation]; assert(sys.events.size()==2);
  UIEvent *event=[UIEvent new];
  event.samples=@[touch(UITouchTypePencil,1,4,11),touch(UITouchTypePencil,3,4,12)];
  [ui touchesMoved:[NSSet setWithObject:pen] withEvent:event];
  assert(sys.events.size()==4 && sys.events[2]->x==22 && sys.events[3]->x==24);
  assert(sys.events[2]->tablet.Pressure==0.25f && sys.events[3]->tablet.Pressure==0.75f);
  [ui touchesEnded:[NSSet setWithObject:pen] withEvent:nil];
  assert(sys.events.back()->type==GHOST_kEventButtonUp && !ui->current_pencil_touch);
  assert(ui->tap_gesture_recognizer.enabled && ui->pan_gesture_recognizer.enabled);
  auto count=sys.events.size();
  [ui touchesCancelled:[NSSet setWithObject:pen] withEvent:nil];
  assert(sys.events.size()==count);
  pen.force=99; pen.maximumPossibleForce=0;
  [ui touchesBegan:[NSSet setWithObject:pen] withEvent:nil];
  assert(sys.events.back()->tablet.Pressure==0);
  [ui cancelActiveInput]; assert(!ui->current_pencil_touch);
  assert(sys.events.back()->type==GHOST_kEventButtonUp);
  pen.maximumPossibleForce=4;
  [ui touchesBegan:[NSSet setWithObject:pen] withEvent:nil];
  assert(sys.events.back()->tablet.Pressure==1);
  [ui touchesCancelled:[NSSet setWithObject:pen] withEvent:nil];
  assert(!ui->current_pencil_touch && sys.events.back()->type==GHOST_kEventButtonUp);
  UserInputEvent tap(nullptr,nullptr,nullptr,true); tap.add_event(UserInputEvent::PENCIL_TAP);
  count=sys.events.size(); [ui generateUserInputEvents:tap];
  assert(sys.events.size()==count+2 && sys.events[count]->button==GHOST_kButtonMaskRight);
  assert(sys.events[count]->type==GHOST_kEventButtonDown);
  assert(sys.events[count+1]->type==GHOST_kEventButtonUp);
  ui->finger_drag_active=true; count=sys.events.size();
  [ui touchesBegan:[NSSet setWithObject:pen] withEvent:nil];
  assert(sys.events.size()==count+3 && sys.events[count]->type==GHOST_kEventButtonUp);
  assert(!ui->finger_drag_active);
  [ui cancelActiveInput];
  puts("Pencil contact, samples, finger isolation, pressure, cancellation, interruption, and double-tap passed.");
} }
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / 'test.mm').write_text(prelude + struct + interface + generate + callbacks + main)
    subprocess.run(['xcrun', '--sdk', 'macosx', 'clang++', '-std=c++20', '-fobjc-arc',
                    '-framework', 'Foundation', '-framework', 'CoreGraphics',
                    str(path / 'test.mm'), '-o', str(path / 'test')], check=True)
    subprocess.run([str(path / 'test')], check=True)
