"""
Morzio Hair Factory
Copyright (C) 2025 Demingo Hill (Noizirom)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import bpy
from bpy.ops import object as object_, hair_factory
from bpy.types import Operator, Panel, UIList, Object, Scene, Modifier, UI_UL_list, Material
from bpy.props import StringProperty, EnumProperty, BoolProperty, IntProperty, PointerProperty
from bpy.utils import register_class, unregister_class
from numpy import array, ndarray, char, where



def set_hair_pts(hair_curve, co):
    if not isinstance(co, ndarray):
        co = array(co)
    hair_curve.data.points.foreach_set('position', co.ravel())


def create_hair_curve(name, ob, points=None, sizes=None):
    with bpy.context.temp_override(active_object=ob):
        object_.curves_empty_hair_add()
        hair_curve = bpy.context.object
        hair_curve.name = name
        hair_curve.data.name = name
        n = bpy.context.object.name
    hair_curve = bpy.data.objects[n]
    if sizes:
        if isinstance(sizes, ndarray):
            sizes = sizes.tolist()
        hair_curve.data.add_curves(sizes)
    if points:
        set_hair_pts(hair_curve, points)
    return hair_curve


# IO Panel
def main_io_panel(context, layout_dock):
    scene = context.scene
    header, panel = layout_dock.box().panel("HAIR_IO", default_closed=True)
    header.label(text=f"Hair   Save | Load")
    if panel:
        io_box = panel.box()
        col = io_box.column()
        col.separator()
        rcol = col.row()
        rcol.prop(scene, 'hf_hair_preset_name', text="Preset Name")
        rcol.operator("hair_factory.save_hair", text='', icon='FILE_TICK')
        col.separator()
        col.separator()
        rcol2 = col.row()
        rcol2s = rcol2.split(factor=.23)
        rcol2s.prop(scene, 'hf_rename_hair_curve', text="Rename Hair")
        rcol2s.prop(scene, 'hf_hair_presets', text="")
        rcol2.operator("hair_factory.load_hair", text='', icon='FILE_FOLDER')
        sheader, spanel = io_box.panel("EO_HAIR", default_closed=True)
        sheader.label(text=f"Extra Options")
        if spanel:
            srow = spanel.row()
            srow.prop(scene, 'hf_hair_preset_search')
            srow.separator()
            srow.separator()
            spanel.separator()
            srow = spanel.row()
            srow.prop(scene, 'hf_hair_preset_rename', text="Rename Hair | Preset")
            srow.operator("hair_factory.rename_hair_preset", text='', icon='TEXT')
            spanel.separator()
            srow = spanel.row()
            srow.prop(scene, 'hf_hair_export_path', text="Export Path")
            srow.operator("hair_factory.export_hair_preset", text='', icon='DOCUMENTS')



### BAKE FUNCS ###

# Get active modifier if node group
def get_modifier_geonode(ob):
    modifiers = getattr(ob, "modifiers", None)
    if (not modifiers):
        return None
    modifier = modifiers.active
    if modifier.type != "NODES":
        return None
    return modifier


# Get active modifier bakes if node group and has bakes
def get_bakes(ob):
    modifier = get_modifier_geonode(ob)
    if not modifier:
        return None
    bake_count = len(modifier.bakes)
    if bake_count == 0:
        return None
    return modifier.bakes


# Get the execution time for a modifier if available
def get_execution_time(ob, modifier=None, decimals=3):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obe = ob.evaluated_get(depsgraph)
    if not modifier:
        modifier = obe.modifiers.active
    execution_time = modifier.execution_time
    if decimals > 0:
        execution_time = round(execution_time, decimals)
    return execution_time


# Returns a list of all bake nodes for the active modifier for EnumProperty
def _available_bake_nodes(self, context):
    available_bakes = [("None", "None", "")]
    ob = bpy.context.object
    if not ob:
        return available_bakes
    modifiers = ob.modifiers
    if len(modifiers) == 0:
        return available_bakes
    modifier = modifiers.active
    bake_count = len(modifier.bakes)
    if bake_count == 0:
        return available_bakes
    try:
        for bake in modifier.bakes:
            if getattr(bake, "node"):
                available_bakes.append((str(bake.bake_id), f"{bake.node.active_item.id_data.name} | {bake.node.name}", f"Bake node {bake.node.name} located in {bake.node.active_item.id_data.name} node group."))
        return available_bakes
    except AttributeError as ae:
        print(ae)
    finally:
        return available_bakes


# Returns the selected bake node from the EnumProperty
def get_selected_bake(modifier, bake_id):
    bakes = array([bake.bake_id for bake in modifier.bakes])
    idx = where(bakes == int(bake_id))[0][0]
    return modifier.bakes[idx]


# Update the selected bake node's mode
def update_active_bake_node_mode(self, context):
    ob = context.object
    if not ob:
        return
    if not get_bakes(ob) or (ob.available_bake_nodes == 'None'):
        return
    modifier = ob.modifiers.active
    bake = get_selected_bake(modifier, ob.available_bake_nodes)
    bake.bake_mode = ob.active_bake_node_mode


# Update the active modifier's bake target
def update_active_bake_modifier_target(self, context):
    ob = context.object
    if not ob:
        return
    if not get_bakes(ob) or (ob.available_bake_nodes == 'None'):
        return
    modifier = ob.modifiers.active
    modifier.bake_target = ob.active_bake_modifier_target


# Update the active modifier's bake path
def update_active_bake_node_destination(self, context):
    ob = context.object
    if not ob:
        return
    if not get_bakes(ob) or (ob.available_bake_nodes == 'None'):
        return
    modifier = ob.modifiers.active
    modifier.bake_directory = ob.active_bake_node_destination


### GUI FUNCS ###


def get_nodegroup_groups(node_tree):
    if node_tree:
        for node in node_tree.nodes:
            if node.type == 'GROUP':
                yield node.node_tree
                yield from get_nodegroup_groups(node.node_tree)


def delete_full_node_tree(node_tree):
    for node_group in reversed(list(get_nodegroup_groups(node_tree))):
        try:
            bpy.data.node_groups.remove(node_group)
        except:
            continue
    try:
        bpy.data.node_groups.remove(node_tree)
    except:
        pass


def delete_geo_node_modifier(ob, modifier):
    if getattr(modifier, 'node_group', None):
        delete_full_node_tree(modifier.node_group)
    ob.modifiers.remove(modifier)


def get_modifier_stack_geo_nodes(ob):
    for modifier in ob.modifiers:
        if modifier.type == 'NODES':
            yield modifier.node_group


def update_mod_idx(self, context):
    ob = context.object
    modifiers = ob.modifiers
    if len(modifiers) > 0:
        modifiers.active = modifiers[ob.active_modifier_idx]


def update_obj_idx(self, context):
    try:
        ob = context.object
        obj = bpy.data.objects
        if ob.mode == 'OBJECT':
            idx = self.active_object_idx
            context.view_layer.objects.active = obj[idx]
            object_.select_all(action='DESELECT')
            obj[idx].select_set(1)
        else:
            self.active_object_idx = next((i for i, o in enumerate(obj) if o == ob))
    except:
        pass


def get_socket_name(modifier, socket):
    itree = modifier.node_group.interface.items_tree
    for i in itree:
        if hasattr(i, 'identifier'):
            if i.identifier == socket:
                yield i.name


def mod_stack_gui(self, context):
    layout = self.layout
    ob = context.object
    scene = context.scene
    if ob:
        stack_box = layout.box()
        row = stack_box.row()
        row.label(text="Modifier Stack")
        row = stack_box.row()
        col = row.column(align=True)
        col.template_list('MODIFIER_UL_modifier_stack_viewer', '', ob, 'modifiers', ob, 'active_modifier_idx')
        col.separator()
        col = row.column(align=True)
        col.operator('hair_factory.launch_modifier_new', text="", icon='ADD')
        col.operator('hair_factory.modifier_delete', text="", icon='REMOVE')
        col.separator()
        col.separator()
        col.operator('hair_factory.modifier_up', text="", icon='TRIA_UP')
        col.operator('hair_factory.modifier_down', text="", icon='TRIA_DOWN')
        col.separator()
        col.operator('hair_factory.mod_apply', text="", icon='MODIFIER')
        # IO Panel
        header, panel = stack_box.panel("NSIO", default_closed=True)
        header.label(text="Modifier Stack   Save | Load")
        if panel:
            io_box = panel.box()
            col = io_box.column()
            col.separator()
            rcol = col.row()
            rcol.prop(scene, 'hf_mod_stack_preset_name', text="Preset Name")
            rcol.operator("hair_factory.save_mod_stack", text='', icon='FILE_TICK')
            col.separator()
            rcol2 = col.row()
            rcol2s = rcol2.split(factor=.23)
            rcol2s.prop(scene, 'hf_mod_stack_include', text="Include Surface Deform")
            rcol2s.prop(scene, 'hf_mod_stack_presets', text="")
            rcol2.operator("hair_factory.load_mod_stack", text='', icon='FILE_FOLDER')
            sheader, spanel = io_box.panel(f"MS_{ob.name}", default_closed=True)
            sheader.label(text=f"Extra Options")
            if spanel:
                srow = spanel.row()
                srow.prop(scene, 'hf_mod_stack_preset_search')
                srow.separator()
                srow.separator()
                spanel.separator()
                srow = spanel.row()
                srow.prop(scene, 'hf_mod_stack_preset_rename', text="Rename Preset")
                srow.operator("hair_factory.rename_mod_stack_preset", text='', icon='TEXT')
                spanel.separator()
                srow = spanel.row()
                srow.prop(scene, 'hf_mod_stack_export_path', text="Export Path")
                srow.operator("hair_factory.export_mod_stack_preset", text='', icon='DOCUMENTS')



def main_gui(self, context):
    ob = context.active_object
    layout = self.layout
    scene = context.scene
    main_box = layout.box()
    row = main_box.row()
    row.label(text="HAIR FACTORY")
    if ob:
        if ob.type == 'CURVES':
            row.operator('hair_factory.convert_hair_to_mesh', text="", icon='OUTLINER_DATA_MESH')
            row.separator()
        if ob.type == 'MESH':
            if "HF_BAKED" in dict(ob).keys():
                row.operator('hair_factory.bake_destination', text="", icon='IMAGE')
                row.separator()
    else:
        row.separator()
        row.separator()
    row.operator("hair_factory.load_scalp", text="", icon='BLENDER')
    row.operator("hair_factory.load_beadz", text="", icon='OUTLINER_OB_MESH')
    row.operator("hair_factory.load_htc", text="", icon='CURVES')
    col = main_box.column()
    col.template_list('OBJECT_UL_hair_curves_viewer', '', bpy.data, 'objects', scene, 'active_object_idx')
    main_io_panel(context, col)
    if ob:
        cps = context.scene.tool_settings.curve_paint_settings
        region_type = context.region.type
        if ob.type == "CURVES":
            # MODES
            if ob.mode == "SCULPT_CURVES":
                col = main_box.column()
                row = col.row()
                row.prop(context.space_data.overlay, "show_sculpt_curves_cage")
                row.prop(context.space_data.overlay, "sculpt_curves_cage_opacity")
                col = main_box.column()
                col.prop(context.space_data.overlay, "sculpt_mode_mask_opacity")
                col = main_box.column()
                col.separator()
                row = col.row()
                row.operator("curves.snap_curves_to_surface")
            elif ob.mode == "EDIT":
                col = main_box.column()
                row = col.row()
                row.operator("curves.draw")
                col = main_box.column()
                row = col.row()
                row.prop(cps, "curve_type", text="")
                row.prop(cps, "depth_mode", expand=True)
                draw_box = layout.box()
                draw_box.label(text="Extra Options")
                col = draw_box.column()
                col.separator()
                if cps.curve_type == 'BEZIER':
                    col.prop(cps, "fit_method")
                    col.prop(cps, "error_threshold")
                    row = col.row(heading="Detect Corners", align=True)
                    row = draw_box.row(heading="Corners", align=True)
                    row.prop(cps, "use_corners_detect", text="")
                    sub = row.row(align=True)
                    sub.active = cps.use_corners_detect
                    sub.prop(cps, "corner_angle", text="")
                    draw_box.separator()
                col = draw_box.column(align=True)
                col.prop(cps, "radius_taper_start", text="Taper Start", slider=True)
                col.prop(cps, "radius_taper_end", text="End", slider=True)
                col = draw_box.column(align=True)
                col.prop(cps, "radius_min", text="Radius Min")
                col.prop(cps, "radius_max", text="Max")
                col.prop(cps, "use_pressure_radius")
                if cps.depth_mode == 'SURFACE':
                    draw_box.separator()
                    col = draw_box.column()
                    col.prop(cps, "use_project_only_selected")
                    col.prop(cps, "surface_offset")
                    col.prop(cps, "use_offset_absolute")
                    col.prop(cps, "use_stroke_endpoints")
                    if cps.use_stroke_endpoints:
                        colsub = draw_box.column(align=True)
                        colsub.prop(cps, "surface_plane")
        if ob.type in ["CURVES", "MESH"] and ob.mode == 'OBJECT':
            mod_stack_gui(self, context)


# Does checks to see if there is anything to draw. Basically a poll func.
def _gui_draw(self, context):
    layout = self.layout
    ob = context.object
    dock = None
    if not ob:
        layout.box().label(text="No object selected!!!")
    else:
        modifiers = getattr(ob, "modifiers", None)
        if (not modifiers) or (len(modifiers) == 0):
            layout.box().label(text="Object has no modifiers!!!")
        else:
            modifier = modifiers.active
            if modifier.type != "NODES":
                layout.box().label(text="Active modifier is not a node group!!!")
            else:
                dock = layout.box()
    return dock


# Draws a dynamic node group panel. If there are panels inside of panels, it will draw those panels unnested.
def node_gui(tree, modifier, layout_dock, is_panel=False):
    for input in tree:
        if input.item_type == 'SOCKET':
            socket_type = getattr(input, "socket_type", None)
            if socket_type:
                if (socket_type != 'NodeSocketGeometry') and (input.hide_in_modifier != True) and (input.in_out == "INPUT"):
                    if ((not is_panel) and (input.parent.name == '')) or ((is_panel) and (input.parent.name != '')):
                        col = layout_dock.column()
                        col.prop(data=modifier, property=f'["{input.identifier}"]', text=input.name)
        elif input.item_type == 'PANEL':
            if not is_panel:
                header, panel = layout_dock.panel(f"PT_{input.name}", default_closed=input.default_closed)
                header.label(text=input.name)
                if panel:
                    p_box = panel.box()
                    node_gui(input.interface_items, modifier, p_box, is_panel=True)
        else:
            continue


def node_group_io(modifier, layout_dock):
    iheader, ipanel = layout_dock.box().panel("GNIO", default_closed=True)
    iheader.label(text=f"{modifier.node_group.name}   Save | Load")
    if ipanel:
        io_box = ipanel.box()
        col = io_box.column()
        col.separator()
        rcol = col.row()
        rcol.prop(modifier.node_group, 'hf_node_group_preset_name', text="Preset Name")
        rcol.operator("hair_factory.save_node_group", text='', icon='FILE_TICK')
        col.separator()
        ltcol = col.row()
        (ltcol.label(text="Load Type:     " + f"{modifier.node_group.hf_node_group_load_type}") if modifier.node_group.hf_node_group_preview else ltcol.prop(modifier.node_group, 'hf_node_group_load_type', text="Load Type"))
        ltcol.separator()
        ltcol.separator()
        col.separator()
        rcol2 = col.row()
        rcol2s = rcol2.split(factor=.23)
        rcol2s.prop(modifier.node_group, 'hf_node_group_preview', text="Preview")
        rcol2s.prop(modifier.node_group, 'hf_node_group_presets', text="")
        rcol2.operator("hair_factory.load_node_group", text='', icon='FILE_FOLDER')
        sheader, spanel = io_box.panel(f"GNIO_{modifier.node_group.name}", default_closed=True)
        sheader.label(text=f"Extra Options")
        if spanel:
            srow = spanel.row()
            srow.prop(modifier.node_group, 'hf_node_group_preset_search')
            srow.separator()
            srow.separator()
            spanel.separator()
            srow = spanel.row()
            srow.prop(modifier.node_group, 'hf_node_group_preset_rename', text="Rename Preset")
            srow.operator("hair_factory.rename_node_group_preset", text='', icon='TEXT')
            spanel.separator()
            srow = spanel.row()
            srow.prop(modifier.node_group, 'hf_node_group_export_path', text="Export Path")
            srow.operator("hair_factory.export_node_group_preset", text='', icon='DOCUMENTS')


#draws a control panel for the selected bake node settings.
def bake_gui(modifier, layout_dock):
    bake_count = len(modifier.bakes)
    if bake_count > 0:
        main_box = layout_dock.box()
        baker_box = main_box.box()
        baker_box.label(text="Bake Node Controls")
        try:
            baker_box.prop(bpy.context.object, "available_bake_nodes", text="Select")
            (None if bpy.context.object.available_bake_nodes == 'None' else baker_box.prop(bpy.context.object, "active_bake_node_mode", text="Mode"))
            (None if bpy.context.object.available_bake_nodes == 'None' else baker_box.prop(bpy.context.object, "active_bake_modifier_target", text="Bake Target"))
            (None if bpy.context.object.active_bake_modifier_target != 'DISK' else baker_box.prop(bpy.context.object, "active_bake_node_destination", text="Bake Path"))
            baker_split = baker_box.split(factor=.8, align=True)
            (None if bpy.context.object.available_bake_nodes == 'None' else baker_split.operator("hair_factory.bake_node_bake", text="Bake"))
            (None if bpy.context.object.available_bake_nodes == 'None' else baker_split.operator("hair_factory.bake_node_delete", text="", icon="X"))
            (None if bpy.context.object.available_bake_nodes == 'None' else baker_box.label(text=f"Execution Time:   {str(get_execution_time(bpy.context.object) * 1000)} ms"))
            # A list of all of the bake nodes in the active node group and their settings.
            header, panel = main_box.panel("BakeData", default_closed=True)
            header.label(text="Available Bake Nodes Info")
            if panel:
                for bake in modifier.bakes:
                    bake_box = panel.box()
                    bake_box.label(text=f"Owner: {bake.node.active_item.id_data.name}")
                    bake_box.label(text=f"Name: {bake.node.name}")
                    bake_box.label(text=f"Session_uuid: {modifier.id_data.session_uid}")
                    bake_box.label(text=f"Mode: {bake.bake_mode}")
                    bake_box.label(text=f"ID: {bake.bake_id}")
                    bake_box.label(text=f"Modifier Target: {modifier.bake_target}")
                    bake_box.label(text=f"Destination: {modifier.bake_directory}")
        except:
            baker_box.label(text="Error displaying bakes!")


def special_node_gui(nodes, layout_dock, ntype='CURVE_FLOAT'):
    for node in nodes:
        if node.type == ntype and char.find(node.name, bpy.context.scene.hf_special_node_search).item() > -1:
            box = layout_dock.box()
            col = box.column()
            col.label(text=f"{node.id_data.name} | {node.name}")
            col.template_node_inputs(node)
            header, panel = box.panel(f"IO_{node.name}", default_closed=True)
            header.label(text=f"{node.name}   Save | Load")
            if panel:
                io_box = panel.box()
                col = io_box.column()
                col.separator()
                rcol = col.row()
                rcol.prop(node, 'hf_node_preset_name', text="Preset Name")
                rcol.operator("hair_factory.save_node", text='', icon='FILE_TICK').node = repr(node)
                col.separator()
                rcol2 = col.row()
                rcol2s = rcol2.split(factor=.23)
                rcol2s.prop(node, 'hf_node_preview', text="Preview")
                rcol2s.prop(node, 'hf_node_presets', text="")
                rcol2.operator("hair_factory.load_node", text='', icon='FILE_FOLDER').node = repr(node)
                sheader, spanel = io_box.panel(f"XO_{node.name}", default_closed=True)
                sheader.label(text=f"Extra Options")
                if spanel:
                    srow = spanel.row()
                    srow.prop(node, 'hf_node_preset_search')
                    srow.separator()
                    srow.separator()
                    spanel.separator()
                    srow = spanel.row()
                    srow.prop(node, 'hf_node_preset_rename', text="Rename Preset")
                    srow.operator("hair_factory.rename_node_preset", text='', icon='TEXT').node = repr(node)
                    spanel.separator()
                    srow = spanel.row()
                    srow.prop(node, 'hf_node_export_path', text="Export Path")
                    srow.operator("hair_factory.export_node_preset", text='', icon='DOCUMENTS').node = repr(node)
        if node.type == 'GROUP':
            gnodes = node.node_tree.nodes
            special_node_gui(gnodes, layout_dock, ntype=ntype)


def get_GN_material_sockets(self, context):
    data = [("None", "None", "")]
    ob = context.object
    if ob:
        if ob.modifiers:
            modifier = ob.modifiers.active
            if modifier.type == "NODES":
                if hasattr(modifier, 'node_group') and hasattr(modifier.node_group, 'interface'):
                    data = data + [(i.identifier, i.name, '') for i in modifier.node_group.interface.items_tree if getattr(i, 'socket_type', None) == 'NodeSocketMaterial']
    return data


def get_GN_object_sockets(self, context):
    data = [("None", "None", "")]
    ob = context.object
    if ob:
        data = data + [("OBJECT", ob.name, '')]
        if ob.modifiers:
            modifier = ob.modifiers.active
            if modifier.type == "NODES":
                if hasattr(modifier, 'node_group') and hasattr(modifier.node_group, 'interface'):
                    data = data + [(i.identifier, i.name, '') for i in modifier.node_group.interface.items_tree if getattr(i, 'socket_type', None) == 'NodeSocketObject']
    return data


def set_mod_socket_mat(modifier, socket, material):
    if material in [None, 'None']:
        modifier[socket] = None
    else:
        modifier[socket] = material
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()


def material_bake_gui(self, context):
    layout_dock = self.layout.box()
    scene = context.scene
    baker_props = scene.baker_props
    header, panel = layout_dock.panel(f"Material_Bake_Panel", default_closed=True)
    header.label(text="Material Bake Panel")
    if panel:
        col = panel.column()
        col.prop(scene, "hf_ob_socs", text="Object")
        col.prop(scene, "hf_available_mats", text="Material")
        col.prop(baker_props, "save_mode", text="Save Mode")
        col.prop(baker_props, "image_types", text="Type")
        col.prop(baker_props, "active_uv", text="UV Map")
        col.prop(baker_props, "image_size", text="Size")
        row = col.row()
        row.prop(baker_props, "sample_count")
        row.prop(baker_props, "use_denoise", text="")
        (None if baker_props.save_mode != 'EXTERNAL' else col.prop(baker_props, "destination_path", text="Save Path"))
        col.operator("hair_factory.bake_material_texture", text="Bake")
        col.separator()


def material_gui(self, context, modifier, layout):
    try:
        ntypes = ['RGB', 'CURVE_FLOAT', 'VALTORGB', 'CURVE_VEC', 'CURVE_RGB']
        if any([getattr(input, 'socket_type', None) == 'NodeSocketMaterial' for input in modifier.node_group.interface.items_tree]):
            nodes = None
            material = None
            socket = bpy.context.scene.hf_mat_socs
            layout.prop(bpy.context.scene, 'hf_mat_socs')
            if socket != "None":
                material = modifier[socket]
                if material not in [None, ""]:
                    nodes = material.node_tree.nodes
                    col = layout.column()
                    row = col.row()
                    row.prop(data=modifier, property=f'["{socket}"]', text="Material")
                    set_mat = row.operator(OBJECT_OT_hf_set_mat.bl_idname, text="", icon='X')
                    set_mat.socket = socket
                    set_mat.is_mat = False
                else:
                    col = layout.column()
                    row = col.row()
                    row.prop_search(bpy.context.scene, 'hf_available_mats', bpy.data, 'materials')
                    set_mat = row.operator(OBJECT_OT_hf_set_mat.bl_idname, text="", icon='FILE_FOLDER')
                    set_mat.socket = socket
                    set_mat.is_mat = True
            # Load Materials
            header, panel = layout.box().panel("MTIO", default_closed=True)
            hrow = header.row()
            hrow.label(text=f"Material    Save | Load")
            hrow.operator('hair_factory.launch_material_new', text="", icon='ADD')
            if material:
                if panel:
                    io_box = panel.box()
                    col = io_box.column()
                    col.separator()
                    rcol = col.row()
                    rcol.prop(material, 'hf_mat_preset_name', text="Preset Name")
                    rcol.operator("hair_factory.save_mat", text='', icon='FILE_TICK').material = repr(material)
                    col.separator()
                    col.separator()
                    rcol2 = col.row()
                    rcol2s = rcol2.split(factor=.23)
                    rcol2s.prop(material, 'hf_mat_preview', text="Preview")
                    rcol2s.prop(material, 'hf_mat_presets', text="")
                    rcol2.operator("hair_factory.load_mat", text='', icon='FILE_FOLDER').material = repr(material)
                    sheader, spanel = io_box.panel(f"MEIO", default_closed=True)
                    sheader.label(text=f"Extra Options")
                    if spanel:
                        srow = spanel.row()
                        srow.prop(material, 'hf_mat_preset_search')
                        srow.separator()
                        srow.separator()
                        spanel.separator()
                        srow = spanel.row()
                        srow.prop(material, 'hf_mat_preset_rename', text="Rename Preset")
                        srow.operator("hair_factory.rename_mat_preset", text='', icon='TEXT').material = repr(material)
                        spanel.separator()
                        srow = spanel.row()
                        srow.prop(material, 'hf_mat_export_path', text="Export Path")
                        srow.operator("hair_factory.export_mat_preset", text='', icon='DOCUMENTS').material = repr(material)
            # Nodes
            node_box = layout.box()
            nheader, npanel = node_box.panel(f"Material Nodes", default_closed=True)
            nheader.label(text=f"Material Nodes")
            if npanel:
                if nodes:
                    npanel.prop(bpy.context.scene, 'hf_special_node_search')
                    for ntype in ntypes:
                        special_node_gui(nodes, npanel, ntype=ntype)
            # Groups
            group_box = layout.box()
            gheader, gpanel = group_box.panel(f"Material Node Groups", default_closed=True)
            gheader.label(text=f"Material Node Groups")
            if gpanel:
                if nodes:
                    for node in nodes:
                        if node.type == 'GROUP':
                            if not all(i.is_linked for i in node.inputs):
                                gbox = gpanel.box()
                                gbox.label(text=f"{node.node_tree.name}")
                                for input in node.inputs:
                                    if not input.is_linked:
                                        col = gbox.column()
                                        col.prop(input, 'default_value', text=input.name)
        material_bake_gui(self, context)
    except:
        material_bake_gui(self, context)


def phy_io_gui(layout_dock, ob):
    header, panel = layout_dock.box().panel("PHY_IO", default_closed=True)
    header.label(text=f"Physics   Save | Load")
    if panel:
        io_box = panel.box()
        col = io_box.column()
        col.separator()
        rcol = col.row()
        rcol.prop(ob.data, 'hf_phy_preset_name', text="Preset Name")
        rcol.operator("hair_factory.save_phy", text='', icon='FILE_TICK')
        col.separator()
        col.separator()
        rcol2 = col.row()
        rcol2s = rcol2.split(factor=.23)
        rcol2s.prop(ob.data, 'hf_phy_preview', text="Preview")
        rcol2s.prop(ob.data, 'hf_phy_presets', text="")
        rcol2.operator("hair_factory.load_phy", text='', icon='FILE_FOLDER')
        sheader, spanel = io_box.panel("PHY_IO_EO", default_closed=True)
        sheader.label(text=f"Extra Options")
        if spanel:
            srow = spanel.row()
            srow.prop(ob.data, 'hf_phy_preset_search')
            srow.separator()
            srow.separator()
            spanel.separator()
            srow = spanel.row()
            srow.prop(ob.data, 'hf_phy_preset_rename', text="Rename Preset")
            srow.operator("hair_factory.rename_phy_preset", text='', icon='TEXT')
            spanel.separator()
            srow = spanel.row()
            srow.prop(ob.data, 'hf_phy_export_path', text="Export Path")
            srow.operator("hair_factory.export_phy_preset", text='', icon='DOCUMENTS')


def col_io_gui(layout_dock, ob):
    header, panel = layout_dock.box().panel("COL_IO", default_closed=True)
    header.label(text=f"Collision   Save | Load")
    if panel:
        io_box = panel.box()
        col = io_box.column()
        col.separator()
        rcol = col.row()
        rcol.prop(ob.data, 'hf_col_preset_name', text="Preset Name")
        rcol.operator("hair_factory.save_col", text='', icon='FILE_TICK')
        col.separator()
        col.separator()
        rcol2 = col.row()
        rcol2s = rcol2.split(factor=.23)
        rcol2s.prop(ob.data, 'hf_col_preview', text="Preview")
        rcol2s.prop(ob.data, 'hf_col_presets', text="")
        rcol2.operator("hair_factory.load_col", text='', icon='FILE_FOLDER')
        sheader, spanel = io_box.panel("COL_IO_EO", default_closed=True)
        sheader.label(text=f"Extra Options")
        if spanel:
            srow = spanel.row()
            srow.prop(ob.data, 'hf_col_preset_search')
            srow.separator()
            srow.separator()
            spanel.separator()
            srow = spanel.row()
            srow.prop(ob.data, 'hf_col_preset_rename', text="Rename Preset")
            srow.operator("hair_factory.rename_col_preset", text='', icon='TEXT')
            spanel.separator()
            srow = spanel.row()
            srow.prop(ob.data, 'hf_col_export_path', text="Export Path")
            srow.operator("hair_factory.export_col_preset", text='', icon='DOCUMENTS')


def cloth_phy_gui(layout, modifier):
    settings = modifier.settings
    collision_settings = modifier.collision_settings
    is_angular = (settings.bending_model == 'ANGULAR')
    psbox = layout.box()
    col_ps = psbox.column()
    col_ps.prop(settings, 'quality', text="Quality Steps")
    col_ps.prop(settings, 'time_scale', text="Speed Multiplier")
    # Physical Properties
    col_ps.separator()
    header_pp, panel_pp = col_ps.box().panel("Physical Properties", default_closed=False)
    header_pp.label(text="Physical Properties")
    if panel_pp:
        col_pp = panel_pp.column()
        col_pp.prop(settings, 'mass', text="Vertex Mass")
        col_pp.prop(settings, 'air_damping', text="Air Viscosity")
        col_pp.prop(settings, 'bending_model', text="Bending Model")
        # Stiffness
        col_pp.separator()
        header_st, panel_st = col_pp.box().panel("Stiffness", default_closed=False)
        header_st.label(text="Stiffness")
        if panel_st:
            col_st = panel_st.column()
            col_st.prop(settings, 'tension_stiffness', text=("Tension" if is_angular else "Structural"))
            if is_angular:
                col_st.prop(settings, 'compression_stiffness', text="Compression")
            col_st.prop(settings, 'shear_stiffness', text="Shear")
            col_st.prop(settings, 'bending_stiffness', text="Bending")
        # Damping
        col_pp.separator()
        header_da, panel_da = col_pp.box().panel("Damping", default_closed=False)
        header_da.label(text="Damping")
        if panel_da:
            col_da = panel_da.column()
            col_da.prop(settings, 'tension_damping', text=("Tension" if is_angular else "Structural"))
            if is_angular:
                col_da.prop(settings, 'compression_damping', text="Compression")
            col_da.prop(settings, 'shear_damping', text="Shear")
            col_da.prop(settings, 'bending_damping', text="Bending")
        # Internal Springs
        col_pp.separator()
        header_is, panel_is = col_pp.box().panel("Internal Springs", default_closed=True)
        h_is_row = header_is.row()
        h_is_row.prop(settings, 'use_internal_springs', text="")
        h_is_row.label(text="Internal Springs")
        if panel_is:
            col_is = panel_is.column()
            col_is.prop(settings, 'internal_spring_max_length', text="Max Spring Creation Length")
            col_is.prop(settings, 'internal_spring_max_diversion', text="Max Creation Diversion")
            col_is.prop(settings, 'internal_spring_normal_check', text="Check Surface Normals")
            col_is.prop(settings, 'internal_tension_stiffness', text="Tension")
            col_is.prop(settings, 'internal_compression_stiffness', text="Compression")
            col_is.prop(settings, 'vertex_group_intern', text="Vertex Group")
            col_is.prop(settings, 'internal_tension_stiffness_max', text="Max Tension")
            col_is.prop(settings, 'internal_compression_stiffness_max', text="Max Compression")
        # Pressure
        col_pp.separator()
        header_pr, panel_pr = col_pp.box().panel("Pressure", default_closed=True)
        h_pr_row = header_pr.row()
        h_pr_row.prop(settings, 'use_pressure', text="")
        h_pr_row.label(text="Pressure")
        if panel_pr:
            col_pr = panel_pr.column()
            col_pr.prop(settings, 'uniform_pressure_force', text="Pressure")
            col_pr.prop(settings, 'use_pressure_volume', text="Custom Volume")
            col_pr.prop(settings, 'target_volume', text="Target Volume")
            col_pr.prop(settings, 'pressure_factor', text="Pressure Scale")
            col_pr.prop(settings, 'fluid_density', text="Fluid Density")
            col_pr.prop(settings, 'vertex_group_pressure', text="Vertex Group")
    # Shape
    col_ps.separator()
    header_sh, panel_sh = col_ps.box().panel("Shape", default_closed=False)
    header_sh.label(text="Shape")
    if panel_sh:
        col_sh = panel_sh.column()
        col_sh.prop(settings, 'vertex_group_mass', text="Pin Group")
        col_sh.prop(settings, 'pin_stiffness', text="Stiffness")
    # Collisions
    col_ps.separator()
    header_co, panel_co = col_ps.box().panel("Collisions", default_closed=False)
    header_co.label(text="Collisions")
    if panel_co:
        col_co = panel_co.column()
        col_co.prop(collision_settings, 'collision_quality', text="Quality")
        # Object Collision
        col_co.separator()
        header_oc, panel_oc = col_co.box().panel("Object Collisions", default_closed=False)
        h_oc_row = header_oc.row()
        h_oc_row.prop(collision_settings, 'use_collision', text="")
        h_oc_row.label(text="Object Collisions")
        if panel_oc:
            col_oc = panel_oc.column()
            col_oc.prop(collision_settings, 'distance_min', text="Distance")
            col_oc.prop(collision_settings, 'impulse_clamp', text="Impulse Clamping")
            col_oc.prop(collision_settings, 'vertex_group_object_collisions', text="Vertex Group")
            col_oc.prop(collision_settings, 'collection', text="Collision Collection")
        # Self Collision
        col_co.separator()
        header_sc, panel_sc = col_co.box().panel("Self Collisions", default_closed=False)
        h_sc_row = header_sc.row()
        h_sc_row.prop(collision_settings, 'use_self_collision', text="")
        h_sc_row.label(text="Self Collisions")
        if panel_sc:
            col_sc = panel_sc.column()
            col_sc.prop(collision_settings, 'self_friction', text="Friction")
            col_sc.prop(collision_settings, 'self_distance_min', text="Distance")
            col_sc.prop(collision_settings, 'self_impulse_clamp', text="Impulse Clamping")
            col_sc.prop(collision_settings, 'vertex_group_self_collisions', text="Vertex Group")


def soft_body_phy_gui(layout, modifier):
    settings = modifier.settings
    psbox = layout.box()
    col_ps = psbox.column()
    col_ps.prop(settings, 'collision_collection', text="Collision Collection")
    # Object
    col_ps.separator()
    header_ob, panel_ob = col_ps.box().panel("Object", default_closed=False)
    header_ob.label(text="Object")
    if panel_ob:
        col_ob = panel_ob.column()
        col_ob.prop(settings, 'friction', text="Friction")
        col_ob.prop(settings, 'mass', text="Mass")
        col_ob.prop(settings, 'vertex_group_mass', text="Control Point")
    # Simulation
    col_ps.separator()
    header_si, panel_si = col_ps.box().panel("Simulation", default_closed=True)
    header_si.label(text="Simulation")
    if panel_si:
        col_si = panel_si.column()
        col_si.prop(settings, 'speed', text="Speed")
    # Goal
    col_ps.separator()
    header_go, panel_go = col_ps.box().panel("Goal", default_closed=False)
    h_go_row = header_go.row()
    h_go_row.prop(settings, 'use_goal', text="")
    h_go_row.label(text="Goal")
    if panel_go:
        col_go = panel_go.column()
        col_go.prop(settings, 'vertex_group_goal', text="Vertex Group")
        # Settings
        col_go.separator()
        header_se, panel_se = col_go.box().panel("Settings", default_closed=False)
        header_se.label(text="Settings")
        if panel_se:
            col_se = panel_se.column()
            col_se.prop(settings, 'goal_spring', text="Stiffness")
            col_se.prop(settings, 'goal_friction', text="Damping")
        # Strengths
        col_go.separator()
        header_st, panel_st = col_go.box().panel("Strengths", default_closed=False)
        header_st.label(text="Strengths")
        if panel_st:
            col_st = panel_st.column()
            col_st.prop(settings, 'goal_default', text="Default")
            col_st.prop(settings, 'goal_min', text="Min")
            col_st.prop(settings, 'goal_max', text="Max")
    # Edges
    col_ps.separator()
    header_ed, panel_ed = col_ps.box().panel("Edges", default_closed=False)
    h_ed_row = header_ed.row()
    h_ed_row.prop(settings, 'use_edges', text="")
    h_ed_row.label(text="Edges")
    if panel_ed:
        col_ed = panel_ed.column()
        col_ed.prop(settings, 'vertex_group_spring', text="Springs")
        col_ed.prop(settings, 'pull', text="Pull")
        col_ed.prop(settings, 'push', text="Push")
        col_ed.prop(settings, 'damping', text="Damp")
        col_ed.prop(settings, 'plastic', text="Plasticity")
        col_ed.prop(settings, 'bend', text="Bemding")
        col_ed.prop(settings, 'spring_length', text="Length")
        row = col_ed.row()
        row.label(text="Collision")
        row.prop(settings, 'use_edge_collision', text="Edge")
        row.prop(settings, 'use_face_collision', text="Face")
        # Aerodynamics
        col_ed.separator()
        header_ae, panel_ae = col_ed.box().panel("Aerodynamics", default_closed=True)
        header_ae.label(text="Aerodynamics")
        if panel_ae:
            col_ae = panel_ae.column()
            col_ae.prop(settings, 'aerodynamics_type', text="Type")
            col_ae.prop(settings, 'aero', text="Factor")
        # Stiffness
        col_ed.separator()
        header_sf, panel_sf = col_ed.box().panel("Stiffness", default_closed=True)
        h_sf_row = header_sf.row()
        h_sf_row.prop(settings, 'use_stiff_quads', text="Stiffness")
        if panel_sf:
            col_sf = panel_sf.column()
            col_sf.prop(settings, 'shear', text="Shear")
    # Self Collisions
    col_ps.separator()
    header_sc, panel_sc = col_ps.box().panel("Self Collisions", default_closed=True)
    h_sc_row = header_sc.row()
    h_sc_row.prop(settings, 'use_self_collision', text="Self Collisions")
    if panel_sc:
        col_sc = panel_sc.column()
        col_sc.prop(settings, 'collision_type', text="Calculation Type")
        col_sc.prop(settings, 'ball_size', text="Ball Size")
        col_sc.prop(settings, 'ball_stiff', text="Stiffness")
        col_sc.prop(settings, 'ball_damp', text="Ball Dampening")
    # Solver
    col_ps.separator()
    header_so, panel_so = col_ps.box().panel("Solver", default_closed=True)
    header_so.label(text="Solver")
    if panel_so:
        col_so = panel_so.column()
        col_so.prop(settings, 'step_min', text="Step Size Min")
        col_so.prop(settings, 'step_max', text="Max")
        col_so.prop(settings, 'use_auto_step', text="Auto-Step")
        col_so.prop(settings, 'error_threshold', text="Error Limit")
        # Diagnostic
        col_so.separator()
        header_di, panel_di = col_so.box().panel("Diagnostic", default_closed=True)
        header_di.label(text="Diagnostic")
        if panel_di:
            col_di = panel_di.column()
            col_di.prop(settings, 'use_diagnose', text="Print Performance to Console")
            col_di.prop(settings, 'use_estimate_matrix', text="Estimate Transforms")
        # Helpers
        col_so.separator()
        header_he, panel_he = col_so.box().panel("Helpers", default_closed=True)
        header_he.label(text="Helpers")
        if panel_he:
            col_he = panel_he.column()
            col_he.prop(settings, 'choke', text="Choke")
            col_he.prop(settings, 'fuzzy', text="Fuzzy")


def pin_controller_gui(layout, ob):
    for m in ob.modifiers:
        if m.type == 'NODES':
            if m.node_group:
                if m.node_group.name.split(".")[0] == "HAIR_PIN_WEIGHTS":
                    nodes = m.node_group.nodes
                    node = next((n for n in nodes if n.type == 'CURVE_FLOAT'))
                    box = layout.box()
                    col = box.column()
                    col.label(text=f"{node.name}")
                    col.template_node_inputs(node)
                    header, panel = box.panel(f"IO_{node.name}", default_closed=True)
                    header.label(text=f"{node.name}   Save | Load")
                    if panel:
                        io_box = panel.box()
                        col = io_box.column()
                        col.separator()
                        rcol = col.row()
                        rcol.prop(node, 'hf_node_preset_name', text="Preset Name")
                        rcol.operator("hair_factory.save_node", text='', icon='FILE_TICK').node = repr(node)
                        col.separator()
                        rcol2 = col.row()
                        rcol2s = rcol2.split(factor=.23)
                        rcol2s.prop(node, 'hf_node_preview', text="Preview")
                        rcol2s.prop(node, 'hf_node_presets', text="")
                        rcol2.operator("hair_factory.load_node", text='', icon='FILE_FOLDER').node = repr(node)
                        sheader, spanel = io_box.panel(f"XO_{node.name}", default_closed=True)
                        sheader.label(text=f"Extra Options")
                        if spanel:
                            srow = spanel.row()
                            srow.prop(node, 'hf_node_preset_search')
                            srow.separator()
                            srow.separator()
                            spanel.separator()
                            srow = spanel.row()
                            srow.prop(node, 'hf_node_preset_rename', text="Rename Preset")
                            srow.operator("hair_factory.rename_node_preset", text='', icon='TEXT').node = repr(node)
                            spanel.separator()
                            srow = spanel.row()
                            srow.prop(node, 'hf_node_export_path', text="Export Path")
                            srow.operator("hair_factory.export_node_preset", text='', icon='DOCUMENTS').node = repr(node)



def phy_ob_gui(layout, ob):
    if "PHY_HAIR".split(".")[0] in dict(ob).keys():
        ob = ob["PHY_HAIR"]
    opm = (None if not "PHY_MESH" in dict(ob) else ob["PHY_MESH"])
    opb = (None if not "PHY_BONES" in dict(ob) else ob["PHY_BONES"])
    pm = ("None" if opm == None else opm.name)
    pb = ("None" if opb == None else opb.name)
    ms_box = layout.box()
    row = ms_box.row()
    row.label(text=f"[Physics Objects]", icon='PRESET')
    if pm:
        row = ms_box.row()
        row.label(text=f"{pm}", icon='GROUP_VERTEX')
        if opm:
            (row.prop(opm, 'show_in_front', text="", emboss=False, icon_only=True, icon='HIDE_OFF') if opm.show_in_front else row.prop(opm, 'show_in_front', text="", emboss=False, icon_only=True, icon='HIDE_ON'))
            row.prop(opm, 'hide_select', text="", emboss=False, icon_only=True)
            row.prop(opm, 'hide_viewport', text="", emboss=False, icon_only=True)
    if pb:
        row = ms_box.row()
        row.label(text=f"{pb}", icon='GROUP_BONE')
        if opb:
            (row.prop(opb, 'show_in_front', text="", emboss=False, icon_only=True, icon='HIDE_OFF') if opb.show_in_front else row.prop(opb, 'show_in_front', text="", emboss=False, icon_only=True, icon='HIDE_ON'))
            row.prop(opb, 'hide_select', text="", emboss=False, icon_only=True)
            row.prop(opb, 'hide_viewport', text="", emboss=False, icon_only=True)
        if not opb.hide_viewport:
            col = ms_box.column()
            col.prop(ob["PHY_BONES"].data, 'display_type')
    if opm:
        if ob.type == 'CURVES':
            if ob.data.hf_phy_ptype == "CLOTH":
                p_col = layout.column()
                pin_controller_gui(p_col, opm)
        pbox = layout.box()
        row = pbox.row()
        opmm = opm.modifiers
        if opmm:
            header, panel = pbox.panel("Physics Settings", default_closed=True)
            header.label(text="Hair Physics Settings")
            if panel:
                for m in opmm:
                    if m.type in ["CLOTH", "SOFT_BODY"]:
                        if m.type == "CLOTH":
                            cloth_phy_gui(panel, m)
                            phy_io_gui(panel, ob)
                        if m.type == "SOFT_BODY":
                            soft_body_phy_gui(panel, m)
                            phy_io_gui(panel, ob)


def collision_gui(layout, ob):
    collision_ob = ob.parent
    if collision_ob:
        for modifier in collision_ob.modifiers:
            if modifier.type == 'COLLISION':
                header, panel = layout.box().panel(f"{modifier.name}_Collision Settings", default_closed=True)
                header.label(text="Hair Collision Settings")
                if panel:
                    mrow = panel.row()
                    sm_box = mrow.box()
                    sm_box.label(text=f"{modifier.name}")
                    collision = collision_ob.collision
                    srow = sm_box.row()
                    srow.prop(collision, "absorption")
                    srow = sm_box.row()
                    srow.prop(collision, "thickness_outer")
                    srow = sm_box.row()
                    srow.prop(collision, "damping")
                    srow = sm_box.row()
                    srow.prop(collision, "cloth_friction")
                    col_io_gui(panel, ob)


def physics_gui(self, context):
    layout_dock = self.layout.box()
    ob = context.object
    if "PHY_HAIR".split(".")[0] in dict(ob).keys():
        ob = ob["PHY_HAIR"]
    col = layout_dock.column()
    if ob.type == 'CURVES':
        (col.label(text=f"{ob.data.hf_phy_ptype}") if ("PHY_BONES" in dict(ob).keys()) else col.prop(ob.data, 'hf_phy_ptype'))
        if ob.data.hf_phy_ptype == 'CLOTH':
            col.prop(ob.data, 'hf_phy_offset')
    row = col.row()
    row.label(text=f"[Physics Controls]")
    row.operator("hair_factory.enable_physics", text="", icon='PHYSICS')
    row.operator("hair_factory.disable_physics", text="", icon='X')
    row.operator("hair_factory.bake_phys", text="", icon='NLA')
    if "PHY_BONES" in dict(ob).keys():
        row.prop(ob["PHY_BONES"].data, "hf_selected_bones_only", text="")
        phy_ob_gui(layout_dock, ob)
        collision_gui(layout_dock, ob)


def GUI_draw(self, context):
    ntypes = ['CURVE_FLOAT', 'VALTORGB', 'CURVE_VEC', 'CURVE_RGB', 'INPUT_COLOR']
    ob = context.object
    scene = context.scene
    layout = self.layout
    if ob:
        try:
            modifiers = getattr(ob, "modifiers", None)
            if modifiers and len(modifiers) > 0:
                modifier = (modifiers.active if not isinstance(modifiers.active, type(None)) else modifiers[-1])
                if "PHY_HAIR".split(".")[0] not in dict(ob).keys():
                    layout.prop(context.scene, 'hf_gui_type')
                if modifier.type == 'NODES':
                    if context.scene.hf_gui_type in ntypes:
                        if getattr(modifier, "node_group", None) and getattr(modifier.node_group, "nodes", None):
                            layout.prop(bpy.context.scene, 'hf_special_node_search')
                            special_node_gui(modifier.node_group.nodes, layout, ntype=context.scene.hf_gui_type)
                    elif context.scene.hf_gui_type == 'NODE':
                        dock = _gui_draw(self, context)
                        if dock and hasattr(modifier, 'node_group') and hasattr(modifier.node_group, 'name'):
                            header, panel = dock.panel("Node_Group_DD", default_closed=False)
                            header.label(text=f"{modifier.name} | {modifier.node_group.name}")
                            if panel:
                                node_gui(modifier.node_group.interface.items_tree, modifier, panel)
                            node_group_io(modifier, layout)
                    elif context.scene.hf_gui_type == 'BAKE':
                        bake_gui(modifier, layout)
                    elif context.scene.hf_gui_type == 'MATERIAL':
                        material_gui(self, context, modifier, layout)
                    elif context.scene.hf_gui_type == 'MAIN':
                        main_gui(self, context)
                    elif context.scene.hf_gui_type == 'PHYSICS':
                        physics_gui(self, context)
                    else:
                        layout.label(text="Nothing to display")
                else:
                    main_gui(self, context)
                    if "PHY_HAIR".split(".")[0] in dict(ob).keys():
                        physics_gui(self, context)
            else:
                main_gui(self, context)
                if "PHY_HAIR".split(".")[0] in dict(ob).keys():
                        physics_gui(self, context)
        except:
            layout.label(text="Error occurred in displaying items!")
    else:
        main_gui(self, context)


### PANEL ###

class HAIRFACTORY_PT_main_panel(Panel):
    """
    """
    bl_label = "MORZIO HAIR FACTORY"
    bl_idname = "HAIRFACTORY_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Morzio Hair Factory"
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.scene.name.split(".")[0] != "HAIR_TEXTURE_CREATOR"
    
    def draw(self, context):
        try:
            GUI_draw(self, context)
        except Exception as e:
            print(f"GUI: {e}")


### OPERATORS ###

class HAIRFACTORY_OT_bake_node(Operator):
    """
    """
    bl_idname = "hair_factory.bake_node_bake"
    bl_label = "Bake Node"
    bl_description = "Bake selected bake node data."
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if not ob:
            return False
        modifiers = ob.modifiers
        if len(modifiers) == 0:
            return False
        modifier = modifiers.active
        if modifier.type != 'NODES':
            return False
        bakes = modifier.bakes
        if len(bakes) == 0:
            return False
        return ob.available_bake_nodes != "None"
    
    def execute(self, context):
        ob = context.object
        modifier = ob.modifiers.active
        bake = get_selected_bake(modifier, ob.available_bake_nodes)
        bake.bake_mode = ob.active_bake_node_mode
        bake.bake_target = ob.active_bake_node_target
        modifier.bake_target = ob.active_bake_modifier_target
        modifier.bake_directory = ob.active_bake_node_destination
        object_.geometry_node_bake_single(session_uid=ob.session_uid, modifier_name=modifier.name, bake_id=int(ob.available_bake_nodes))
        return {'FINISHED'}


class HAIRFACTORY_OT_bake_delete(Operator):
    """
    """
    bl_idname = "hair_factory.bake_node_delete"
    bl_label = "Bake Delete"
    bl_description = "Delete bake node data."
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if not ob:
            return False
        modifiers = ob.modifiers
        if len(modifiers) == 0:
            return False
        modifier = modifiers.active
        if modifier.type != 'NODES':
            return False
        bakes = modifier.bakes
        if len(bakes) == 0:
            return False
        return ob.available_bake_nodes != "None"
    
    def execute(self, context):
        ob = context.object
        modifier = ob.modifiers.active
        object_.geometry_node_bake_delete_single(session_uid=ob.session_uid, modifier_name=modifier.name, bake_id=int(ob.available_bake_nodes))
        return {'FINISHED'}


class OBJECT_OT_hf_set_mat(Operator):
    """
    """
    bl_idname = "hair_factory.hf_set_mat"
    bl_label = "Set Material"
    bl_description = "Set material for node group socket. (X) for None."
    bl_options = {'REGISTER', 'UNDO'}
    
    socket: StringProperty(name="Socket", description="node group material socket")
    is_mat: BoolProperty(default=False)
    
    def execute(self, context):
        ob = context.object
        modifier = ob.modifiers.active
        material = (context.scene.hf_available_mats if self.is_mat else None)
        set_mod_socket_mat(modifier, self.socket, material)
        mn = (material.name if self.is_mat else None)
        sn = next(get_socket_name(modifier, self.socket))
        self.report({'INFO'}, f"{modifier.name} socket {sn} set to {mn}")
        return {'FINISHED'}


class MODIFIER_OT_launch_add_mat(Operator):
    bl_idname = 'hair_factory.launch_material_new'
    bl_label = 'Load Material'
    bl_description = "Load Material to file."
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        hair_factory.material_new('INVOKE_DEFAULT')
        self.report({'INFO'}, f"Launching Material popup.")
        return{'FINISHED'}


class MODIFIER_UL_modifier_stack_viewer(UIList):
    """
    """
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row()
            row.prop(item, 'name', text="", emboss=False, icon_value=1, icon=self.get_icon(item))
            row.prop(item, 'show_viewport', text="", emboss=False, icon_only=True)
            row.prop(item, 'show_render', text="", emboss=False, icon_only=True)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)
    
    def get_icon(self, item):
        icon = Modifier.bl_rna.properties['type'].enum_items[item.type].icon
        return icon


class MODIFIER_OT_launch_add_mod(Operator):
    bl_idname = 'hair_factory.launch_modifier_new'
    bl_label = 'Add Modifier to Stack'
    bl_description = "Add node group to Modifier Stack."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object is not None
    
    def execute(self, context):
        scene = context.scene
        ob = context.object
        if ob is None:
            self.report({'ERROR'}, "No Active Object")
            return{'CANCELLED'}
        hair_factory.modifier_new('INVOKE_DEFAULT')
        self.report({'INFO'}, f"Launching node group popup.")
        return{'FINISHED'}


class MODIFIER_OT_modifier_delete(Operator):
    bl_idname = 'hair_factory.modifier_delete'
    bl_label = 'Remove Modifier from Stack'
    bl_description = "Remove modifier from Modifier Stack."
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if not ob:
            return False
        count = len(ob.modifiers)
        return count > 0 and ob.active_modifier_idx < count
    
    def execute(self, context):
        ob = context.object
        if ob is None:
            self.report({'ERROR'}, "No Active Object")
            return{'CANCELLED'}
        modifiers = ob.modifiers
        index = ob.active_modifier_idx
        count = len(modifiers)
        if (count == 0):
            self.report({'ERROR'}, "Active object has no modifiers.")
            return{'CANCELLED'}
        elif (index >= count):
            self.report({'ERROR'}, "No modifiers Selected.")
            return{'CANCELLED'}
        else:
            modifier = modifiers[index]
            ng = modifier.node_group
            mn = getattr(modifier, 'name', None)
            ngn = getattr(ng, 'name', None)
            if context.preferences.addons[__package__].preferences.delete_node_group:
                delete_geo_node_modifier(ob, modifier)
            ob.active_modifier_idx -= 1
            self.report({'INFO'}, f"Removed Modifier: {mn} and Node Group: {ngn} from {ob.name}.")
        return{'FINISHED'}


class MODIFIER_OT_modifier_up(Operator):
    bl_idname = 'hair_factory.modifier_up'
    bl_label = 'Move Modifier Up in Stack'
    bl_description = "Move the Active Modofier up in the Stack."
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if not ob:
            return False
        count = len(ob.modifiers)
        return count > 0 and ob.active_modifier_idx > 0
    
    def execute(self, context):
        ob = context.object
        if ob is None:
            self.report({'ERROR'}, "No Active Object")
            return{'CANCELLED'}
        index = ob.active_modifier_idx
        modifiers = ob.modifiers
        count = len(modifiers)
        if (count == 0):
            self.report({'ERROR'}, "No Modifiers Present")
            return{'CANCELLED'}
        elif (index == 0):
            self.report({'ERROR'}, "Can not Move Up")
            return{'CANCELLED'}
        else:
            try:
                mod = modifiers[index].name
                object_.modifier_move_up(modifier=mod)
                self.report({'INFO'}, f"{mod} was moved from index {index} to {ob.active_modifier_idx}.")
            except:
                pass
            finally:
                ob.active_modifier_idx -= 1
        return{'FINISHED'}


class MODIFIER_OT_modifier_down(Operator):
    bl_idname = 'hair_factory.modifier_down'
    bl_label = 'Move Modifier Down in Stack'
    bl_description = "Move the Active Modofier down in the Stack."
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if not ob:
            return False
        count = len(ob.modifiers)
        return count > 0 and ob.active_modifier_idx < count - 1
    
    def execute(self, context):
        ob = context.object
        if ob is None:
            self.report({'ERROR'}, "No Active Object")
            return{'CANCELLED'}
        modifiers = ob.modifiers
        index = ob.active_modifier_idx
        count = len(modifiers)
        if (count == 0):
            self.report({'ERROR'}, "No Modifiers Present")
            return{'CANCELLED'}
        elif (index == count - 1):
            self.report({'ERROR'}, "Can not Move Down")
            return{'CANCELLED'}
        else:
            mod = modifiers[index].name
            object_.modifier_move_down(modifier=mod)
            ob.active_modifier_idx += 1
        self.report({'INFO'}, f"{mod} was moved from index {index} to {ob.active_modifier_idx}.")
        return{'FINISHED'}


class MODIFIER_OT_apply_modifier(Operator):
    bl_idname = 'hair_factory.mod_apply'
    bl_label = 'Apply Modifier'
    bl_description = "Only use if you are not using physics."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if not ob:
            return False
        count = len(ob.modifiers)
        return count > 0 and ob.active_modifier_idx < count
    
    def execute(self, context):
        ob = context.object
        if ob is None:
            self.report({'ERROR'}, "No Active Object")
            return{'CANCELLED'}
        modifiers = ob.modifiers
        index = ob.active_modifier_idx
        count = len(modifiers)
        if (count == 0):
            self.report({'ERROR'}, "No Modifiers Present")
            return{'CANCELLED'}
        elif (index >= count):
            self.report({'ERROR'}, "No modifiers Selected.")
            return{'CANCELLED'}
        else:
            try:
                mod = modifiers[index].name
                node_group = getattr(mod, 'node_group', None)
                object_.modifier_apply(modifier=mod)
                if index != 0:
                    ob.active_modifier_idx -= 1
                if context.preferences.addons[__package__].preferences.apply_mod_delete:
                    if node_group:
                        delete_full_node_tree(node_group)
            except Exception as ee:
                self.report({'ERROR'}, f"{ee}")
                return{'CANCELLED'}
        self.report({'INFO'}, f"{mod} was applied.")
        return{'FINISHED'}


class OBJECT_OT_add_hair_curve(Operator):
    bl_idname = 'hair_factory.add_hair_curve'
    bl_label = 'Add Hair Curve'
    bl_description = "Add Hair Curve to mesh."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if not ob:
            return False
        return ob.type == 'MESH'
    
    def execute(self, context):
        ob = context.object
        obj = bpy.data.objects
        scene = context.scene
        if ob is None:
            self.report({'ERROR'}, "No Active Object")
            return{'CANCELLED'}
        object_.curves_empty_hair_add()
        context.object.name = scene.new_hair_name
        context.object.data.name = context.object.name
        idx = next((i for i, o in enumerate(obj) if o == context.object))
        scene.active_object_idx = idx
        self.report({'INFO'}, f"Hair curve {context.object.name} added to {ob.name}.")
        return{'FINISHED'}


class OBJECT_UL_hair_curves_viewer(UIList):
    
    SHOW_CURVES = 1 << 0
    
    filter_curves: BoolProperty(
                    name="Show Hair Curves Only",
                    description="Show Hair Curves only in list.", 
                    default=False,
                    )
    filter_search: StringProperty(
                    name = "Search", 
                    options = {'TEXTEDIT_UPDATE'},
                    description = "Use text to narrow down search of objects. (Case Sensitive)",
                    )
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row()
            icon = Object.bl_rna.properties['type'].enum_items[item.type].icon
            row.prop(item, 'name', text="", emboss=False, icon_value=1, icon=icon)
            if hasattr(item, 'hide_select'):
                row.prop(item, 'hide_select', text="", emboss=False, icon_only=True)
            if hasattr(item, 'hide_viewport'):
                row.prop(item, 'hide_viewport', text="", emboss=False, icon_only=True)
            if hasattr(item, 'hide_render'):
                row.prop(item, 'hide_render', text="", emboss=False, icon_only=True)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)
    
    def draw_filter(self, context, layout):
        scene = context.scene
        row = layout.row()
        subrow = row.row(align=True)
        icon = 'PROP_ON' if self.filter_curves else 'PROP_OFF'
        subrow.prop(self, "filter_curves", text="", icon=icon)
        subrow.separator()
        subrow.separator()
        subrow.separator()
        subrow.separator()
        subrow.separator()
        subrow.separator()
        subrow.separator()
        subrow.separator()
        subrow.separator()
        subrow.prop(scene, "new_hair_name", text="")
        subrow.separator()
        subrow.operator('hair_factory.add_hair_curve', text="", icon='ADD')
        col = layout.column()
        crow = col.row()
        crow.prop(self, 'filter_search')
        crow.separator()
        crow.separator()
    
    def filter_items(self, context, data, propname):
        helper_funcs = UI_UL_list
        flt_flags = []
        flt_neworder = []
        items = getattr(data, propname)
        is_curves = {i: ob.type == 'CURVES' for i, ob in enumerate(bpy.data.objects)}
        
        if not flt_flags:
            flt_flags = [self.bitflag_filter_item] * len(items)
        
        for idx, item in enumerate(items):
            if not is_curves[idx] and char.find(item.name, self.filter_search).item() > -1:
                flt_flags[idx] |= self.SHOW_CURVES
                if self.filter_curves:
                    flt_flags[idx] &= ~self.bitflag_filter_item
            else:
                if not char.find(item.name, self.filter_search).item() > -1:
                    flt_flags[idx] &= ~self.bitflag_filter_item
        return flt_flags, flt_neworder


def has_special_node(tree, ntype):
    if hasattr(tree, 'nodes'):
        for node in tree.nodes:
            if node.type == ntype:
                yield True
            if node.type == 'GROUP':
                yield from has_special_node(node.node_tree, ntype)


def gui_items(self, context):
    ob = context.object
    if ob:
        try:
            for i in  [
                    ("MAIN", "Main", "Display the main panel."),
                    ("NODE", "Node Group", "Display the active node group."),
                ]:
                    yield i
            if ob.type == 'CURVES':
                yield ("MATERIAL", "Material", "Display the materials panel.")
            if ob.type == 'CURVES' or "PHY_HAIR" in dict(ob).keys():
                yield ("PHYSICS", "Physics", "Display the physics panel.")
            if hasattr(ob, 'modifiers'):
                modifier = ob.modifiers.active
                if hasattr(modifier, 'bakes'):
                    if len(modifier.bakes) > 0:
                        yield ("BAKE", "Bake", "Display the available bake data.")
                ndict = {
                    "CURVE_FLOAT": ("CURVE_FLOAT", "Float Curve", "Display node group float curves."),
                    "VALTORGB": ("VALTORGB", "Color Ramp", "Display node group color ramps."),
                    "CURVE_VEC": ("CURVE_VEC", "Vector Curve", "Display node group vector curves."),
                    "CURVE_RGB": ("CURVE_RGB", "RGB Curve", "Display node group rgb curves."),
                    "INPUT_COLOR": ("INPUT_COLOR", "Input Color", "Display node group input colors."),
                }
                if hasattr(modifier, 'node_group'):
                    for ntype in ['CURVE_FLOAT', 'VALTORGB', 'CURVE_VEC', 'CURVE_RGB', 'INPUT_COLOR']:
                        if any(has_special_node(modifier.node_group, ntype)):
                            yield ndict[ntype]
        except:
            pass


def mat_poll(self, mat):
    return isinstance(mat, Material)


classes = [
            OBJECT_OT_hf_set_mat,
            MODIFIER_OT_launch_add_mat,
            MODIFIER_OT_launch_add_mod,
            MODIFIER_OT_modifier_delete,
            MODIFIER_OT_modifier_up,
            MODIFIER_OT_modifier_down,
            MODIFIER_OT_apply_modifier,
            OBJECT_OT_add_hair_curve,
            HAIRFACTORY_OT_bake_node,
            HAIRFACTORY_OT_bake_delete,
            OBJECT_UL_hair_curves_viewer,
            MODIFIER_UL_modifier_stack_viewer,
            HAIRFACTORY_PT_main_panel,
            ]


def register():
    for cls in classes:
        register_class(cls)
    
    Object.active_modifier_idx = IntProperty(default=0, update=update_mod_idx)
    Scene.active_object_idx = IntProperty(default=0, update=update_obj_idx)
    Scene.hf_gui_type = EnumProperty(
        name = "GUI Type",
        description = "The type of gui to display.",
        items = gui_items,
    )
    Scene.hf_mat_socs = EnumProperty(
        name = "Material Sockets",
        description = "Available material sockets of active node group.",
        items = get_GN_material_sockets,
    )
    Scene.hf_ob_socs = EnumProperty(
        name = "Object Sockets",
        description = "Available object sockets of active node group.",
        items = get_GN_object_sockets,
    )
    Scene.hf_available_mats = PointerProperty(
        name = "Available Materials",
        description = "Available materials loaded in blend.",
        type = Material,
        poll = mat_poll,
    )
    Object.available_bake_nodes = EnumProperty(
        items = _available_bake_nodes,
        description="Select a bake node.",
    )
    Object.active_bake_node_mode = EnumProperty(
        items = [
            ("STILL", "STILL", "Bake a single frame."),
            ("ANIMATION", "ANIMATION", "Bake a frame range.")
        ],
        default = "STILL",
        update=update_active_bake_node_mode,
    )
    Object.active_bake_node_target = EnumProperty(
        items = [
            ("INHERIT", "INHERIT", "Inherit baked data"),
            ("PACKED", "PACKED", "Pack the baked data into the .blend file"),
            ("DISK", "DISK", "Store the baked data in a directory on disk."),
        ],
        default = "INHERIT",
    )
    Object.active_bake_modifier_target = EnumProperty(
        items = [
            ("PACKED", "PACKED", "Pack the baked data into the .blend file"),
            ("DISK", "DISK", "Store the baked data in a directory on disk."),
        ],
        default = "PACKED",
        update=update_active_bake_modifier_target,
    )
    Object.active_bake_node_destination = StringProperty(
        name="",
        default="",
        description="Location on disk where baked data is stored.",
        subtype="FILE_PATH",
        update=update_active_bake_node_destination,
    )
    Scene.new_hair_name = StringProperty(
        name="New Hair Name",
        default="Hair",
        description="Name for new hair objects.",
    )
    Scene.hf_special_node_search = StringProperty(
        name = "Search", 
        options = {'TEXTEDIT_UPDATE'},
        description = "Use text to narrow down search of nodes. (Case Sensitive)",
    )



def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
        
    del Object.active_modifier_idx
    del Scene.active_object_idx
    del Scene.hf_gui_type
    del Scene.hf_mat_socs
    del Scene.hf_available_mats
    del Object.available_bake_nodes
    del Object.active_bake_node_mode
    del Object.active_bake_node_target
    del Object.active_bake_modifier_target
    del Object.active_bake_node_destination
    del Scene.hf_special_node_search

