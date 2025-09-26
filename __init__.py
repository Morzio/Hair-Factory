bl_info = {
    "name": "Morzio Hair Factory",
    "Author": "Demingo Hill (Noizirom)",
    "version": (0,1,0),
    "blender": (4, 4, 0),
    "location": "View3D > Sidebar > Hair Factory",
    "description": "A tool to aid in the creation of complex hair assets.",
    "warning": "",
    "doc_url": "",
    "tracker_url": "",
    "category": "3D View",
}

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
from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, BoolProperty
from bpy.utils import script_path_user, register_class, unregister_class
from pathlib import Path
from json import dumps, loads
from platform import system, architecture
from os import access, F_OK, R_OK, W_OK
from .pip_utils import requirements_not_installed_dict, pip_install_wheel_from, pip_install_wheel_from_requirements, pip_uninstall, read_requirements
from .preset_util import load_preset_mat_colors, modify_in_zip, read_json
from .hair_factory_utils import hf_register, hf_unregister, init_preset, remove_preset, do_presets_exists, import_geo_node_file, import_mat_file, import_preset_settings_file


main_directory = Path(script_path_user()).joinpath("addons").joinpath(__package__).resolve()
req_pack = list(read_requirements(main_directory))


def _is_file_accessible(file_path):
    return [access(file_path, F_OK), access(file_path, R_OK), access(file_path, W_OK)]


def _is_file_accessible_message(data):
    msg = "File Path {} {}. "
    if not all(data):
        return [msg.format('is not', 'accessible')]
    exists_ = (msg.format('does', 'exist') if data[0] else msg.format('does not', 'exist'))
    readable_ = (msg.format('is', 'readable') if data[1] else msg.format('is not', 'readable'))
    writeable_ = (msg.format('is', 'writeable') if data[2] else msg.format('is not', 'writeable'))
    return [exists_, readable_, writeable_]


def is_file_accessible(file_path):
    acc = _is_file_accessible(file_path)
    return {'access': acc, 'message': "".join(_ for _ in _is_file_accessible_message(acc))}


class HAIRFACTORY_PT_AddonPreferences(AddonPreferences):
    bl_idname = __package__
    
    preset_path: StringProperty(
        name="Preset Path",
        subtype='DIR_PATH',
        default=str(Path.home().joinpath("Documents")),
    )
    
    is_preset_path_set: BoolProperty(
        name="Is Preset Path Set",
        default=False,
    )

    pip: StringProperty(
        name="Pip",
        default='',
    )

    pip_installed: BoolProperty(
        name="Able to Install",
        default=False,
    )

    geo_node_file: StringProperty(
        name="Geo Node File",
        description = "Select a geometry node file to import.",
        subtype='FILE_PATH',
    )

    mat_file: StringProperty(
        name="Material File",
        description = "Select a material file to import.",
        subtype='FILE_PATH',
    )

    preset_data_file: StringProperty(
        name="Preset Data File",
        description = "Select a preset data file to import.",
        subtype='FILE_PATH',
    )

    apply_mod_delete: BoolProperty(
        name="Delete Node Group on Apply",
        description = "Delete geometry node group on apply modifier.",
        default=True,
    )

    set_surface_ob: BoolProperty(
        name="Automatic Surface Object",
        description = "Automatically set geometry node Surface socket if available.",
        default=True,
    )

    delete_node_group: BoolProperty(
        name="Automatic Delete Node Group",
        description = "Automatically delete geometry node group on removal if available.",
        default=True,
    )

    delete_presets: BoolProperty(
        name="Delete Presets Option",
        description = "Choose to have the option to delete all presets from this panel.",
        default=False,
    )
    
    
    def draw(self, context):
        global req_pack
        layout = self.layout
        pref_box = layout.box()
        pb_row = pref_box.row()
        pb_row.label(text="[Morzio Hair Factory Preferences]")
        # Options
        opt_box = pref_box.box()
        ocol = opt_box.column()
        ocol.prop(self, 'set_surface_ob')
        ocol.prop(self, 'delete_node_group')
        ocol.prop(self, 'apply_mod_delete')
        ocol.prop(self, 'delete_presets')
        # Presets
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            pref_box.label(text=f"Setup Preset directory and files.")
            pip_msg = "Required packages:" + "".join(f" {p}" for p in req_pack)
            pref_box.label(text=pip_msg)
            pref_box.prop(self, "preset_path")
        bt_row = pref_box.row()
        bt_row.operator(OBJECT_OT_hf_add_presets.bl_idname)
        if context.preferences.addons[__package__].preferences.delete_presets:
            bt_row.operator(OBJECT_OT_hf_delete_presets.bl_idname, text="", icon='X')
        pref_box.separator()
        # Imports
        if context.preferences.addons[__package__].preferences.is_preset_path_set:
            iheader, ipanel = layout.panel("HF_IMPORTS", default_closed=True)
            iheader.label(text=f"Import Options")
            if ipanel:
                io_box = ipanel.box()
                io_box.separator()
                gn_row = io_box.row()
                gn_row.prop(self, 'geo_node_file')
                gn_row.separator()
                gn_row.operator(OBJECT_OT_hf_import_geo_node_file.bl_idname, text="", icon='TEXT')
                io_box.separator()
                mt_row = io_box.row()
                mt_row.prop(self, 'mat_file')
                mt_row.separator()
                mt_row.operator(OBJECT_OT_hf_import_mat_file.bl_idname, text="", icon='TEXT')
                io_box.separator()
                ps_row = io_box.row()
                ps_row.prop(self, 'preset_data_file')
                ps_row.separator()
                ps_row.operator(OBJECT_OT_hf_import_preset_data_file.bl_idname, text="", icon='TEXT')
                io_box.separator()


