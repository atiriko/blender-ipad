"""Optional on-device input probe; run through Blender's --python argument.

Records up to 1500 input events to Documents/pencil-events.jsonl and passes
every event through to Blender. No simulator or input injection is involved.
"""
import json
import os
from pathlib import Path
import time

import bpy


class WM_OT_ios_input_probe(bpy.types.Operator):
    bl_idname = 'wm.ios_input_probe'
    bl_label = 'Record iOS Pencil Input'

    def invoke(self, context, event):
        self._count = 0
        self._path = Path(os.environ['HOME']) / 'Documents' / 'pencil-events.jsonl'
        self._path.write_text('')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'LEFTMOUSE', 'RIGHTMOUSE'}:
            with self._path.open('a') as log:
                log.write(json.dumps({
                    'time': time.monotonic(),
                    'type': event.type,
                    'value': event.value,
                    'tablet': event.is_tablet,
                    'pressure': event.pressure,
                    'tilt': list(event.tilt),
                    'x': event.mouse_x,
                    'y': event.mouse_y,
                }) + '\n')
            self._count += 1
            if self._count >= 1500:
                return {'FINISHED', 'PASS_THROUGH'}
        return {'PASS_THROUGH'}


def start():
    window = next(iter(bpy.context.window_manager.windows), None)
    if window is None:
        return 0.5
    with bpy.context.temp_override(window=window):
        bpy.ops.wm.ios_input_probe('INVOKE_DEFAULT')
    return None


bpy.utils.register_class(WM_OT_ios_input_probe)
bpy.app.timers.register(start, first_interval=1.0)
