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
from bpy.ops import node as node_
from bpy.types import Operator, Scene, GeometryNodeTree, Material, Menu, NODE_MT_add
from bpy.props import StringProperty, EnumProperty
from bpy.utils import script_paths, script_path_user, register_class, unregister_class
from zipfile import ZipFile, is_zipfile, ZIP_LZMA
from pathlib import Path
from re import findall
from numpy import array, where, char, isin, r_
from h5py import File
from .preset_util import get_from_zip


### PATHS

def get_assets_path():
    return Path(script_path_user()).joinpath("addons").joinpath(__package__).joinpath("Assets")


def get_preset_path():
    try:
        return Path(bpy.context.preferences.addons[__package__].preferences.preset_path)
    except:
        pass


def get_hf_accessories_zip():
    return get_assets_path().joinpath("ACCESSORIES.zip")


def get_hf_node_group_zip():
    return get_assets_path().joinpath("Geo_Nodes.zip")


def get_user_node_group_zip():
    return get_preset_path().joinpath("User_Geo_Nodes.zip")


def get_hf_mat_zip():
    return get_assets_path().joinpath("Materials.zip")


def get_user_mat_zip():
    return get_preset_path().joinpath("User_Materials.zip")


def get_procedural_hair_node_assets_file():
    script_path = Path(script_paths()[0])
    GN_path = script_path.parent.joinpath("datafiles").joinpath("assets").joinpath("geometry_nodes")
    GN_file = GN_path.joinpath("procedural_hair_node_assets.blend")
    return str(GN_file)


### ERRORS

class SuspectFileError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


### SETUP

def concat_gen(*gens):
    for gen in gens:
        yield from gen


def zip_gen(*gens):
    return zip(*gens)


def get_zip_file_list(zip_file):
    with ZipFile(zip_file, 'r') as zf:
        name_list = (f for f in zf.namelist())
    return name_list


def zip_from_folder(src_dir_path, dest_dir_path):
    name = Path(src_dir_path).stem
    zip_name = f"{name}.zip"
    zip_file = Path(dest_dir_path).joinpath(zip_name)
    files_list = Path(src_dir_path).rglob("*")
    with ZipFile(file=zip_file, mode='w', compression=ZIP_LZMA, compresslevel=9) as zf:
        for file in files_list:
            zf.write(filename=file, arcname=file.name)


def zip_append(zip_file, file, arcname=None):
    with ZipFile(zip_file, 'a') as zf:
        name = (Path(file).name if isinstance(arcname, type(None)) else arcname)
        zf.write(file, arcname=name)


def read_from_zip(zip_file, file_name):
    with ZipFile(zip_file, 'r') as zf:
        with zf.open(zf.namelist()[where(char.find(zf.namelist(), file_name) > -1)[0][0]]) as f:
            data = f.read()
    return data


def create_filler_zip(zip_file):
    file_name = 'USER.txt'
    file = zip_file.parent.joinpath(file_name)
    with ZipFile(zip_file, 'w', compression=ZIP_LZMA, compresslevel=9, allowZip64=True) as zf:
        zf.writestr(file_name, "")


def read_file(file):
    with open(file, 'r') as f:
        data = f.read()
    return data


def write_file(file, data):
    with open(file, 'w') as f:
        f.write(data)


def inject_detect(data):
    s = findall(r'\b(?:os|sys|subprocess|asyncio|pathlib|marshal|ast|cmd|ord|chr)\b', data)
    f = findall(r' eval\(| var\(| exec\(| ord\(| chr\(| -c ', data)
    i = findall(r' os\.| sys\.| subprocess\.| asyncio\.| pathlib\.| marshal\.| ast\.| cmd\.', data)
    check_ = [len(s) > 0, len(f) > 0, len(i) > 0]
    if any(check_):
        print(f"[SUSPICIOUS]: {[_ for idx, _ in enumerate([s, f, i]) if check_[idx]]}")
        return True
    return False


def is_file_suspicious(file):
    data = read_file(file)
    check_ = inject_detect(data)
    if check_:
        raise SuspectFileError(f"Suspect File!!! {Path(file.name)}")
    return check_


### NODE

def format_node_file(data):
    splitlines = data.splitlines()
    # Locate POI
    find_defs = where(char.find(splitlines, "():") > -1)[0]
    first_def = find_defs[0]
    find_last_func = splitlines[find_defs[-1]].replace("def ", "").lstrip().replace(":", "")
    last_call = where(char.find(splitlines, find_last_func) > -1)[0][-1]
    last_return = where(char.find(splitlines, "return") > -1)[0][-1]
    # Convert file to function
    splitlines[first_def - 2] = "\ndef node():"
    splitlines[last_call] = "\n"
    splitlines[last_return + 1] = f"return {find_last_func}\n"
    for idx, line in enumerate(splitlines):
        if idx >= first_def - 1:
            splitlines[idx] = f"\t{line}\n"
        else:
            splitlines[idx] = f"{line}\n"
    node = "".join([line for line in splitlines])
    return node


