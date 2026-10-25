# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Editable touch shortcuts, backed by ordinary Blender operators."""

import json
import math
import os
from pathlib import Path
import re

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import GizmoGroup, Operator, Panel, PropertyGroup, UIList


ACTION_ITEMS = (
    ('UNDO', "Undo", "Undo the last action", 'LOOP_BACK', 0),
    ('REDO', "Redo", "Redo the last action", 'LOOP_FORWARDS', 1),
    ('MOVE', "Move Tool", "Show move handles", 'EMPTY_ARROWS', 2),
    ('ROTATE', "Rotate Tool", "Show rotation handles", 'ORIENTATION_GIMBAL', 3),
    ('SCALE', "Scale Tool", "Show scale handles", 'FULLSCREEN_ENTER', 4),
    ('FRAME', "Frame Selected", "Center the view on the selection", 'ZOOM_SELECTED', 5),
    ('MODE', "Toggle Edit Mode", "Switch between Object and Edit Mode", 'EDITMODE_HLT', 6),
    ('CONTEXT', "Context Menu", "Open the current mode's context menu", 'MENU_PANEL', 7),
    ('SAVE', "Save", "Save the current scene", 'FILE_TICK', 8),
    ('SELECT_ALL', "Select All", "Select all in the current mode", 'SELECT_SET', 9),
    ('DESELECT', "Deselect All", "Clear the current selection", 'SELECT_SUBTRACT', 10),
    ('DELETE', "Delete Menu", "Choose what to delete", 'TRASH', 11),
    ('DUPLICATE', "Duplicate", "Duplicate the selection", 'DUPLICATE', 12),
    ('EXTRUDE', "Extrude Tool", "Show mesh extrusion handles", 'FACESEL', 13),
    ('INSET', "Inset Tool", "Show mesh inset handles", 'MOD_SOLIDIFY', 14),
    ('ZOOM_IN', "Zoom In", "Zoom the viewport in", 'ZOOM_IN', 15),
    ('ZOOM_OUT', "Zoom Out", "Zoom the viewport out", 'ZOOM_OUT', 16),
    ('CUSTOM', "Custom Operator", "Run a Blender operator with optional JSON properties", 'CONSOLE', 17),
)
ACTION_INFO = {item[0]: item for item in ACTION_ITEMS}
DEFAULT_ACTIONS = ('UNDO', 'REDO', 'MOVE', 'ROTATE', 'SCALE', 'FRAME', 'MODE', 'CONTEXT', 'SAVE')
MAX_SLOTS = 12
_loading = False


def config_path():
    directory = bpy.utils.user_resource('CONFIG', create=True)
    if not directory:
        raise OSError("No writable Blender configuration folder")
    return Path(directory) / 'ipad_shortcuts.json'


def redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def save_settings(_self=None, context=None):
    if _loading:
        return
    context = context or bpy.context
    settings = getattr(context.window_manager, 'ipad_shortcuts', None)
    if settings is None:
        return
    payload = {
        'version': 1,
        'enabled': settings.enabled,
        'position': settings.position,
        'size': settings.size,
        'slots': [{key: getattr(slot, key) for key in ('action', 'label', 'operator', 'properties')}
                  for slot in settings.slots],
    }
    try:
        path = config_path()
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    except OSError as error:
        print("Could not save iPad shortcuts:", error)
    redraw()


def load_settings():
    global _loading
    settings = bpy.context.window_manager.ipad_shortcuts
    try:
        path = config_path()
        if path.exists() and path.stat().st_size <= 65536:
            payload = json.loads(path.read_text(encoding='utf-8'))
        else:
            payload = {}
        if not isinstance(payload, dict) or payload.get('version', 1) != 1:
            payload = {}
    except (OSError, ValueError):
        payload = {}
    _loading = True
    try:
        settings.enabled = bool(payload.get('enabled', True))
        position = payload.get('position', 'BOTTOM')
        settings.position = position if position in {'TOP', 'BOTTOM'} else 'BOTTOM'
        size = payload.get('size', 48)
        settings.size = max(36, min(84, size)) if type(size) is int else 48
        settings.slots.clear()
        slots = payload.get('slots')
        if not isinstance(slots, list) or not slots:
            slots = [{'action': action} for action in DEFAULT_ACTIONS]
        for values in slots[:MAX_SLOTS]:
            if not isinstance(values, dict) or values.get('action') not in ACTION_INFO:
                continue
            slot = settings.slots.add()
            slot.action = values['action']
            for key in ('label', 'operator', 'properties'):
                value = values.get(key, '')
                setattr(slot, key, value[:4096] if isinstance(value, str) else '')
        if not settings.slots:
            for action in DEFAULT_ACTIONS:
                settings.slots.add().action = action
        settings.active_index = 0
    finally:
        _loading = False
    redraw()