class OBJECT_OT_hf_add_presets(Operator):
    bl_idname = "hair_factory.hf_add_presets"
    bl_label = "Set Up Preset"
    bl_description = "Set up Preset files and directory and pip install packages if not installed."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        global req_pack
        if not context.preferences.addons[__package__].preferences.pip_installed and any(requirements_not_installed_dict(main_directory)[p] for p in req_pack):
            return False
        return not context.preferences.addons[__package__].preferences.is_preset_path_set
    
    def execute(self, context):
        preferences = context.preferences
        addon_prefs = preferences.addons[__package__].preferences
        preset_path = Path(addon_prefs.preset_path).resolve()
        
        i_dict = {True: "was installed.", False: "is already installed."}
        info = "".join(f"{k} {i_dict[v]}" for k,v in loads(addon_prefs.pip).items())
        
        accessible_ = is_file_accessible(str(preset_path))
        if not all(accessible_['access']):
            self.report({'ERROR'}, accessible_['message'])
            return {'CANCELLED'}
        try:
            init_preset(preset_path)
            addon_prefs.is_preset_path_set = True
            data_dict = read_json(str(main_directory.joinpath("Preset_Hair_Colors.json")))
            modify_in_zip(preset_path.joinpath("Presets.zip"), 'Presets.hfdb', load_preset_mat_colors, data_dict)
            self.report({'INFO'}, info)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"{e}")
            return {'CANCELLED'}


class OBJECT_OT_hf_delete_presets(Operator):
    bl_idname = "hair_factory.hf_delete_presets"
    bl_label = "Delete Preset"
    bl_description = "Delete Preset files if they exist."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set and do_presets_exists(Path(context.preferences.addons[__package__].preferences.preset_path).resolve())
    
    def execute(self, context):
        try:
            pp = Path(context.preferences.addons[__package__].preferences.preset_path).resolve()
            remove_preset(pp)
            self.report({'INFO'}, f"Preset files removed from ({pp})")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"{e}")
            return {'CANCELLED'}