def modify_node_file_data(file, zip_file):
    raw_data = read_file(file)
    if inject_detect(raw_data):
        raise SuspectFileError(f"Suspect File!!! {Path(file.name)}")
    data = format_node_file(raw_data)
    temp_file = Path("temp.py")
    temp_file.touch(exist_ok=True)
    write_file(temp_file, data)
    zip_file.write(filename=temp_file, arcname=file.name)
    temp_file.unlink()


def zip_node_files(src_dir_path, dest_dir_path):
    name = Path(src_dir_path).stem
    zip_name = f"{name}.zip"
    zip_file = Path(dest_dir_path).joinpath(zip_name)
    files_list = Path(src_dir_path).rglob("*py")
    with ZipFile(file=zip_file, mode='w', compression=ZIP_LZMA, compresslevel=9) as zf:
        for file in files_list:
            modify_node_file_data(file, zf)


def append_node_file_to_zip(src_file, dest_dir_path):
    if not is_zipfile(dest_dir_path):
        raise ValueError("Destination file is not a .zip file!")
    src_file = Path(src_file)
    if f"{str(src_file.stem).upper()}.py" in (Path(file).name for file in get_zip_file_list(dest_dir_path)):
        raise FileExistsError("File already exists!")
    else:
        file_data = format_node_file(read_file(src_file))
        if inject_detect(file_data):
            raise SuspectFileError(f"Suspect File!!! {src_file.name}")
        with ZipFile(file=dest_dir_path, mode='a', compression=ZIP_LZMA, compresslevel=9) as zf:
            zf.writestr(f"{str(src_file.stem).upper()}.py", file_data)


def node_func(dir_path, file, read_raw=False):
    if is_zipfile(dir_path):
        file_data = read_from_zip(dir_path, file).decode('utf-8')
    else:
        file_data = read_file(Path(dir_path).joinpath(file))
        if read_raw:
            file_data = format_node_file(file_data)
        if inject_detect(file_data):
            raise SuspectFileError(f"Suspect File!!! {Path(file.name)}")
    file_dict = dict()
    exec(file_data, file_dict)
    return file_dict['node']()


### MATERIAL

def format_material_file(data):
    splitlines = data.splitlines()
    # Locate POI
    mat_init = where(char.find(splitlines, "mat = bpy.data.materials.new") > -1)[0][0]
    use_nodes = where(char.find(splitlines, "mat.use_nodes = True") > -1)[0][0]
    find_defs = where(char.find(splitlines, "def ") > -1)[0]
    first_def = find_defs[0]
    find_last_func = splitlines[find_defs[-1]].replace("def ", "").lstrip().replace(":", "")
    last_call = where(char.find(splitlines, find_last_func) > -1)[0][-1]
    last_return = where(char.find(splitlines, "return") > -1)[0][-1]
    # Convert file to function
    splitlines[first_def - 2] = "\ndef node(mat):"
    splitlines[last_call] = "\n"
    splitlines[last_return + 1] = f"return {find_last_func}\n"
    for idx, line in enumerate(splitlines):
        if idx >= first_def - 1:
            splitlines[idx] = f"\t{line}\n"
        else:
            splitlines[idx] = f"{line}\n"
    splitlines[mat_init] = "\n"
    if use_nodes != first_def - 2:
        splitlines[use_nodes] = "\n"
    node = ""
    for line in splitlines:
        node = node + line
    return node


def modify_material_file_data(file, zip_file):
    raw_data = read_file(file)
    if inject_detect(raw_data):
        raise SuspectFileError(f"Suspect File!!! {Path(file.name)}")
    data = format_material_file(raw_data)
    temp_file = Path("temp.py")
    temp_file.touch(exist_ok=True)
    write_file(temp_file, data)
    zip_file.write(filename=temp_file, arcname=file.name)
    temp_file.unlink()


def zip_material_files(src_dir_path, dest_dir_path):
    name = Path(src_dir_path).stem
    zip_name = f"{name}.zip"
    zip_file = Path(dest_dir_path).joinpath(zip_name)
    files_list = Path(src_dir_path).rglob("*py")
    with ZipFile(file=zip_file, mode='w', compression=ZIP_LZMA, compresslevel=9) as zf:
        for file in files_list:
            modify_material_file_data(file, zf)