class IPAD_PG_shortcut(PropertyGroup):
    action: EnumProperty(name="Action", items=ACTION_ITEMS, default='UNDO', update=save_settings)
    label: StringProperty(name="Label", description="Optional tooltip label", maxlen=80, update=save_settings)
    operator: StringProperty(name="Operator", description="For example: mesh.merge", maxlen=128, update=save_settings)
    properties: StringProperty(name="Properties", description='JSON object, for example: {"type": "CENTER"}',
                               maxlen=4096, default='{}', update=save_settings)


class IPAD_PG_shortcuts(PropertyGroup):
    enabled: BoolProperty(name="Show Shortcut Strip", default=True, update=save_settings)
    position: EnumProperty(name="Position", items=(('BOTTOM', "Bottom", ""), ('TOP', "Top", "")),
                           default='BOTTOM', update=save_settings)
    size: IntProperty(name="Button Size", default=48, min=36, max=84, update=save_settings)
    slots: CollectionProperty(type=IPAD_PG_shortcut)
    active_index: IntProperty(default=0, min=0)


def reject_constant(value):
    raise ValueError("Invalid JSON constant: " + value)


def custom_operator(identifier, properties):
    if not re.fullmatch(r'[a-z_][a-z_0-9]*\.[a-z_][a-z_0-9]*', identifier):
        raise ValueError("Use an operator ID such as mesh.merge")
    kwargs = json.loads(properties or '{}', parse_constant=reject_constant)
    if not isinstance(kwargs, dict):
        raise ValueError("Operator properties must be a JSON object")
    module, name = identifier.split('.')
    operator = getattr(getattr(bpy.ops, module), name)
    try:
        operator.get_rna_type()  # Validate existence without executing it.
    except (AttributeError, KeyError) as error:
        raise ValueError("Unknown Blender operator: " + identifier) from error
    return operator, kwargs


def action_operator(action, context):
    fixed = {
        'UNDO': ('ed.undo', {}), 'REDO': ('ed.redo', {}),
        'MOVE': ('wm.tool_set_by_id', {'name': 'builtin.move'}),
        'ROTATE': ('wm.tool_set_by_id', {'name': 'builtin.rotate'}),
        'SCALE': ('wm.tool_set_by_id', {'name': 'builtin.scale'}),
        'FRAME': ('view3d.view_selected', {}),
        'MODE': ('object.editmode_toggle', {}),
        'SAVE': ('wm.save_mainfile', {}),
        'ZOOM_IN': ('view3d.zoom', {'delta': 1}),
        'ZOOM_OUT': ('view3d.zoom', {'delta': -1}),
        'EXTRUDE': ('wm.tool_set_by_id', {'name': 'builtin.extrude_region'}),
        'INSET': ('wm.tool_set_by_id', {'name': 'builtin.inset'}),
    }
    if action in fixed:
        return fixed[action]
    if action == 'CONTEXT':
        menus = {
            'OBJECT': 'VIEW3D_MT_object_context_menu', 'EDIT_MESH': 'VIEW3D_MT_edit_mesh_context_menu',
            'POSE': 'VIEW3D_MT_pose_context_menu', 'EDIT_CURVE': 'VIEW3D_MT_edit_curve_context_menu',
            'EDIT_ARMATURE': 'VIEW3D_MT_armature_context_menu',
        }
        panels = {
            'SCULPT': 'VIEW3D_PT_sculpt_context_menu',
            'PAINT_TEXTURE': 'VIEW3D_PT_paint_texture_context_menu',
            'PAINT_VERTEX': 'VIEW3D_PT_paint_vertex_context_menu',
            'PAINT_WEIGHT': 'VIEW3D_PT_paint_weight_context_menu',
        }
        if context.mode in panels:
            return 'wm.call_panel', {'name': panels[context.mode]}
        return 'wm.call_menu', {'name': menus.get(context.mode, 'VIEW3D_MT_object_context_menu')}
    namespace = 'mesh' if context.mode == 'EDIT_MESH' else 'object'
    if action in {'SELECT_ALL', 'DESELECT'}:
        return namespace + '.select_all', {'action': 'SELECT' if action == 'SELECT_ALL' else 'DESELECT'}
    if action == 'DELETE':
        if context.mode == 'EDIT_MESH':
            return 'wm.call_menu', {'name': 'VIEW3D_MT_edit_mesh_delete'}
        return 'object.delete', {}
    if action == 'DUPLICATE':
        return namespace + '.duplicate_move', {}
    raise ValueError("Unknown shortcut action")


