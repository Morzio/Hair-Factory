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

from .load_util import register as lu_reg, unregister as lu_unreg, create_filler_zip, append_node_file_to_zip, append_material_file_to_zip, is_file_suspicious
from .bake_materials_util import register as bmu_reg, unregister as bmu_unreg
from .hair_texture_creator import register as htc_reg, unregister as htc_unreg
from .physics_util import register as phy_reg, unregister as phy_unreg
from .preset_util import register as pre_reg, unregister as pre_unreg, create_preset_zip, read_json, modify_in_zip, import_func_dict
from .gui_util import register as gui_reg, unregister as gui_unreg


def init_preset(preset_path):
    if not preset_path.joinpath("Presets.zip").is_file():
        create_preset_zip(preset_path.joinpath("Presets.zip"))
    if not preset_path.joinpath("User_Materials.zip").is_file():
        create_filler_zip(preset_path.joinpath("User_Materials.zip"))
    if not preset_path.joinpath("User_Geo_Nodes.zip").is_file():
        create_filler_zip(preset_path.joinpath("User_Geo_Nodes.zip"))


def remove_preset(preset_path):
    try:
        preset_path.joinpath("Presets.zip").unlink()
        preset_path.joinpath("User_Materials.zip").unlink()
        preset_path.joinpath("User_Geo_Nodes.zip").unlink()
    except:
        pass


def do_presets_exists(preset_path):
    return all(
        [
            preset_path.joinpath("Presets.zip").is_file(),
            preset_path.joinpath("User_Materials.zip").is_file(),
            preset_path.joinpath("User_Geo_Nodes.zip").is_file(),
        ]
    )


def import_geo_node_file(file, preset_path):
    if do_presets_exists(preset_path):
        append_node_file_to_zip(file, preset_path.joinpath("User_Geo_Nodes.zip"))


def import_mat_file(file, preset_path):
    if do_presets_exists(preset_path):
        append_material_file_to_zip(file, preset_path.joinpath("User_Materials.zip"))


def import_preset_settings_file(zip_file, data_file):
    check_ = is_file_suspicious(data_file)
    preset_file = 'Presets.hfdb'
    data = read_json(data_file)
    ftype = data['META']['TYPE']
    if ftype not in import_func_dict().keys():
        raise ValueError("Preset type not found!")
    func = import_func_dict()[ftype]
    preset_saved, pname = modify_in_zip(zip_file, preset_file, func, data['DATA'])
    return preset_saved, pname, ftype



def hf_register():
    lu_reg()
    bmu_reg()
    htc_reg()
    phy_reg()
    pre_reg()
    gui_reg()


def hf_unregister():
    gui_unreg()
    lu_unreg()
    bmu_unreg()
    htc_unreg()
    phy_unreg()
    pre_unreg()