def append_material_file_to_zip(src_file, dest_dir_path):
    if not is_zipfile(dest_dir_path):
        raise ValueError("Destination file is not a .zip file!")
    src_file = Path(src_file)
    if f"{str(src_file.stem).upper()}.py" in (Path(file).name for file in get_zip_file_list(dest_dir_path)):
        raise FileExistsError("File already exists!")
    else:
        file_data = format_material_file(read_file(src_file))
        if inject_detect(file_data):
            raise SuspectFileError(f"Suspect File!!! {src_file.name}")
        with ZipFile(file=dest_dir_path, mode='a', compression=ZIP_LZMA, compresslevel=9) as zf:
            zf.writestr(f"{str(src_file.stem).upper()}.py", file_data)


def material_func(dir_path, file, mat, read_raw=False):
    if is_zipfile(dir_path):
        file_data = read_from_zip(dir_path, file).decode('utf-8')
    else:
        file_data = read_file(Path(dir_path).joinpath(file))
        if read_raw:
            file_data = format_material_file(file_data)
        if inject_detect(file_data):
            raise SuspectFileError(f"Suspect File!!! {Path(file.name)}")
    file_dict = dict()
    exec(file_data, file_dict)
    return file_dict['node'](mat)


### DATA

def get_phna_names(gn_file=None):
    try:
        if gn_file == None:
            gn_file = get_procedural_hair_node_assets_file()
        with bpy.data.libraries.load(str(gn_file)) as (data_from, data_to):
            data = (n for n in data_from.node_groups)
        return data
    except Exception as phna_error:
        print(f"Error in loading procedural_hair_node_assets: {phna_error}")
        return []


def load_procedural_hair_node(ob, name, gn_file=None):
    try:
        if gn_file == None:
            gn_file = get_procedural_hair_node_assets_file()
        with bpy.data.libraries.load(str(gn_file)) as (data_from, data_to):
            prev = r_[[n.name for n in bpy.data.node_groups]]
            data_to.node_groups = [name]
        new = r_[[n.name for n in bpy.data.node_groups]]
        ng_new = new[isin(new, prev, invert=True)]
        ng_name = ng_new[where(char.find(ng_new, name) > -1)[0][0]]
        node_group = bpy.data.node_groups[ng_name]
        modifier = ob.modifiers.new(node_group.name, 'NODES')
        modifier.node_group = node_group
        return modifier
    except Exception as phna_error:
        print(f"Error in loading {name} from procedural_hair_node_assets: {phna_error}")


def get_phna_nodes():
    try:
        return ((f"{n}|{'BLENDER'}", n, '') for n in get_phna_names() if char.find(n, bpy.context.scene.hf_mod_search).item() > -1)
    except:
        return []


def get_hf_node_enum(zip_file, user_='HAIR_FACTORY'):
    with ZipFile(zip_file, 'r') as zf:
        return ((f"{file[:-3]}|{user_}", file[:-3], '') for file in zf.namelist() if (file[-3:] == '.py') and (char.find(file[:-3], bpy.context.scene.hf_mod_search).item() > -1))


def get_hf_mat_enum(zip_file, user_='HAIR_FACTORY'):
    with ZipFile(zip_file, 'r') as zf:
        return ((f"{file[:-3]}|{user_}", file[:-3], '') for file in zf.namelist() if (file[-3:] == '.py') and (char.find(file[:-3], bpy.context.scene.hf_mat_search).item() > -1))


def get_hair_factory_nodes():
    try:
        return get_hf_node_enum(get_hf_node_group_zip(), user_='HAIR_FACTORY')
    except:
        return []


def get_user_nodes():
    try:
        return get_hf_node_enum(get_user_node_group_zip(), user_='USER')
    except:
        return []


def get_all_nodes():
    try:
        return concat_gen(get_phna_nodes(), get_hair_factory_nodes(), get_user_nodes())
    except:
        return concat_gen(get_phna_nodes(), get_hair_factory_nodes())


def get_hair_factory_mats():
    try:
        return get_hf_mat_enum(get_hf_mat_zip(), user_='HAIR_FACTORY')
    except:
        return []


def get_user_mats():
    try:
        return get_hf_mat_enum(get_user_mat_zip(), user_='USER')
    except:
        return []


def get_all_mats():
    try:
        return concat_gen(get_hair_factory_mats(), get_user_mats())
    except:
        return get_hair_factory_mats()


def is_name_in(name, source):
    return name.split(".")[0] in (n[0].split("|")[0] for n in source)