class OBJECT_OT_hf_import_geo_node_file(Operator):
    bl_idname = "hair_factory.hf_import_geo_node_file"
    bl_label = "Import Geometry Node File"
    bl_description = "Import geometry node file into preset zip."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set and do_presets_exists(Path(context.preferences.addons[__package__].preferences.preset_path).resolve())
    
    def execute(self, context):
        try:
            pp = Path(context.preferences.addons[__package__].preferences.preset_path).resolve()
            file = Path(context.preferences.addons[__package__].preferences.geo_node_file).resolve()
            if not file.is_file() or not str(file.name).endswith(".py"):
                context.preferences.addons[__package__].preferences.geo_node_file = ""
                self.report({'ERROR'}, f"Not a valid file: {file}")
                return {'CANCELLED'}
            import_geo_node_file(file, pp)
            context.preferences.addons[__package__].preferences.geo_node_file = ""
            self.report({'INFO'}, f"{file.name} was added to presets.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"{e}")
            return {'CANCELLED'}


class OBJECT_OT_hf_import_mat_file(Operator):
    bl_idname = "hair_factory.hf_import_mat_file"
    bl_label = "Import Material File"
    bl_description = "Import material file into preset zip."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set and do_presets_exists(Path(context.preferences.addons[__package__].preferences.preset_path).resolve())
    
    def execute(self, context):
        try:
            pp = Path(context.preferences.addons[__package__].preferences.preset_path).resolve()
            file = Path(context.preferences.addons[__package__].preferences.mat_file).resolve()
            if not file.is_file() or not str(file.name).endswith(".py"):
                context.preferences.addons[__package__].preferences.mat_file = ""
                self.report({'ERROR'}, f"Not a valid file: {file}")
                return {'CANCELLED'}
            import_mat_file(file, pp)
            context.preferences.addons[__package__].preferences.mat_file = ""
            self.report({'INFO'}, f"{file.name} was added to presets.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"{e}")
            return {'CANCELLED'}


class OBJECT_OT_hf_import_preset_data_file(Operator):
    bl_idname = "hair_factory.hf_import_preset_data_file"
    bl_label = "Import Preset Data File"
    bl_description = "Import preset data file into preset zip."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set and do_presets_exists(Path(context.preferences.addons[__package__].preferences.preset_path).resolve())
    
    def execute(self, context):
        try:
            pp = Path(context.preferences.addons[__package__].preferences.preset_path).resolve()
            file = Path(context.preferences.addons[__package__].preferences.preset_data_file).resolve()
            if not file.is_file() or not str(file.name).endswith(".json"):
                context.preferences.addons[__package__].preferences.preset_data_file = ""
                self.report({'ERROR'}, f"Not a valid file: {file}")
                return {'CANCELLED'}
            preset_saved, pname, ftype = import_preset_settings_file(pp.joinpath("Presets.zip"), file)
            context.preferences.addons[__package__].preferences.preset_data_file = ""
            if isinstance(preset_saved, list):
                for p in preset_saved:
                    self.report({'INFO'}, f"{p} from {file.name} was added to {ftype.title()} presets.")
                for p in pname:
                    self.report({'INFO'}, f"Preset from {file.name} was already saved as {p} in {ftype.title()} presets.")
            else:
                if preset_saved:
                    self.report({'INFO'}, f"{pname} from {file.name} was added to {ftype.title()} presets.")
                else:
                    self.report({'INFO'}, f"Preset from {file.name} was already saved as {pname} in {ftype.title()} presets.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"{e}")
            return {'CANCELLED'}


classes = [
    HAIRFACTORY_PT_AddonPreferences,
    OBJECT_OT_hf_add_presets,
    OBJECT_OT_hf_delete_presets,
    OBJECT_OT_hf_import_geo_node_file,
    OBJECT_OT_hf_import_mat_file,
    OBJECT_OT_hf_import_preset_data_file,
]


def register_all_classes():
    for cls in classes:
        register_class(cls)


def unregister_all_classes():
    for cls in reversed(classes):
        unregister_class(cls)



def register():
    hf_register()
    register_all_classes()

    reqs = requirements_not_installed_dict(main_directory)
    # Pip
    bpy.context.preferences.addons[__package__].preferences.pip = dumps(reqs)
    try:
        if architecture()[0] == '64bit':
            if all(list(reqs.values())):
                pip_install_wheel_from_requirements(main_directory.joinpath("Wheels").joinpath(system()), main_directory)
            else:
                for k, v in reqs.items():
                    if v:
                        pip_install_wheel_from(k, main_directory.joinpath("Wheels").joinpath(system()))
            bpy.context.preferences.addons[__package__].preferences.pip_installed = True
    except:
        pass


def unregister():
    # Pip
    try:
        if bpy.context.preferences.addons[__package__].preferences.pip_installed:
            for k, v in loads(bpy.context.preferences.addons[__package__].preferences.pip).items():
                if v:
                    pip_uninstall(k)
    except:
        pass

    hf_unregister()
    unregister_all_classes()


if __name__ == '__main__':
    register()

