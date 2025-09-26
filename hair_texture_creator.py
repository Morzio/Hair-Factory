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
from bpy.ops import workspace
from bpy.types import Panel, Operator
from bpy.utils import register_class, unregister_class
from .load_util import get_assets_path
from .gui_util import delete_geo_node_modifier, material_gui, special_node_gui, node_gui, node_group_io

scene_curr = None
workspace_curr = None
scene_engine = None


def get_htc_path():
    file = get_assets_path().joinpath("HAIR_TEXTURE_CREATOR.blend")
    return str(file)


def load_hair_texture_creator():
    with bpy.data.libraries.load(get_htc_path()) as (data_from, data_to):
        data_to.scenes.append("HAIR_TEXTURE_CREATOR")
        data_to.workspaces.append("VIEWER")


def clean_scene():
    obj = bpy.data.objects
    for mat in obj['Hair_Creator_Curve'].data.materials:
        bpy.data.materials.remove(mat)
    for mod in obj['Hair_Creator_Curve'].modifiers:
        delete_geo_node_modifier(obj['Hair_Creator_Curve'], mod)
    bpy.data.hair_curves.remove(obj['Hair_Creator_Curve'].data)
    bpy.data.meshes.remove(obj['Hair_Creator_Cage'].data)
    bpy.data.cameras.remove(obj['Hair Camera'].data)
    bpy.data.node_groups.remove(bpy.data.node_groups['Color_Rotation_Control'])



class HAIRFACTORY_OT_load_hair_texture_creator(Operator):
    """
    """
    bl_idname = "hair_factory.load_htc"
    bl_label = "Load HAIR TEXTURE CREATOR Scene"
    bl_description = "Load the HAIR TEXTURE CREATOR Scene to Create Hair Alphas, Normals, and/or Textures for Hair Cards."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.name.split(".")[0] != "HAIR_TEXTURE_CREATOR" and 'HAIR_TEXTURE_CREATOR' not in [s.name for s in bpy.data.scenes]
    
    def execute(self, context):
        global scene_curr
        global workspace_curr
        global scene_engine
        scene_curr = context.scene
        workspace_curr = context.workspace
        scene_engine = context.scene.render.engine
        try:
            if 'HAIR_TEXTURE_CREATOR' not in [s.name for s in bpy.data.scenes]:
                load_hair_texture_creator()
            context.scene.render.engine = 'CYCLES'
            context.window.scene = bpy.data.scenes['HAIR_TEXTURE_CREATOR']
            context.window.workspace = bpy.data.workspaces['VIEWER']
            self.report({'INFO'}, "HAIR_TEXTURE_CREATOR loaded.")
            return{'FINISHED'}
        except Exception as htc_error:
            scene_curr = None
            workspace_curr = None
            scene_engine = None
            self.report({'ERROR'}, f"HAIR_TEXTURE_CREATOR load error: {htc_error}")
            return{'CANCELLED'}


class HAIRFACTORY_OT_reset_scene(Operator):
    """
    """
    bl_idname = "hair_factory.reset_scene"
    bl_label = "Reset Scene"
    bl_description = "Reset to the previous Scene and Delete the HAIR TEXTURE CREATOR Scene."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.name.split(".")[0] == "HAIR_TEXTURE_CREATOR"
    
    def execute(self, context):
        global scene_curr
        global workspace_curr
        global scene_engine
        if not scene_curr and not workspace_curr:
            self.report({'ERROR'}, "Nothing to Reset.")
            return{'CANCELLED'}
        if scene_curr:
            context.window.scene = scene_curr
            scene_curr = None
        if workspace_curr:
            context.window.workspace = workspace_curr
            workspace_curr = None
        if scene_engine:
            context.scene.render.engine = scene_engine
            scene_engine = None
        clean_scene()
        bpy.data.scenes.remove(bpy.data.scenes['HAIR_TEXTURE_CREATOR'])
        with bpy.context.temp_override(workspace=bpy.data.workspaces['VIEWER']):
            workspace.delete()
        self.report({'INFO'}, f"{context.scene.name} Reset.")
        return{'FINISHED'}