def get_node_group_user(name):
    if is_name_in(name, get_hair_factory_nodes()):
        return 'HAIR_FACTORY'
    elif is_name_in(name, get_phna_nodes()):
        return 'BLENDER'
    elif is_name_in(name, get_user_nodes()):
        return 'USER'
    else:
        raise ValueError(f'Name: {name} not found!')
        return


def get_mat_user(name):
    if is_name_in(name, get_hair_factory_mats()):
        return 'HAIR_FACTORY'
    elif is_name_in(name, get_user_mats()):
        return 'USER'
    else:
        raise ValueError(f'Name: {name} not found!')
        return


def mod_load_items(self, context):
    scene = context.scene
    item = scene.hf_mod_source
    ng_list = []
    if item == 'ALL':
        ng_list = get_all_nodes()
    if item == 'BLENDER':
        ng_list = get_phna_nodes()
    if item == 'HAIR_FACTORY':
        ng_list = get_hair_factory_nodes()
    if item == 'USER':
        ng_list = get_user_nodes()
    return [("None", "None", "")] + list(ng_list)


def mat_load_items(self, context):
    scene = context.scene
    item = scene.hf_mat_source
    mat_list = []
    if item == 'ALL':
        mat_list = get_all_mats()
    if item == 'HAIR_FACTORY':
        mat_list = get_hair_factory_mats()
    if item == 'USER':
        mat_list = get_user_mats()
    return [("None", "None", "")] + list(mat_list)


def get_modifier_socket_type_by_name(modifier, name):
    if getattr(modifier, 'node_group', None):
        ng = modifier.node_group
        if getattr(ng, 'interface'):
            itree = ng.interface.items_tree
            if hasattr(itree[name], 'socket_type'):
                return itree[name].socket_type
    return


def get_modifier_identifier_by_name(modifier, name):
    if getattr(modifier, 'node_group', None):
        ng = modifier.node_group
        if getattr(ng, 'interface'):
            itree = ng.interface.items_tree
            if name in itree.keys():
                return itree[name].identifier
    return


def get_modifier_socket_by_name(modifier, name):
    socket = get_modifier_identifier_by_name(modifier, name)
    if socket:
        return modifier[socket]
    return


def set_modifier_socket_by_name(modifier, name, data):
    socket = get_modifier_identifier_by_name(modifier, name)
    if socket:
        try:
            modifier[socket] = data
        except:
            pass


def add_hair_factory_node(ob, dir_path, file):
    try:
        node_group = node_func(dir_path, file)
        modifier = ob.modifiers.new(node_group.name, 'NODES')
        modifier.node_group = node_group
        if bpy.context.preferences.addons[__package__].preferences.set_surface_ob:
            if get_modifier_socket_type_by_name(modifier, "Surface") == 'NodeSocketObject':
                set_modifier_socket_by_name(modifier, "Surface", ob.parent)
        return modifier
    except Exception as hfn_error:
        print(f"Error in loading {file} from {dir_path}: {hfn_error}")


def add_hair_factory_material(dir_path, file):
    try:
        mat = bpy.data.materials.new(name=Path(file).stem)
        mat.use_nodes = True
        material_func(dir_path, file, mat)
    except Exception as mat_error:
        print(f"Error in loading {file} from {dir_path}: {mat_error}")


### ACCESSORIES

def set_vert_groups(ob, vert_group_data):
    vertex_groups = ob.vertex_groups
    vertices = ob.data.vertices
    groups = array([g for g in vert_group_data.keys()])
    count = len(groups)
    for g in groups:
        nvg = vertex_groups.new(name=g)
        index = vert_group_data[g]['index'].tolist()
        nvg.add(index, 1.0, 'REPLACE')


def set_shape_keys(ob, key_block_data):
    keys = array(key_block_data.keys())
    count = len(keys)
    shape_keys = ob.data.shape_keys
    for sk in keys:
        data = key_block_data[sk]
        shape_key = ob.shape_key_add(from_mix=True)
        shape_key.name = sk
        shape_key.interpolation = data["interpolation"]
        shape_key.relative_key = data["relative_key"]
        shape_key.value = data["value"]
        shape_key.slider_min = data["slider_min"]
        shape_key.slider_max = data["slider_max"]
        shape_key.vertex_group = data["vertex_group"]
        for i, co in enumerate(data["co"]):
            shape_key.data[i].co = co
    return shape_keys


def set_uv_co(ob, co, uv_map="UVMap"):
    layers = ob.data.uv_layers
    if uv_map not in dict(layers).keys():
        layer = layers.new(name=uv_map, do_init=True)
    else:
        layer = layers[uv_map]
    uv = layer.uv
    co = array(co).ravel()
    uv.foreach_set('vector', co)