class WM_OT_ipad_shortcut(Operator):
    bl_idname = 'wm.ipad_shortcut'
    bl_label = "iPad Shortcut"
    index: IntProperty(options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        settings = context.window_manager.ipad_shortcuts
        if 0 <= properties.index < len(settings.slots):
            slot = settings.slots[properties.index]
            return slot.label or ACTION_INFO[slot.action][1]
        return "iPad Shortcut"

    def execute(self, context):
        settings = context.window_manager.ipad_shortcuts
        if not 0 <= self.index < len(settings.slots):
            return {'CANCELLED'}
        slot = settings.slots[self.index]
        try:
            if slot.action == 'CUSTOM':
                operator, kwargs = custom_operator(slot.operator, slot.properties)
            else:
                identifier, kwargs = action_operator(slot.action, context)
                operator, _ = custom_operator(identifier, '{}')
            if not operator.poll():
                self.report({'INFO'}, "This shortcut is unavailable in the current mode")
                return {'CANCELLED'}
            operator('INVOKE_DEFAULT', **kwargs)
        except (AttributeError, RuntimeError, ValueError, TypeError) as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class WM_OT_ipad_shortcut_edit(Operator):
    bl_idname = 'wm.ipad_shortcut_edit'
    bl_label = "Edit Touch Shortcuts"
    operation: EnumProperty(items=(('ADD', "Add", ""), ('REMOVE', "Remove", ""),
                                   ('UP', "Move Up", ""), ('DOWN', "Move Down", ""),
                                   ('RESET', "Reset", "")))

    def execute(self, context):
        settings = context.window_manager.ipad_shortcuts
        index = min(settings.active_index, len(settings.slots) - 1)
        if self.operation == 'ADD' and len(settings.slots) < MAX_SLOTS:
            settings.slots.add().action = 'CUSTOM'
            settings.active_index = len(settings.slots) - 1
        elif self.operation == 'REMOVE' and len(settings.slots) > 1:
            settings.slots.remove(index)
            settings.active_index = max(0, index - 1)
        elif self.operation in {'UP', 'DOWN'}:
            destination = index + (-1 if self.operation == 'UP' else 1)
            if 0 <= destination < len(settings.slots):
                settings.slots.move(index, destination)
                settings.active_index = destination
        elif self.operation == 'RESET':
            global _loading
            _loading = True
            try:
                settings.slots.clear()
                for action in DEFAULT_ACTIONS:
                    settings.slots.add().action = action
                settings.active_index = 0
            finally:
                _loading = False
        save_settings(context=context)
        return {'FINISHED'}


class IPAD_UL_shortcuts(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        info = ACTION_INFO[item.action]
        layout.label(text=item.label or info[1], icon=info[3])


def draw_settings(layout, settings):
    layout.prop(settings, 'enabled')
    row = layout.row(align=True)
    row.prop(settings, 'position', text="")
    row.prop(settings, 'size')
    row = layout.row()
    row.template_list('IPAD_UL_shortcuts', '', settings, 'slots', settings, 'active_index', rows=5)
    column = row.column(align=True)
    for operation, icon in (('ADD', 'ADD'), ('REMOVE', 'REMOVE'), ('UP', 'TRIA_UP'), ('DOWN', 'TRIA_DOWN')):
        column.operator('wm.ipad_shortcut_edit', text="", icon=icon).operation = operation
    if settings.slots:
        slot = settings.slots[min(settings.active_index, len(settings.slots) - 1)]
        layout.prop(slot, 'action')
        layout.prop(slot, 'label')
        if slot.action == 'CUSTOM':
            layout.prop(slot, 'operator')
            layout.prop(slot, 'properties')
    layout.operator('wm.ipad_shortcut_edit', text="Restore Default Buttons", icon='LOOP_BACK').operation = 'RESET'


class WM_OT_ipad_shortcut_settings(Operator):
    bl_idname = 'wm.ipad_shortcut_settings'
    bl_label = "Touch Shortcuts"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=380)

    def draw(self, context):
        draw_settings(self.layout, context.window_manager.ipad_shortcuts)

    def execute(self, context):
        return {'FINISHED'}


class VIEW3D_PT_ipad_shortcuts(Panel):
    bl_label = "Touch Shortcuts"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Touch"

    def draw(self, context):
        draw_settings(self.layout, context.window_manager.ipad_shortcuts)


class VIEW3D_GGT_ipad_shortcuts(GizmoGroup):
    bl_idname = 'VIEW3D_GGT_ipad_shortcuts'
    bl_label = "Touch Shortcuts"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.window_manager, 'ipad_shortcuts', None)
        return bool(settings and settings.enabled and settings.slots)

    def setup(self, context):
        self.buttons = []
        for index in range(MAX_SLOTS + 1):
            button = self.gizmos.new('GIZMO_GT_button_2d')
            button.draw_options = {'BACKDROP', 'OUTLINE'}
            button.show_drag = False
            button.use_tooltip = True
            button.color = (0.12, 0.15, 0.20)
            button.alpha = 0.85
            button.color_highlight = (0.35, 0.65, 1.0)
            button.alpha_highlight = 1.0
            if index == MAX_SLOTS:
                button.icon = 'PREFERENCES'
                button.target_set_operator('wm.ipad_shortcut_settings')
            else:
                button.target_set_operator('wm.ipad_shortcut').index = index
            self.buttons.append(button)

    def draw_prepare(self, context):
        settings = context.window_manager.ipad_shortcuts
        scale = context.preferences.system.ui_scale
        spacing = settings.size * scale
        left = right = 8 * scale
        for region in context.area.regions:
            if region.type == 'TOOLS' and region.width > 1:
                left += region.width
            elif region.type == 'UI' and region.width > 1:
                right += region.width
        available = max(spacing, context.region.width - left - right)
        count = len(settings.slots) + 1
        columns = max(1, min(count, int(available // spacing)))
        rows = math.ceil(count / columns)
        x_start = left + (available - columns * spacing) / 2 + spacing / 2
        for index, button in enumerate(self.buttons):
            is_settings = index == MAX_SLOTS
            button.hide = not is_settings and index >= len(settings.slots)
            if button.hide:
                continue
            position = len(settings.slots) if is_settings else index
            if not is_settings:
                button.icon = ACTION_INFO[settings.slots[index].action][3]
            button.scale_basis = settings.size * 0.46
            button.matrix_basis[0][3] = x_start + (position % columns) * spacing
            row = position // columns
            button.matrix_basis[1][3] = (spacing * (rows - row - 0.5) + 12 * scale
                                        if settings.position == 'BOTTOM'
                                        else context.region.height - spacing * (row + 0.5) - 12 * scale)


classes = (
    IPAD_PG_shortcut, IPAD_PG_shortcuts, WM_OT_ipad_shortcut, WM_OT_ipad_shortcut_edit,
    IPAD_UL_shortcuts, WM_OT_ipad_shortcut_settings, VIEW3D_PT_ipad_shortcuts, VIEW3D_GGT_ipad_shortcuts,
)


@bpy.app.handlers.persistent
def reload_settings(_unused):
    if hasattr(bpy.types.WindowManager, 'ipad_shortcuts'):
        load_settings()


def register_props():
    bpy.types.WindowManager.ipad_shortcuts = PointerProperty(type=IPAD_PG_shortcuts)
    load_settings()
    if reload_settings not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(reload_settings)


def unregister_props():
    if reload_settings in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(reload_settings)
    if hasattr(bpy.types.WindowManager, 'ipad_shortcuts'):
        del bpy.types.WindowManager.ipad_shortcuts