class HAIRFACTORY_PT_texture_creator_panel(Panel):
    """Hair Texture Creator Panel"""
    bl_label = "Hair Texture Creator Panel"
    bl_idname = "HAIRFACTORY_PT_texture_creator_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Morzio Hair Factory"

    @classmethod
    def poll(cls, context):
        return context.scene.name.split(".")[0] == "HAIR_TEXTURE_CREATOR" and context.area.type == 'VIEW_3D'
    
    def draw(self, context):
        layout = self.layout
        title_box = layout.box()
        cam_box = layout.box()
        hair_box = layout.box()
        curve_box = layout.box()
        mat_box = layout.box()
        scene = context.scene
        cscene = scene.cycles
        rd = context.scene.render
        image_settings = rd.image_settings
        trow = title_box.row()
        trow.label(text="HAIR_TEXTURE_CREATOR")
        trow.operator('render.render', text="", icon='RENDER_STILL').use_viewport = True
        trow.separator()
        trow.operator(HAIRFACTORY_OT_reset_scene.bl_idname, text="", icon='CURVES')
        layout.use_property_split = True
        layout.use_property_decorate = False
        # Camera
        header, panel = cam_box.panel("Camera", default_closed=False)
        header.label(text="CAMERA SETTINGS")
        if panel:
            heading = cam_box.row(heading="Noise Threshold")
            row = heading.row(align=True)
            row.prop(cscene, "use_adaptive_sampling", text="")
            sub = row.row()
            sub.active = cscene.use_adaptive_sampling
            sub.prop(cscene, "adaptive_threshold", text="")
            col = panel.column(align=True)
            col.prop(cscene, "device")
            if cscene.use_adaptive_sampling:
                col.prop(cscene, "samples", text="Max Samples")
                col.prop(cscene, "adaptive_min_samples", text="Min Samples")
            else:
                col.prop(cscene, "samples", text="Samples")
            col.prop(cscene, "time_limit")
            col = cam_box.column(align=True)
            col.prop(rd, "resolution_x", text="Resolution X")
            col.prop(rd, "resolution_y", text="Y")
            col.prop(rd, "resolution_percentage", text="%")
            col = cam_box.column(align=True)
            col.prop(rd, "pixel_aspect_x", text="Aspect X")
            col.prop(rd, "pixel_aspect_y", text="Y")
            col = cam_box.column(align=True)
            col.template_image_settings(image_settings, color_management=False)
            col = cam_box.column(align=True)
            col.prop(scene.camera, "location")
        # Hair
        hheader, hpanel = hair_box.panel("Hair", default_closed=False)
        hheader.label(text="HAIR SETTINGS")
        if hpanel:
            try:
                modi = bpy.data.objects["Hair_Creator_Curve"].modifiers.get("HAIR_CREATOR")
                if modi:
                    node_gui(modi.node_group.interface.items_tree, modi, hpanel)
                    node_group_io(modi, hpanel)
            except Exception as e:
                print(e)
                self.report({'ERROR'}, f"[HAIR SETTINGS] {e}")
        # Curves
        cheader, cpanel = curve_box.panel("Curves", default_closed=False)
        cheader.label(text="SHAPE CURVES")
        if cpanel:
            try:
                nodes = bpy.data.objects["Hair_Creator_Curve"].modifiers["HAIR_CREATOR"].node_group.nodes
                special_node_gui(nodes, cpanel, ntype='CURVE_FLOAT')
            except Exception as e:
                print(e)
                self.report({'ERROR'}, f"[SHAPE CURVES] {e}")
        # Curves
        mheader, mpanel = mat_box.panel("Material", default_closed=False)
        mheader.label(text="MATERIAL SETTINGS")
        if mpanel:
            try:
                material_gui(self, context, bpy.data.objects["Hair_Creator_Curve"].modifiers["HAIR_CREATOR"], mpanel)
            except Exception as e:
                print(e)
                self.report({'ERROR'}, f"[MATERIAL SETTINGS] {e}")


classes = [
    HAIRFACTORY_OT_load_hair_texture_creator,
    HAIRFACTORY_OT_reset_scene,
    HAIRFACTORY_PT_texture_creator_panel,
]


def register():
    for cls in classes:
        register_class(cls)


def unregister():
    for cls in reversed(classes):
        unregister_class(cls)