def get_sliced_data(data, counts):
    idx = 0
    for ct in counts:
        i = idx
        idx += ct
        s = slice(i, idx)
        yield list(data[s])


def deserialize_mesh(Name, verts=[], edges=[], faces=[], vert_groups=None, shape_keys=None, uv_co=None, uv_map="UVMap"):
    mesh = bpy.data.meshes.new(Name)
    mesh.from_pydata(verts, edges, faces)
    ob = bpy.data.objects.new(Name, mesh)
    bpy.context.collection.objects.link(ob)
    if not isinstance(vert_groups, type(None)):
        set_vert_groups(ob, vert_groups)
    if not isinstance(shape_keys, type(None)):
        set_shape_keys(ob, shape_keys)
    if not isinstance(uv_co, type(None)):
        set_uv_co(ob, uv_co, uv_map=uv_map)
    return ob


def get_scalp_mesh_data(file):
    with File(file, 'r') as hf:
        scalp = hf['SCALP']
        points = scalp['POINTS']['CO'][:]
        faces = list(get_sliced_data(scalp['FACES']['VERTS'][:], scalp['FACES']['COUNTS'][:]))
        vert_groups = {k: {'index': scalp["VERT_GROUPS"][k]['index'][:]} for k in scalp["VERT_GROUPS"].keys()}
        uvs = scalp['UVS']['CO'][:]
        return deserialize_mesh("Scalp_Mesh", verts=points, edges=[], faces=faces, vert_groups=vert_groups, shape_keys=None, uv_co=uvs, uv_map="UVMap")


def get_bead_data(file):
    with File(file, 'r') as hf:
        bead = hf['BEADZ']
        points = bead['POINTS']['CO'][:]
        faces = list(get_sliced_data(bead['FACES']['VERTS'][:], bead['FACES']['COUNTS'][:]))
        uvs = bead['UVS']['CO'][:]
        return deserialize_mesh("Bead", verts=points, edges=[], faces=faces, vert_groups=None, shape_keys=None, uv_co=uvs, uv_map="UVMap")


def load_scalp_mesh():
    zip_file = get_hf_accessories_zip()
    scalp = get_from_zip(zip_file, 'Accessories.hfdb', False, get_scalp_mesh_data)
    return scalp


def load_beadz():
    zip_file = get_hf_accessories_zip()
    beads = get_from_zip(zip_file, 'Accessories.hfdb', False, get_bead_data)
    return beads


### OPERATORS

