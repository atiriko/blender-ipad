"""Run with Blender --background --factory-startup --python this_file.py."""
from pathlib import Path
import importlib.util
import json
import tempfile

import bpy

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ipad_shortcuts_test',
    ROOT / 'scripts/startup/bl_ui/space_view3d_ipad.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory() as directory:
    config = Path(directory) / 'shortcuts.json'
    module.config_path = lambda: config
    for cls in module.classes:
        bpy.utils.register_class(cls)
    try:
        module.register_props()
        settings = bpy.context.window_manager.ipad_shortcuts
        assert tuple(slot.action for slot in settings.slots) == module.DEFAULT_ACTIONS
        assert bpy.ops.wm.ipad_shortcut_edit(operation='DOWN') == {'FINISHED'}
        assert settings.slots[0].action == 'REDO' and settings.slots[1].action == 'UNDO'
        assert bpy.ops.wm.ipad_shortcut_edit(operation='ADD') == {'FINISHED'}
        assert len(settings.slots) == len(module.DEFAULT_ACTIONS) + 1
        assert settings.slots[-1].action == 'CUSTOM'
        assert bpy.ops.wm.ipad_shortcut_edit(operation='REMOVE') == {'FINISHED'}
        assert bpy.ops.wm.ipad_shortcut_edit(operation='RESET') == {'FINISHED'}
        assert tuple(slot.action for slot in settings.slots) == module.DEFAULT_ACTIONS
        icons = bpy.types.UILayout.bl_rna.functions['operator'].parameters['icon'].enum_items
        for item in module.ACTION_ITEMS:
            assert item[3] in icons, item[3]
        settings.size = 64
        settings.slots[0].action = 'FRAME'
        settings.slots[0].label = 'My focus button'
        settings.slots.move(0, 2)
        module.save_settings()
        assert json.loads(config.read_text())['slots'][2]['label'] == 'My focus button'
        module.load_settings()
        assert settings.size == 64 and settings.slots[2].action == 'FRAME'
        operator, kwargs = module.custom_operator('mesh.merge', '{"type":"CENTER"}')
        assert operator.get_rna_type().identifier == 'MESH_OT_merge'
        assert kwargs == {'type': 'CENTER'}
        for identifier, properties in [('os.system', '{}'), ('mesh.merge()', '{}'),
                                       ('mesh.merge', '[]'), ('mesh.merge', '{"x": NaN}')]:
            try:
                module.custom_operator(identifier, properties)
            except (AttributeError, ValueError, TypeError):
                pass
            else:
                raise AssertionError((identifier, properties))
        config.write_text('{broken')
        module.load_settings()
        assert tuple(slot.action for slot in settings.slots) == module.DEFAULT_ACTIONS
        config.write_text(json.dumps({'version': 1, 'slots': [{'action': 'UNDO'}] * 100}))
        module.load_settings()
        assert len(settings.slots) == module.MAX_SLOTS
        # Mode-aware menus retain the expected right-click behavior.
        assert module.action_operator('CONTEXT', type('C', (), {'mode': 'EDIT_MESH'})())[1]['name'] == 'VIEW3D_MT_edit_mesh_context_menu'
        assert module.action_operator('CONTEXT', type('C', (), {'mode': 'SCULPT'})())[0] == 'wm.call_panel'
    finally:
        module.unregister_props()
        for cls in reversed(module.classes):
            bpy.utils.unregister_class(cls)
print('Touch shortcut registration, icons, persistence, bounds, and custom operators passed.')