class HAIRFACTORY_OT_get_node_user(Operator):
    bl_idname = "hair_factory.get_node_user"
    bl_label = "Get Geometry Node User"
    bl_description = "Get Geometry Node user type."
    bl_options = {'REGISTER', 'UNDO'}
    
    node_group: StringProperty(default="")

    def execute(self, context):
        ob = context.object
        try:
            user_ = get_node_group_user(self.node_group)
            ob.modifiers.active.node_group.hf_user = user_
            self.report({'INFO'}, f"{self.node_group} has user {user_}")
            return {'FINISHED'}
        except Exception as usr_error:
            self.report({'ERROR'}, f"Error gettting {self.node_group} user.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_menu_node(Operator):
    bl_idname = "hair_factory.load_menu_node"
    bl_label = "Load Menu Node"
    bl_description = "Load Node from Menu."
    bl_options = {'REGISTER', 'UNDO'}
    
    dir_path: StringProperty(default="")
    name: StringProperty(default="")

    def execute(self, context):
        try:
            node_group = node_func(Path(self.dir_path), self.name)
            node_.add_node(use_transform=True, settings=[{"name":"node_tree", "value":f"bpy.data.node_groups['{node_group.name}']"}, {"name":"width", "value":"140"}], type="GeometryNodeGroup")
            self.report({'INFO'}, f"{node_group.name} loaded.")
            return {'FINISHED'}
        except:
            self.report({'ERROR'}, f"Error loading {self.name[:-3]}.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_geometry_node(Operator):
    bl_idname = "hair_factory.load_geometry_node"
    bl_label = "Load Blender Geometry Node"
    bl_description = "Load Blender Geometry Node to Modifier Stack."
    bl_options = {'REGISTER', 'UNDO'}
    
    name: StringProperty(default="")

    def execute(self, context):
        try:
            ob = context.object
            modifier = load_procedural_hair_node(ob, self.name, gn_file=None)
            ob.modifiers.active = modifier
            self.report({'INFO'}, f"{self.name} loaded to Modifier Stack")
            return {'FINISHED'}
        except:
            self.report({'ERROR'}, f"Error loading {self.name} from Blender.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_hair_factory_node(Operator):
    bl_idname = "hair_factory.load_hair_factory_node"
    bl_label = "Load Hair Factory Node"
    bl_description = "Load Hair Factory Node to Modifier Stack."
    bl_options = {'REGISTER', 'UNDO'}
    
    name: StringProperty(default="")

    def execute(self, context):
        try:
            ob = context.object
            modifier = add_hair_factory_node(ob, get_hf_node_group_zip(), f"{self.name}.py")
            ob.modifiers.active = modifier
            self.report({'INFO'}, f"{self.name} loaded to Modifier Stack")
            return {'FINISHED'}
        except:
            self.report({'ERROR'}, f"Error loading {self.name} from Hair Factory.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_user_node(Operator):
    bl_idname = "hair_factory.load_user_node"
    bl_label = "Load User Node"
    bl_description = "Load User Node to Modifier Stack."
    bl_options = {'REGISTER', 'UNDO'}
    
    name: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return not context.preferences.addons[__package__].preferences.is_preset_path_set

    def execute(self, context):
        try:
            ob = context.object
            modifier = add_hair_factory_node(ob, get_user_node_group_zip(), f"{self.name}.py")
            ob.modifiers.active = modifier
            self.report({'INFO'}, f"{self.name} loaded to Modifier Stack")
            return {'FINISHED'}
        except:
            self.report({'ERROR'}, f"Error loading {self.name} from User.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_add_modifier(Operator):
    bl_idname = "hair_factory.modifier_new"
    bl_label = "Add Modifier"
    bl_description = "Add Geometry Node to Modifier Stack."
    bl_options = {'REGISTER', 'UNDO'}
    

    def execute(self, context):
        ob = context.object
        scene = context.scene
        if scene.hf_mod_target == 'None':
            self.report({'ERROR'}, "Node group not selected.")
            return {'CANCELLED'}
        name, user_ = scene.hf_mod_target.split("|")
        if user_ == "BLENDER":
            modifier = load_procedural_hair_node(ob, name, gn_file=None)
        elif user_ == "HAIR_FACTORY":
            modifier = add_hair_factory_node(ob, get_hf_node_group_zip(), f"{name}.py")
        elif user_ == "USER":
            modifier = add_hair_factory_node(ob, get_user_node_group_zip(), f"{name}.py")
        else:
            self.report({'ERROR'}, "Node group not found.")
            return {'CANCELLED'}
        ob.modifiers.active = modifier
        ob.active_modifier_idx = len(ob.modifiers) - 1
        self.report({'INFO'}, f"Source: {context.scene.hf_mod_source}  Node Group: {name}  User: {get_node_group_user(name)}")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        area_3d = context.area if context.area.type == 'VIEW_3D' else None
        if not area_3d:
            self.report({'ERROR'}, "3D viewport not found!")
            return {'CANCELLED'}
        context.window.cursor_warp(int(area_3d.width / 2), int(area_3d.height / 1.5))
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        scene = context.scene
        layout = self.layout
        box = layout.box()
        box.prop(scene, 'hf_mod_source')
        box.prop(scene, 'hf_mod_target')
        box.prop(scene, 'hf_mod_search')


class HAIRFACTORY_OT_get_mat_user(Operator):
    bl_idname = "hair_factory.get_mat_user"
    bl_label = "Get Material User"
    bl_description = "Get Material user type."
    bl_options = {'REGISTER', 'UNDO'}
    
    material: StringProperty(default="")

    def execute(self, context):
        try:
            user_ = get_mat_user(self.material)
            bpy.data.materials[self.material].hf_user = user_
            self.report({'INFO'}, f"{self.material} has user {user_}")
            return {'FINISHED'}
        except Exception as usr_error:
            self.report({'ERROR'}, f"Error gettting {self.material} user.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_add_material(Operator):
    bl_idname = "hair_factory.material_new"
    bl_label = "Load Material"
    bl_description = "Load Material to file."
    bl_options = {'REGISTER', 'UNDO'}
    

    def execute(self, context):
        scene = context.scene
        if scene.hf_mat_target == 'None':
            self.report({'ERROR'}, "Material not selected.")
            return {'CANCELLED'}
        name, user_ = scene.hf_mat_target.split("|")
        if user_ == "HAIR_FACTORY":
            add_hair_factory_material(get_hf_mat_zip(), f"{name}.py")
        elif user_ == "USER":
            add_hair_factory_material(get_user_mat_zip(), f"{name}.py")
        else:
            self.report({'ERROR'}, "Material not found.")
            return {'CANCELLED'}
        self.report({'INFO'}, f"{user_} Material: {name} loaded to file.")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        area_3d = context.area if context.area.type == 'VIEW_3D' else None
        if not area_3d:
            self.report({'ERROR'}, "3D viewport not found!")
            return {'CANCELLED'}
        context.window.cursor_warp(int(area_3d.width / 2), int(area_3d.height / 1.5))
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        scene = context.scene
        layout = self.layout
        box = layout.box()
        box.prop(scene, 'hf_mat_source')
        box.prop(scene, 'hf_mat_target')
        box.prop(scene, 'hf_mat_search')


class HAIRFACTORY_OT_load_menu_mat(Operator):
    bl_idname = "hair_factory.load_menu_mat"
    bl_label = "Load Menu Material"
    bl_description = "Load Material from Menu."
    bl_options = {'REGISTER', 'UNDO'}
    
    dir_path: StringProperty(default="")
    name: StringProperty(default="")

    def execute(self, context):
        try:
            add_hair_factory_material(Path(self.dir_path), self.name)
            self.report({'INFO'}, f"{self.name[:-3]} loaded.")
            return {'FINISHED'}
        except:
            self.report({'ERROR'}, f"Error loading {self.name[:-3]}.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_scalp(Operator):
    """
    """
    bl_idname = "hair_factory.load_scalp"
    bl_label = "Load Scalp Mesh"
    bl_description = "Load a Scalp Mesh for Hair placement."
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            scalp = load_scalp_mesh()
            add_hair_factory_node(scalp, get_hf_node_group_zip(), "SUBDIVISION_SHRINKWRAP.py")
            self.report({'INFO'}, "Scalp Mesh loaded.")
            return{'FINISHED'}
        except:
            self.report({'ERROR'}, f"Scalp Mesh could not be loaded.")
            return {'CANCELLED'}



class HAIRFACTORY_OT_load_beadz(Operator):
    """
    """
    bl_idname = "hair_factory.load_beadz"
    bl_label = "Load Procedural Beads"
    bl_description = "Load Procedural Beads for use as Hair Accessories. For example the BRAIDZ beads."
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            beads = load_beadz()
            add_hair_factory_node(beads, get_hf_node_group_zip(), "BEADZ_CONFIG.py")
            self.report({'INFO'}, "Beads loaded.")
            return{'FINISHED'}
        except:
            self.report({'ERROR'}, f"Beads could not be loaded.")
            return {'CANCELLED'}


class HAIRFACTORY_MT_hf_nodes(Menu):
    bl_label = "HAIR FACTORY"
    bl_idname = "HAIRFACTORY_MT_hf_nodes"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'GeometryNodeTree'
    
    def draw(self, context):
        layout = self.layout
        try:
            for name in get_zip_file_list(get_hf_node_group_zip()):
                if name[-3:] == '.py':
                    n_op = layout.operator(HAIRFACTORY_OT_load_menu_node.bl_idname, text=name[:-3])
                    n_op.dir_path = str(get_hf_node_group_zip())
                    n_op.name = name
        except:
            pass


class HAIRFACTORY_MT_user_nodes(Menu):
    bl_label = "USER"
    bl_idname = "HAIRFACTORY_MT_user_nodes"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'GeometryNodeTree'
    
    def draw(self, context):
        layout = self.layout
        try:
            for name in get_zip_file_list(get_user_node_group_zip()):
                if name[-3:] == '.py':
                    n_op = layout.operator(HAIRFACTORY_OT_load_menu_node.bl_idname, text=name[:-3])
                    n_op.dir_path = str(get_user_node_group_zip())
                    n_op.name = name
        except:
            pass


class HAIRFACTORY_MT_morzio_nodes(Menu):
    bl_label = "MORZIO"
    bl_idname = "HAIRFACTORY_MT_morzio_nodes"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'GeometryNodeTree'
    
    def draw(self, context):
        try:
            self.layout.menu(HAIRFACTORY_MT_hf_nodes.bl_idname)
            self.layout.menu(HAIRFACTORY_MT_user_nodes.bl_idname)
        except:
            pass


class HAIRFACTORY_MT_hf_mats(Menu):
    bl_label = "HAIR FACTORY"
    bl_idname = "HAIRFACTORY_MT_hf_mats"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'ShaderNodeTree'
    
    def draw(self, context):
        layout = self.layout
        try:
            for name in get_zip_file_list(get_hf_mat_zip()):
                if name[-3:] == '.py':
                    n_op = layout.operator(HAIRFACTORY_OT_load_menu_mat.bl_idname, text=name[:-3])
                    n_op.dir_path = str(get_hf_mat_zip())
                    n_op.name = name
        except:
            pass


class HAIRFACTORY_MT_user_mats(Menu):
    bl_label = "USER"
    bl_idname = "HAIRFACTORY_MT_user_mats"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'ShaderNodeTree'

    def draw(self, context):
        layout = self.layout
        try:
            for name in get_zip_file_list(get_user_mat_zip()):
                if name[-3:] == '.py':
                    n_op = layout.operator(HAIRFACTORY_OT_load_menu_mat.bl_idname, text=name[:-3])
                    n_op.dir_path = str(get_user_mat_zip())
                    n_op.name = name
        except:
            pass


class HAIRFACTORY_MT_morzio_mats(Menu):
    bl_label = "MORZIO"
    bl_idname = "HAIRFACTORY_MT_morzio_mats"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'ShaderNodeTree'
    
    def draw(self, context):
        try:
            self.layout.menu(HAIRFACTORY_MT_hf_mats.bl_idname)
            self.layout.menu(HAIRFACTORY_MT_user_mats.bl_idname)
        except:
            pass


def menu_func(self, context):
    if context.space_data.tree_type == 'GeometryNodeTree':
        self.layout.menu(HAIRFACTORY_MT_morzio_nodes.bl_idname)
    if context.space_data.tree_type == 'ShaderNodeTree':
        self.layout.menu(HAIRFACTORY_MT_morzio_mats.bl_idname)



classes = [
    HAIRFACTORY_OT_get_node_user,
    HAIRFACTORY_OT_load_menu_node,
    HAIRFACTORY_OT_load_geometry_node,
    HAIRFACTORY_OT_load_hair_factory_node,
    HAIRFACTORY_OT_load_user_node,
    HAIRFACTORY_OT_add_modifier,
    HAIRFACTORY_OT_get_mat_user,
    HAIRFACTORY_OT_add_material,
    HAIRFACTORY_OT_load_menu_mat,
    HAIRFACTORY_OT_load_scalp,
    HAIRFACTORY_OT_load_beadz,
    HAIRFACTORY_MT_hf_nodes,
    HAIRFACTORY_MT_user_nodes,
    HAIRFACTORY_MT_morzio_nodes,
    HAIRFACTORY_MT_hf_mats,
    HAIRFACTORY_MT_user_mats,
    HAIRFACTORY_MT_morzio_mats,
]


def register():
    for cls in classes:
        register_class(cls)
    
    NODE_MT_add.append(menu_func)

    Scene.hf_mod_source = EnumProperty(
        name = "Source",
        description = "Display Geometry Nodes by selected source.",
        items = [
            ("ALL", "All", "Display all available Geometry Node Groups."),
            ("BLENDER", "Blender", "Display the blender default Geometry Node Groups."),
            ("HAIR_FACTORY", "Hair Factory", "Display the Hair Factory Geometry Node Groups."),
            ("USER", "User", "Display the user defined Geometry Node Groups."),
        ],
    )
    Scene.hf_mod_target = EnumProperty(
        name = "Modifier",
        description = "Select Geometry Node Group to add to Modifier Stack.",
        items = mod_load_items,
    )
    Scene.hf_mod_search = StringProperty(
        name="Search",
        description="Narrow down search for Geometry Node Group.",
        options = {'TEXTEDIT_UPDATE'},
    )
    Scene.hf_mat_source = EnumProperty(
        name = "Source",
        description = "Display Materials by selected source.",
        items = [
            ("ALL", "All", "Display all available Materials."),
            ("HAIR_FACTORY", "Hair Factory", "Display the Hair Factory Materials."),
            ("USER", "User", "Display the user defined Materials."),
        ],
    )
    Scene.hf_mat_target = EnumProperty(
        name = "Material",
        description = "Select Material to Load.",
        items = mat_load_items,
    )
    Scene.hf_mat_search = StringProperty(
        name="Search",
        description="Narrow down search for Material.",
        options = {'TEXTEDIT_UPDATE'},
    )
    GeometryNodeTree.hf_user = StringProperty(
        name="User",
        description="Geometry Node user type.",
        default = "",
    )
    Material.hf_user = StringProperty(
        name="User",
        description="Material user type.",
        default = "",
    )


def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
    
    NODE_MT_add.remove(menu_func)
    
    del Scene.hf_mod_source
    del Scene.hf_mod_target
    del Scene.hf_mod_search
    del Scene.hf_mat_source
    del Scene.hf_mat_target
    del Scene.hf_mat_search
    del GeometryNodeTree.hf_user
    del Material.hf_user

