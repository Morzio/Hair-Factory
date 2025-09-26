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
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator, ShaderNode, FunctionNodeInputColor, GeometryNodeTree, Scene, Material, Curves
from bpy.utils import register_class, unregister_class, script_path_user
from mathutils import Vector, Euler
from numpy import (
                array, 
                empty, 
                r_, 
                ndarray, 
                where, 
                isin, 
                char, 
                invert, 
                array_split,
                integer,
                floating,
                )
from numpy.dtypes import StrDType
from hashlib import sha256
from json import dumps, loads, dump, load as jload, JSONEncoder
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_LZMA
from h5py import File, string_dtype
from re import search as search_


NODE_ENUM_CACHE = {}
NODE_GROUP_ENUM_CACHE = {}
MOD_STACK_ENUM_CACHE = {}
MAT_ENUM_CACHE = {}
PHY_ENUM_CACHE = {}
COL_ENUM_CACHE = {}
HAIR_ENUM_CACHE = {}
NODE_PREVIEW_CACHE = {}
NODE_GROUP_PREVIEW_CACHE = {}
MAT_PREVIEW_CACHE = {}
PHY_PREVIEW_CACHE = {}
COL_PREVIEW_CACHE = {}
HAIR_PREVIEW_CACHE = {}



def get_zip_file():
    return Path(bpy.context.preferences.addons[__package__].preferences.preset_path).joinpath("Presets.zip")


def is_preset_set():
    return bpy.context.preferences.addons[__package__].preferences.is_preset_path_set


def get_node_preset_count(file, node_type):
    with File(file, 'r') as hf:
        return hf['PRESETS'][node_type].len()


################################################################################


def is_basic_type(value):
    return isinstance(value, int) or isinstance(value, float) or isinstance(value, str) or isinstance(value, bool)


def is_string_blank(text):
    s = search_('\w', text)
    if not s:
        return True
    return False


def string_has_space(text):
    s = search_('\s', text)
    if not s:
        return False
    return True


def string_startswith_space(text):
    s = search_('\s', text)
    if not s:
        return False
    if s.start() == 0:
        return True
    return False


def get_node_node_tree(node_tree, node):
    for node_ in node_tree.nodes:
        if node_ == node:
            yield node_tree
        if node_.type == 'GROUP':
            yield from get_node_node_tree(node_.node_tree, node)


def get_node_material(node):
    for material in bpy.data.materials:
        tree = get_node_node_tree(material.node_tree, node)
        for t in tree:
            if t != None:
                return material


def get_node_source_data(node):
    if isinstance(node.id_data, GeometryNodeTree):
        node_group = bpy.context.object.modifiers.active.node_group
        return node_group, 'Geometry_Node', None
    else:
        material = get_node_material(node)
        return material.node_tree, 'Material', material.name


def immutable_dict(data_dict):
    data = dict()
    for k, v in data_dict.items():
        if isinstance(v, dict):
            data[k] = immutable_dict(v)
        elif isinstance(v, list):
            data[k] = tuple(v)
        elif isinstance(v, ndarray):
            data[k] = tuple(v.tolist())
        else:
            data[k] = v
    return data
        

def hash_dict(data_dict, chunk_size=1024):
    sha256_hash = sha256()
    hash_dict = immutable_dict(data_dict)
    hash_string = dumps(hash_dict, sort_keys=True).encode('utf-8')
    hs = BytesIO(hash_string)
    for byte_block in iter(lambda: hs.read(chunk_size), b""):
        sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def hash_list(data_list, chunk_size=1024):
    sha256_hash = sha256()
    hash_list = tuple(data_list)
    hash_string = dumps(hash_list).encode('utf-8')
    hs = BytesIO(hash_string)
    for byte_block in iter(lambda: hs.read(chunk_size), b""):
        sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_groups_str(node_group_name, groups):
    ng = f"""bpy.data.node_groups['{node_group_name}']"""
    ng += f""".nodes['{groups[0]}']"""
    if len(groups) > 1:
        for group in groups[1:]:
            ng += f""".node_tree.nodes['{group}']"""
    return ng


def get_node_group_groups(node_group_name, groups):
    ng = get_groups_str(node_group_name, groups)
    ob = dict()
    func = """
import bpy

def get_node_group_group():
    return {}

get_node_group_group()""".format(ng)
    exec(func, ob)
    return ob['get_node_group_group']()


def get_mat_str(mat_name, groups):
    mn = f"""bpy.data.materials['{mat_name}']"""
    for group in groups:
        mn += f""".node_tree.nodes['{group}']"""
    return mn


def get_mat_group_groups(mat_name, groups):
    ng = get_mat_str(mat_name, groups)
    ob = dict()
    func = """
import bpy

def get_node_group_group():
    return {}

get_node_group_group()""".format(ng)
    exec(func, ob)
    return ob['get_node_group_group']()


def is_linked(socket):
    return bool(socket.links)


def get_node_is_linked(node, invert=False):
    for socket in node.inputs:
        if invert:
            yield not is_linked(socket)
        else:
            yield is_linked(socket)


def get_input_sockets(node):
    for socket in node.inputs:
        yield socket


def get_node_attr(node):
    ignore_attr = [
            '__doc__', 
            '__module__', 
            '__slots__', 
            'bl_description', 
            'bl_height_default', 
            'bl_height_max', 
            'bl_height_min', 
            'bl_icon', 
            'bl_idname', 
            'bl_label', 
            'bl_rna', 
            'bl_static_type', 
            'bl_width_default', 
            'bl_width_max', 
            'bl_width_min', 
            'color', 
            'color_mapping', 
            'color_tag', 
            'debug_zone_body_lazy_function_graph', 
            'debug_zone_lazy_function_graph', 
            'dimensions', 
            'draw_buttons', 
            'draw_buttons_ext', 
            'height', 
            'hide', 
            'input_template', 
            'inputs', 
            'internal_links', 
            'is_registered_node_type', 
            'label', 
            'location', 
            'location_absolute', 
            'name', 
            'output_template', 
            'outputs', 
            'parent', 
            'poll', 
            'poll_instance', 
            'rna_type', 
            'select', 
            'show_options', 
            'show_preview', 
            'show_texture', 
            'socket_value_update', 
            'texture_mapping', 
            'type', 
            'update', 
            'use_custom_color', 
            'warning_propagation', 
            'width', 
            'object',
            'script',                
                ]
    for attr in dir(node):
        if attr not in ignore_attr and not attr.startswith('hf_'):
            yield {attr: getattr(node, attr)}


def get_node_inputs(node):
    for idx, n_s in enumerate(zip(get_node_is_linked(node, True), get_input_sockets(node))):
        not_linked, socket = n_s
        if not_linked:
            if hasattr(socket, "default_value"):
                value = socket.default_value
                if (hasattr(value, "data") and value.data.type in ['VECTOR', 'RGBA']) or isinstance(value, Vector) or isinstance(value, Euler):
                    value = list(value)
                yield {socket.name: [value, idx]}


def get_nodes(node_tree, parent=None):
    ignore_types = [
                    'RGB', 
                    'CURVE_FLOAT', 
                    'VALTORGB', 
                    'CURVE_VEC', 
                    'CURVE_RGB', 
                    'INPUT_COLOR', 
                    'OUTPUT_MATERIAL', 
                    'REROUTE', 
                    'FRAME', 
                    'GROUP', 
                    'GROUP_INPUT', 
                    'GROUP_OUTPUT',
                    'TEX_IMAGE' 
                    ]
    for idx in range(len(node_tree.nodes)):
        node = node_tree.nodes[idx]
        if node.type not in ignore_types:
            index = [idx] if parent is None else list([*parent, idx])
            yield [index, node.type, list(get_node_attr(node)), list(get_node_inputs(node))]


def get_group_nodes(node_tree, parent=None):
    for idx in range(len(node_tree.nodes)):
        node = node_tree.nodes[idx]
        if node.type == 'GROUP':
            index = [idx] if parent is None else list([*parent, idx])
            yield node.node_tree, index


def get_node_structure_gen(node_tree, parent=None):
    yield from get_nodes(node_tree, parent)
    for group in get_group_nodes(node_tree, parent):
        yield from get_node_structure_gen(*group)


def array_difference(src, target):
    return src[isin(src, target, invert=True)]


def search_bar_results(data, search_text):
    for idx in where(char.find(data, search_text) > -1)[0]:
        yield data[idx]


def info_finder(data_dict, keys_list, targets_list):
    poi = (data_dict[key] for key in keys_list)
    return list(i for i, d in enumerate(zip(*poi)) if (list(d) == list(targets_list)))


def add_series_nums(arr):
    def _add_series_nums(arr):
        num = 0
        for n in arr:
            num += n
            yield num
    return r_[*_add_series_nums(arr)]


def split_array_by_counts(arr, counts):
    return array_split(arr, add_series_nums(counts))


###################################################################################


def get_node_structure_list(nodes, ntype, parent=None):
    for i in range(len(nodes)):
        node = nodes[i]
        data = [i] if parent is None else list([*parent, i])
        if node.type == ntype:
            yield data
        if node.type == 'GROUP':
            gnodes = node.node_tree.nodes
            yield from get_node_structure_list(gnodes, ntype, parent=data)


def node_type_dict(node_group, classification='Geometry_Node'):
    slice_dict = {'Geometry_Node': (_ for _ in ['CURVE_FLOAT', 'VALTORGB', 'CURVE_VEC', 'CURVE_RGB', 'INPUT_COLOR']), 'Material': (_ for _ in ['RGB', 'CURVE_FLOAT', 'VALTORGB', 'CURVE_VEC', 'CURVE_RGB'])}
    data = {node_type: list(get_node_structure_list(node_group.nodes, node_type)) for node_type in slice_dict[classification]}
    return {k: v for k, v in data.items() if len(v) > 0}


def node_scan(node_group, node_dict, index=None):
    nodes = node_group.nodes
    for i in range(len(nodes)):
        if index is not None:
            idx = list([*index, i])
        else:
            idx = [i]
        node_dict['indices'].append([idx])
        node = nodes[i]
        node_dict['nodes'].append(node)
        node_dict['types'].append(node.type)
        if node.type == 'GROUP':
            gnodes = node.node_tree
            node_scan(gnodes, node_dict, index=idx)


def node_link_scan(node_group, node_dict):
    nodes = node_group.nodes
    links = node_group.links
    for l in links:
        fn = None
        tn = None
        for i, n in enumerate(node_dict['nodes']):
            if l.from_node == n:
                fn = i
            if l.to_node == n:
                tn = i
        node_dict['links'].append([list(*node_dict['indices'][fn]), list(*node_dict['indices'][tn])])
    for node in nodes:
        if node.type == 'GROUP':
            gnodes = node.node_tree
            node_link_scan(gnodes, node_dict)



def get_all_nodes(node_group):
    node_dict = {'indices': [], 'types': [], 'links': [], 'nodes': []}
    node_scan(node_group, node_dict)
    node_link_scan(node_group, node_dict)
    del node_dict['nodes']
    return node_dict


#######################################################################################
# Material Data


def get_mat_node_group_inputs(node_tree):
    for node in node_tree.nodes:
        if node.type == 'GROUP':
            data = dict(node.inputs)
            data = {n: (data[n].default_value if is_basic_type(data[n].default_value) else list(data[n].default_value)) for n in data if not data[n].is_linked}
            yield {
                'name': node.name, 
                'node': None, 
                'type': node.type,
                'data': {'attr': {}, 'inputs': data},
                }


def format_mat_node_data(material):
    node_tree = material.node_tree
    structure = get_node_structure_gen(node_tree, parent=None)
    for index, ntype, attr, inputs in structure:
        ndata = {
                'node': index,
                'type': ntype,
                'data': {'attr': {k: v for d in attr for k, v in d.items()}, 'inputs': {k: v for d in inputs for k, v in d.items()}},
                }
        yield ndata
    yield from get_mat_node_group_inputs(node_tree)


def set_mat_node_data(mat_name, mat_data):
    for mat_node in mat_data:
        name, addr, ntype, data = mat_node['name'], mat_node['node'], mat_node['type'], mat_node['data']
        if addr == None:
            addr = name
        else:
            addr = f"{addr}|{name}"
        node = get_mat_group_groups(mat_name, addr.split("|"))
        inputs = node.inputs
        for attr in data['attr']:
            try:
                setattr(node, attr, data['attr'][attr])
            except:
                continue
        for key in data['inputs']:
            try:
                node.inputs[key].default_value = (data['inputs'][key] if ntype == 'GROUP' else data['inputs'][key][0])
            except:
                node.inputs[data['inputs'][key][1]].default_value = (data['inputs'][key] if ntype == 'GROUP' else data['inputs'][key][0])
    bpy.data.materials[mat_name].node_tree.nodes.update()


###################################################################################

# HAIR

def get_hair_pts(hair_curve):
    points = hair_curve.data.points
    curves = hair_curve.data.curves
    ct = len(points)
    co = empty(ct * 3)
    points.foreach_get('position', co)
    sct = len(curves)
    sizes = empty(sct)
    curves.foreach_get('points_length', sizes)
    return {
        'points': co.reshape((ct, 3)),
        'sizes': sizes,
    }


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
    if not isinstance(sizes, type(None)):
        if isinstance(sizes, ndarray):
            sizes = sizes.tolist()
        hair_curve.data.add_curves(sizes)
    if not isinstance(points, type(None)):
        set_hair_pts(hair_curve, points)
    return hair_curve


###################################################################################

# SPECIAL NODE FUNCTIONS

def get_color_ramp_data(color_ramp):
    ramp = color_ramp.color_ramp
    interpolation = (ramp.interpolation if ramp.color_mode == 'RGB' else ramp.hue_interpolation)
    elements = ramp.elements
    count = len(elements)
    col = empty(count * 4)
    pos = empty(count)
    elements.foreach_get('color', col)
    elements.foreach_get('position', pos)
    return {
            'color': col.reshape((count, 4)).tolist(),
            'position': pos.tolist(),
            'color_mode': ramp.color_mode,
            'interpolation': interpolation,
            'factor': color_ramp.inputs[0].default_value,
            }


def set_color_ramp_data(color_ramp, data):
    ramp = color_ramp.color_ramp
    elements = ramp.elements
    col, pos = data['color'], data['position']
    mode, interpolation = data['color_mode'], data['interpolation']
    ramp.color_mode = mode
    color_ramp.inputs[0].default_value = data['factor']
    if mode == 'RGB':
        ramp.interpolation = interpolation
    else:
        ramp.hue_interpolation = interpolation
    count = len(elements)
    pct = len(pos)
    if count > pct:
        ct = count - pct
        for e in range(ct):
            elements.remove(elements[e])
    if count < pct:
        ct = pct - count
        for e in range(ct):
            elements.new(0.0)
    col = array(col).ravel()
    elements.foreach_set('color', col)
    elements.foreach_set('position', pos)
    elements.update()


def get_float_curve_data(float_curve):
    mapping = float_curve.mapping
    inputs = float_curve.inputs
    points = mapping.curves[0].points
    count = len(points)
    loc = empty(count * 2)
    points.foreach_get('location', loc)
    ht = [p.handle_type for p in points]
    return {
            'location': loc.reshape((count, 2)).tolist(),
            'handle_type': ht, 
            'use_clip': mapping.use_clip, 
            'clip_min_x': mapping.clip_min_x,
            'clip_min_y': mapping.clip_min_y,
            'clip_max_x': mapping.clip_max_x,
            'clip_max_y': mapping.clip_max_y,
            'black_level': list(mapping.black_level),
            'white_level': list(mapping.white_level),
            'tone': mapping.tone,
            'extend': mapping.extend,
            'factor': inputs[0].default_value,
            'value': inputs[1].default_value,
            }


def set_float_curve_data(float_curve, data):
    mapping = float_curve.mapping
    inputs = float_curve.inputs
    mapping.use_clip = data['use_clip']
    mapping.clip_min_x = data['clip_min_x']
    mapping.clip_min_y = data['clip_min_y']
    mapping.clip_max_x = data['clip_max_x']
    mapping.clip_max_y = data['clip_max_y']
    mapping.black_level = data['black_level']
    mapping.white_level = data['white_level']
    mapping.tone = data['tone']
    mapping.extend = data['extend']
    inputs[0].default_value = data['factor']
    inputs[1].default_value = data['value']
    points = mapping.curves[0].points
    loc, ht = data['location'], data['handle_type']
    count = len(points)
    htct = len(ht)
    if count > htct:
        ct = count - htct
        for p in range(ct):
            points.remove(points[p])
            points.update()
    if count < htct:
        ct = htct - count
        for p in range(ct):
            points.new(.5, .5)
            points.update()
    loc = array(loc).ravel()
    points.foreach_set('location', loc)
    for p in range(htct):
        points[p].handle_type = ht[p]
    float_curve.mapping.curves.update()
    float_curve.mapping.update()
    float_curve.update()


def get_rgb_curves_data(rgb_curves):
    mapping = rgb_curves.mapping
    curves = mapping.curves
    inputs = rgb_curves.inputs
    pts = []
    hts = []
    for curve in curves:
        points = curve.points
        count = len(points)
        loc = empty(count * 2)
        points.foreach_get('location', loc)
        ht = [p.handle_type for p in points]
        pts.append(loc.reshape((count, 2)).tolist())
        hts.append(ht)
    return {
            'location': pts,
            'handle_type': hts, 
            'use_clip': mapping.use_clip, 
            'clip_min_x': mapping.clip_min_x,
            'clip_min_y': mapping.clip_min_y,
            'clip_max_x': mapping.clip_max_x,
            'clip_max_y': mapping.clip_max_y,
            'black_level': list(mapping.black_level),
            'white_level': list(mapping.white_level),
            'tone': mapping.tone,
            'extend': mapping.extend,
            'factor': inputs[0].default_value,
            'color': list(inputs[1].default_value),
            }


def set_rgb_curves_data(rgb_curves, data):
    mapping = rgb_curves.mapping
    curves = mapping.curves
    inputs = rgb_curves.inputs
    mapping.use_clip = data['use_clip']
    mapping.clip_min_x = data['clip_min_x']
    mapping.clip_min_y = data['clip_min_y']
    mapping.clip_max_x = data['clip_max_x']
    mapping.clip_max_y = data['clip_max_y']
    mapping.black_level = data['black_level']
    mapping.white_level = data['white_level']
    mapping.tone = data['tone']
    mapping.extend = data['extend']
    inputs[0].default_value = data['factor']
    inputs[1].default_value = data['color']
    for idx, curve in enumerate(curves):
        points = curve.points
        loc, ht = data['location'][idx], data['handle_type'][idx]
        count = len(points)
        htct = len(ht)
        if count > htct:
            ct = count - htct
            for p in range(ct):
                points.remove(points[p])
                points.update()
        if count < htct:
            ct = htct - count
            for p in range(ct):
                points.new(.5, .5)
                points.update()
        loc = array(loc).ravel()
        points.foreach_set('location', loc)
        for p in range(htct):
            points[p].handle_type = ht[p]
    rgb_curves.mapping.curves.update()
    rgb_curves.mapping.update()
    rgb_curves.update()


def get_vector_curves_data(vector_curves):
    mapping = vector_curves.mapping
    curves = mapping.curves
    inputs = vector_curves.inputs
    pts = []
    hts = []
    for curve in curves:
        points = curve.points
        count = len(points)
        loc = empty(count * 2)
        points.foreach_get('location', loc)
        ht = [p.handle_type for p in points]
        pts.append(loc.reshape((count, 2)).tolist())
        hts.append(ht)
    return {
            'location': pts,
            'handle_type': hts, 
            'use_clip': mapping.use_clip, 
            'clip_min_x': mapping.clip_min_x,
            'clip_min_y': mapping.clip_min_y,
            'clip_max_x': mapping.clip_max_x,
            'clip_max_y': mapping.clip_max_y,
            'black_level': list(mapping.black_level),
            'white_level': list(mapping.white_level),
            'tone': mapping.tone,
            'extend': mapping.extend,
            'factor': inputs[0].default_value,
            'vector': list(inputs[1].default_value),
            }


def set_vector_curves_data(vector_curves, data):
    mapping = vector_curves.mapping
    curves = mapping.curves
    inputs = vector_curves.inputs
    mapping.use_clip = data['use_clip']
    mapping.clip_min_x = data['clip_min_x']
    mapping.clip_min_y = data['clip_min_y']
    mapping.clip_max_x = data['clip_max_x']
    mapping.clip_max_y = data['clip_max_y']
    mapping.black_level = data['black_level']
    mapping.white_level = data['white_level']
    mapping.tone = data['tone']
    mapping.extend = data['extend']
    inputs[0].default_value = data['factor']
    inputs[1].default_value = data['vector']
    for idx, curve in enumerate(curves):
        points = curve.points
        loc, ht = data['location'][idx], data['handle_type'][idx]
        count = len(points)
        htct = len(ht)
        if count > htct:
            ct = count - htct
            for p in range(ct):
                points.remove(points[p])
                points.update()
        if count < htct:
            ct = htct - count
            for p in range(ct):
                points.new(.5, .5)
                points.update()
        loc = array(loc).ravel()
        points.foreach_set('location', loc)
        for p in range(htct):
            points[p].handle_type = ht[p]
    vector_curves.mapping.curves.update()
    vector_curves.mapping.update()
    vector_curves.update()


def get_input_color_data(rgb_color):
    return {'value': list(rgb_color.value)}


def set_input_color_data(rgb_color, data):
    rgb_color.value = data['value']


def get_rgb_color_data(rgb_color):
    return {'color': list(rgb_color.outputs[0].default_value)}


def set_rgb_color_data(rgb_color, data):
    rgb_color.outputs[0].default_value = data['color']


def get_nodes_func_dict():
    return {
        'CURVE_FLOAT': get_float_curve_data,
        'VALTORGB': get_color_ramp_data,
        'CURVE_RGB': get_rgb_curves_data,
        'CURVE_VEC': get_vector_curves_data,
        'INPUT_COLOR': get_input_color_data,
        'RGB': get_rgb_color_data,
    }


def set_nodes_func_dict():
    return {
        'CURVE_FLOAT': set_float_curve_data,
        'VALTORGB': set_color_ramp_data,
        'CURVE_RGB': set_rgb_curves_data,
        'CURVE_VEC': set_vector_curves_data,
        'INPUT_COLOR': set_input_color_data,
        'RGB': set_rgb_color_data,
    }


def node_type_abbr_dict():
    data = {
        'RGB': 'RB', 
        'CURVE_FLOAT': 'FC', 
        'VALTORGB': 'CR', 
        'CURVE_VEC': 'VC', 
        'CURVE_RGB': 'RC', 
        'INPUT_COLOR': 'IC',
    }
    return data


###################################################################################


def get_dir_files(dir_path, filter='*py'):
    return Path(dir_path).glob(filter)


def get_dir_file_stems(dir_path, filter='*py', ignore_files=['__init__']):
    return (file.stem for file in get_dir_files(dir_path, filter=filter) if file.stem not in ignore_files)


###################################################################################

# IO FUNCTIONS

class NameExistsError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


def get_from_zip(zip_file, file_name, is_gen, func, *args, **kwargs):
    try:
        with ZipFile(zip_file, 'r') as zf:
            with zf.open(file_name) as hf:
                if is_gen:
                    return (_ for _ in list(func(hf, *args, **kwargs)))
                return func(hf, *args, **kwargs)
    except:
        pass


def copy_file_by_chunks(src_file, target_file):
    with open(src_file, 'rb') as src:
        with open(target_file, 'wb') as tgt:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                tgt.write(chunk)


def read_file_by_chunks(src_file):
    with open(src_file, 'rb') as src:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            yield chunk


def get_max_series_num(name, data):
    num = 0
    for n in data:
        if n:
            ns = n.split('.')
            if ns[0] == name.split('.')[0]:
                if len(ns) > 1:
                    i = int(ns[1])
                    if i > num:
                        num = i
    return num
            

def get_match_series_highest(name, data):
    ms = get_max_series_num(name, data)
    return f'{name.split(".")[0]}.{str(ms + 1).zfill(3)}'


def modify_in_zip(zip_file, file_name, func, *args, **kwargs):
    try:
        extract_dir = zip_file.parent
        extract_file = extract_dir.joinpath(file_name)
        with ZipFile(zip_file, 'r') as zf:
            zf.extract(file_name, extract_dir)
        data = func(extract_file, *args, **kwargs)
        with ZipFile(zip_file, 'w', compression=ZIP_LZMA, compresslevel=9, allowZip64=True) as zf:
            for chunk in read_file_by_chunks(extract_file):
                zf.writestr(file_name, chunk)
        extract_file.unlink()
        return data
    except:
        # pass
        try:
            extract_file.unlink()
        except:
            pass


def match_node(node_, node_tree, parent=None):
    for idx in range(len(node_tree.nodes)):
        node = node_tree.nodes[idx]
        if node == node_:
            index = [idx] if parent is None else list([*parent, idx])
            yield [index, node.type]


def get_group_nodes(node_tree, parent=None):
    for node in node_tree.nodes:
        if node.type == 'GROUP':
            yield node.node_tree, parent


def match_node_structure_gen(node_, node_tree, parent=None):
    yield from match_node(node_, node_tree, parent)
    for group in get_group_nodes(node_tree, parent):
        yield from match_node_structure_gen(node_, *group)


def get_names(pfile):
    for n in pfile:
        yield pfile[n].attrs.get('name')


def get_names_enum(file, pfile):
    with File(file, 'r') as hf:
        for n in hf[pfile]:
            yield (n, hf[pfile][n].attrs.get('name'), '')


def get_name_by_id(file, pfile, id_):
    with File(file, 'r') as hf:
        return hf[pfile][id_].attrs.get('name')


def get_node_names_enum(file, node_type, search_text):
    with File(file, 'r') as hf:
        node_file = hf['NODES']
        presets = hf['PRESETS'][node_type]
        for n in presets[:].astype(str):
            name = node_file[n].attrs.get('name')
            if char.find(name, search_text).item() > -1:
                yield (n, name, '')


def change_preset_name(file, pfile, id_, name):
    with File(file, 'r+') as hf:
        if name in get_names(hf[pfile]):
            raise NameExistsError(f'[Preset] {name} already in use. Please choose another name.')
        prev_name = hf[pfile][id_].attrs.get('name')
        hf[pfile][id_].attrs['name'] = name
        return prev_name


def create_preset_files(file):
    ntypes = ['RGB', 'CURVE_FLOAT', 'VALTORGB', 'CURVE_VEC', 'CURVE_RGB', 'INPUT_COLOR']
    with File(file, 'a') as hf:
        files = [key for key in hf.keys()]
        if "PRESETS" not in files:
            presets = hf.create_group("PRESETS")
            pmat = presets.create_group("MATERIALS")
            mdata = pmat.create_group("DATA", track_order=True)
            minfo = pmat.create_group("INFO", track_order=True)
            mtrans = pmat.create_group("TRANSACTIONS", track_order=True)
            mful = pmat.create_group("FULL", track_order=True)
            mval = pmat.create_group("VALUES", track_order=True)
            pgn = presets.create_group("GEOMETRY_NODES")
            gdata = pgn.create_group("DATA", track_order=True)
            ginfo = pgn.create_group("INFO", track_order=True)
            gtrans = pgn.create_group("TRANSACTIONS", track_order=True)
            gful = pgn.create_group("FULL", track_order=True)
            gval = pgn.create_group("VALUES", track_order=True)
            mstack = pgn.create_group("MODIFIER_STACK", track_order=True)
            for ntype in ntypes:
                presets.create_dataset(ntype, shape=(0,), dtype=string_dtype(), maxshape=(None,), compression='gzip', compression_opts=9)
        if "NODES" not in files:
            hf.create_group("NODES", track_order=True)
        if "NODE_STACK" not in files:
            hf.create_group("NODE_STACK", track_order=True)
        if "PHYSICS" not in files:
            physics = hf.create_group("PHYSICS")
            cl = physics.create_group("CLOTH", track_order=True)
            sb = physics.create_group("SOFT_BODY", track_order=True)
            co = physics.create_group("COLLISION", track_order=True)
        if "HAIR" not in files:
            hair = hf.create_group("HAIR")
            pts = hair.create_group("POINTS", track_order=True)
            szs = hair.create_group("SIZES", track_order=True)
            

def create_preset_zip(zip_file):
    file_name = 'Presets.hfdb'
    file = zip_file.parent.joinpath(file_name)
    create_preset_files(file)
    with ZipFile(zip_file, 'w', compression=ZIP_LZMA, compresslevel=9, allowZip64=True) as zf:
        for chunk in read_file_by_chunks(file):
            zf.writestr(file_name, chunk)
    file.unlink()


def get_mat_colors_(file):
    with File(file, 'r') as hf:
        return loads(hf["COLOR_PRESETS"]["PRESETS"][0])

def get_mat_colors():
    return get_from_zip(Path(script_path_user()).joinpath("addons").joinpath(__package__).joinpath("Assets").joinpath("ACCESSORIES.zip"), "Accessories.hfdb", False, get_mat_colors_)


def load_preset_mat_colors(file, data_dict):
    node_type = "VALTORGB"
    with File(file, 'a') as hf:
        node_file = hf['NODES']
        for preset_name in data_dict:
            data = data_dict[preset_name]
            nid = hash_dict(data)
            if (nid not in node_file.keys()):
                nf = hf[f'/PRESETS/{node_type}']
                ndata = node_file.create_dataset(nid, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
                ndata.attrs['name'] = f'{preset_name}'
                ndata.attrs['type'] = node_type
                if nid not in nf[:].astype(str):
                    nf.resize((nf.shape[0] + 1,))
                    nf[-1:] = array([nid], dtype=bytes)


###################################################################################

# PRESET FUNCTIONS

def node_preset_processing(file, node, node_tree, preset_name, classification='Geometry_Node', mat_name=None):
    preset_saved = False
    pname = None
    node_data, node_type = next(match_node_structure_gen(node, node_tree))
    func = get_nodes_func_dict()[node_type]
    if len(node_data) == 1:
        data = func(node_tree.nodes[node_data[0]])
    elif classification == 'Geometry_Node':
        data = func(get_node_group_groups(node_tree.name, node_data))
    else:
        data = func(get_mat_group_groups(mat_name, node_data))
    nid = hash_dict(data)
    with File(file, 'a') as hf:
        node_file = hf['NODES']
        if preset_name in get_names(node_file):
            raise NameExistsError(f'[Node Preset] {preset_name} already exists. Please choose another name.')
        if (nid not in node_file.keys()):
            nf = hf[f'/PRESETS/{node_type}']
            ndata = node_file.create_dataset(nid, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
            ndata.attrs['name'] = f'{preset_name}'
            ndata.attrs['type'] = node_type
            preset_saved = True
            if nid not in nf[:].astype(str):
                nf.resize((nf.shape[0] + 1,))
                nf[-1:] = array([nid], dtype=bytes)
        else:
            pname = node_file[nid].attrs.get('name')
        return preset_saved, pname


def material_preset_processing(file, material, preset_name, user_):
    preset_saved = False
    pname = None
    node_tree = material.node_tree
    # FILES
    with File(file, 'a') as hf:
        type_file = hf['PRESETS']['MATERIALS']
        trans_file = type_file['TRANSACTIONS']
        if preset_name in get_names(trans_file):
            raise NameExistsError(f'[Preset Name] {preset_name} already exists. Please choose another name.')
        info_file = type_file['INFO']
        data_file = type_file['DATA']
        node_file = hf['NODES']
        node_stack_file = hf['NODE_STACK']
        mat_id = hash_dict(get_all_nodes(node_tree))
        node_values = list(format_mat_node_data(material))
        values_id = hash_list(node_values)
        # INFO
        if (mat_id not in info_file.keys()):
            ntd_ = node_type_dict(node_tree, classification='Material')
            minfo = info_file.create_dataset(mat_id, shape=(1,), dtype=string_dtype(), data=array([dumps(ntd_)], dtype=bytes), compression='gzip', compression_opts=9)
            minfo.attrs['name'] = material.name.split('.')[0]
            minfo.attrs['class'] = 'Material'
            minfo.attrs['user'] = user_
        else:
            minfo = info_file[mat_id]
            ntd_ = loads(minfo[0])
        # DATA
        if (values_id not in data_file.keys()):
            mdata = data_file.create_dataset(values_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_values)], dtype=bytes), compression='gzip', compression_opts=9)
            values_name = preset_name
            if values_name in get_names(data_file):
                values_name = get_match_series_highest(values_name, get_names(data_file))
            mdata.attrs['name'] = values_name
        else:
            mdata = data_file[values_id]
        # NODES
        node_ids = {}
        for node_type in ntd_:
            nis = {node_type: []}
            func = get_nodes_func_dict()[node_type]
            ngroup_name = f'/PRESETS/{node_type}'
            ct = hf[ngroup_name].len()
            for node in ntd_[node_type]:
                if len(node) == 1:
                    data = func(node_tree.nodes[node[0]])
                else:
                    data = func(get_mat_group_groups(material.name, node))
                nid = hash_dict(data)
                if (nid not in node_file.keys()):
                    ndata = node_file.create_dataset(nid, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
                    suggested_name = f'{node_type_abbr_dict()[node_type]}_{ct}'
                    if suggested_name in get_names(node_file):
                        suggested_name = get_match_series_highest(suggested_name, get_names(node_file))
                    ndata.attrs['name'] = suggested_name
                    ndata.attrs['type'] = f'{node_type}'
                    ct += 1
                else:
                    ndata = node_file[nid]
                nis[node_type].append(nid)
                if nid not in hf[ngroup_name][:].astype(str):
                    hf[ngroup_name].resize((hf[ngroup_name].shape[0] + 1,))
                    hf[ngroup_name][-1:] = array([nid], dtype=bytes)
            node_ids.update(nis)
        ni_id = hash_dict(node_ids)
        if (ni_id not in node_stack_file.keys()):
            nid_data = node_stack_file.create_dataset(ni_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_ids)], dtype=bytes), compression='gzip', compression_opts=9)
        # TRANSACTIONS
        pid = hash_list([mat_id, values_id, ni_id])
        if (pid not in trans_file.keys()):
            pdata = trans_file.create_dataset(pid, shape=(1, 3), dtype=string_dtype(), data=array([mat_id, values_id, ni_id], dtype=bytes), compression='gzip', compression_opts=9)
            pdata.attrs['name'] = preset_name
        else:
            pdata = trans_file[pid]
        # LINKS
        pname = pdata.attrs.get('name')
        pful_name = '/PRESETS/MATERIALS/FULL'
        pval_name = '/PRESETS/MATERIALS/VALUES'
        pful_file = hf[pful_name]
        pval_file = hf[pval_name]
        if mat_id not in pful_file.keys():
            pf_data = pful_file.create_dataset(mat_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([pid], dtype=bytes), compression='gzip', compression_opts=9)
            pv_data = pval_file.create_dataset(mat_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([values_id], dtype=bytes), compression='gzip', compression_opts=9)
            preset_saved = True
        else:
            if pid not in pful_file[mat_id][:].astype(str):
                pful_file[mat_id].resize((pful_file[mat_id].shape[0] + 1,))
                pful_file[mat_id][-1:] = array([pid], dtype=bytes)
                preset_saved = True
            if values_id not in pval_file[mat_id][:].astype(str):
                pval_file[mat_id].resize((pval_file[mat_id].shape[0] + 1,))
                pval_file[mat_id][-1:] = array([values_id], dtype=bytes)
    return preset_saved, pname


def geometry_node_preset_processing(file, node_group, preset_name, user_):
    preset_saved = False
    pname = None
    # FILES
    with File(file, 'a') as hf:
        type_file = hf['PRESETS']['GEOMETRY_NODES']
        trans_file = type_file['TRANSACTIONS']
        if preset_name in get_names(trans_file):
            raise NameExistsError(f'[Preset Name] {preset_name} already exists. Please choose another name.')
        info_file = type_file['INFO']
        data_file = type_file['DATA']
        node_file = hf['NODES']
        node_stack_file = hf['NODE_STACK']
        ng_id = hash_dict(get_all_nodes(node_group))
        node_values = dict(get_node_group_input_data(node_group))
        values_id = hash_dict(node_values)
        # INFO
        if (ng_id not in info_file.keys()):
            ntd_ = node_type_dict(node_group)
            minfo = info_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), data=array([dumps(ntd_)], dtype=bytes), compression='gzip', compression_opts=9)
            minfo.attrs['name'] = node_group.name.split('.')[0]
            minfo.attrs['class'] = 'Geometry_Node'
            minfo.attrs['user'] = user_
        else:
            minfo = info_file[ng_id]
            ntd_ = loads(minfo[0])
        # DATA
        if (values_id not in data_file.keys()):
            mdata = data_file.create_dataset(values_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_values)], dtype=bytes), compression='gzip', compression_opts=9)
            values_name = preset_name
            if values_name in get_names(data_file):
                values_name = get_match_series_highest(values_name, get_names(data_file))
            mdata.attrs['name'] = values_name
        else:
            mdata = data_file[values_id]
        # NODES
        node_ids = {}
        for node_type in ntd_:
            nis = {node_type: []}
            func = get_nodes_func_dict()[node_type]
            ngroup_name = f'/PRESETS/{node_type}'
            ct = hf[ngroup_name].len()
            for node in ntd_[node_type]:
                if len(node) == 1:
                    data = func(node_group.nodes[node[0]])
                else:
                    data = func(get_node_group_groups(node_group.name, node))
                nid = hash_dict(data)
                if (nid not in node_file.keys()):
                    ndata = node_file.create_dataset(nid, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
                    suggested_name = f'{node_type_abbr_dict()[node_type]}_{ct}'
                    if suggested_name in get_names(node_file):
                        suggested_name = get_match_series_highest(suggested_name, get_names(node_file))
                    ndata.attrs['name'] = suggested_name
                    ndata.attrs['type'] = f'{node_type}'
                    ct += 1
                else:
                    ndata = node_file[nid]
                nis[node_type].append(nid)
                if nid not in hf[ngroup_name][:].astype(str):
                    hf[ngroup_name].resize((hf[ngroup_name].shape[0] + 1,))
                    hf[ngroup_name][-1:] = array([nid], dtype=bytes)
            node_ids.update(nis)
        ni_id = hash_dict(node_ids)
        if (ni_id not in node_stack_file.keys()):
            nid_data = node_stack_file.create_dataset(ni_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_ids)], dtype=bytes), compression='gzip', compression_opts=9)
        # TRANSACTIONS
        pid = hash_list([ng_id, values_id, ni_id])
        if (pid not in trans_file.keys()):
            pdata = trans_file.create_dataset(pid, shape=(1, 3), dtype=string_dtype(), data=array([ng_id, values_id, ni_id], dtype=bytes), compression='gzip', compression_opts=9)
            pdata.attrs['name'] = preset_name
        else:
            pdata = trans_file[pid]
        # LINKS
        pname = pdata.attrs.get('name')
        pful_name = '/PRESETS/GEOMETRY_NODES/FULL'
        pval_name = '/PRESETS/GEOMETRY_NODES/VALUES'
        pful_file = hf[pful_name]
        pval_file = hf[pval_name]
        if ng_id not in pful_file.keys():
            pf_data = pful_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([pid], dtype=bytes), compression='gzip', compression_opts=9)
            pv_data = pval_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([values_id], dtype=bytes), compression='gzip', compression_opts=9)
            preset_saved = True
        else:
            if pid not in pful_file[ng_id][:].astype(str):
                pful_file[ng_id].resize((pful_file[ng_id].shape[0] + 1,))
                pful_file[ng_id][-1:] = array([pid], dtype=bytes)
                preset_saved = True
            if values_id not in pval_file[ng_id][:].astype(str):
                pval_file[ng_id].resize((pval_file[ng_id].shape[0] + 1,))
                pval_file[ng_id][-1:] = array([values_id], dtype=bytes)
        return preset_saved, pname


def geometry_node_processing(hf, modifier, preset_name, user_):
    preset_saved = False
    pname = None
    # FILES
    type_file = hf['PRESETS']['GEOMETRY_NODES']
    trans_file = type_file['TRANSACTIONS']
    if preset_name in get_names(trans_file):
        preset_name = get_match_series_highest(preset_name, get_names(trans_file))
    info_file = type_file['INFO']
    data_file = type_file['DATA']
    node_file = hf['NODES']
    node_stack_file = hf['NODE_STACK']
    node_group = modifier.node_group
    ng_id = hash_dict(get_all_nodes(node_group))
    node_values = dict(get_node_group_input_data(node_group, modifier=modifier))
    values_id = hash_dict(node_values)
    # INFO
    if (ng_id not in info_file.keys()):
        ntd_ = node_type_dict(node_group)
        minfo = info_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), data=array([dumps(ntd_)], dtype=bytes), compression='gzip', compression_opts=9)
        minfo.attrs['name'] = node_group.name.split('.')[0]
        minfo.attrs['class'] = 'Geometry_Node'
        minfo.attrs['user'] = user_
    else:
        minfo = info_file[ng_id]
        ntd_ = loads(minfo[0])
    # DATA
    if (values_id not in data_file.keys()):
        mdata = data_file.create_dataset(values_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_values)], dtype=bytes), compression='gzip', compression_opts=9)
        values_name = preset_name
        if values_name in get_names(data_file):
            values_name = get_match_series_highest(values_name, get_names(data_file))
        mdata.attrs['name'] = values_name
    else:
        mdata = data_file[values_id]
    # NODES
    node_ids = {}
    for node_type in ntd_:
        nis = {node_type: []}
        func = get_nodes_func_dict()[node_type]
        ngroup_name = f'/PRESETS/{node_type}'
        ct = hf[ngroup_name].len()
        for node in ntd_[node_type]:
            if len(node) == 1:
                    data = func(node_group.nodes[node[0]])
            else:
                data = func(get_node_group_groups(node_group.name, node))
            nid = hash_dict(data)
            if (nid not in node_file.keys()):
                ndata = node_file.create_dataset(nid, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
                suggested_name = f'{node_type_abbr_dict()[node_type]}_{ct}'
                if suggested_name in get_names(node_file):
                    suggested_name = get_match_series_highest(suggested_name, get_names(node_file))
                ndata.attrs['name'] = suggested_name
                ndata.attrs['type'] = f'{node_type}'
                ct += 1
            else:
                ndata = node_file[nid]
            nis[node_type].append(nid)
            if nid not in hf[ngroup_name][:].astype(str):
                hf[ngroup_name].resize((hf[ngroup_name].shape[0] + 1,))
                hf[ngroup_name][-1:] = array([nid], dtype=bytes)
        node_ids.update(nis)
    ni_id = hash_dict(node_ids)
    if (ni_id not in node_stack_file.keys()):
        nid_data = node_stack_file.create_dataset(ni_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_ids)], dtype=bytes), compression='gzip', compression_opts=9)
    # TRANSACTIONS
    pid = hash_list([ng_id, values_id, ni_id])
    if (pid not in trans_file.keys()):
        pdata = trans_file.create_dataset(pid, shape=(1, 3), dtype=string_dtype(), data=array([ng_id, values_id, ni_id], dtype=bytes), compression='gzip', compression_opts=9)
        pdata.attrs['name'] = preset_name
    else:
        pdata = trans_file[pid]
    # LINKS
    pname = pdata.attrs.get('name')
    pful_name = '/PRESETS/GEOMETRY_NODES/FULL'
    pval_name = '/PRESETS/GEOMETRY_NODES/VALUES'
    pful_file = hf[pful_name]
    pval_file = hf[pval_name]
    if ng_id not in pful_file.keys():
        pf_data = pful_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([pid], dtype=bytes), compression='gzip', compression_opts=9)
        pv_data = pval_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([values_id], dtype=bytes), compression='gzip', compression_opts=9)
        preset_saved = True
    else:
        if pid not in pful_file[ng_id][:].astype(str):
            pful_file[ng_id].resize((pful_file[ng_id].shape[0] + 1,))
            pful_file[ng_id][-1:] = array([pid], dtype=bytes)
            preset_saved = True
        if values_id not in pval_file[ng_id][:].astype(str):
            pval_file[ng_id].resize((pval_file[ng_id].shape[0] + 1,))
            pval_file[ng_id][-1:] = array([values_id], dtype=bytes)
    return preset_saved, pname, pid


def modifier_stack_preset_processing(file, ob, preset_name, include_surface_deform=False):
    mod_stack_ids = []
    success = []
    fail = []
    get_user = lambda n: hair_factory.get_node_user(node_group=n)
    mods = ((mod for mod in ob.modifiers if (mod.type=='NODES' and mod.node_group.name.split('.')[0] != 'Surface Deform')) if not include_surface_deform else (mod for mod in ob.modifiers if mod.type=='NODES'))
    users = ((get_user(mod.node_group.name) for mod in ob.modifiers if (mod.type=='NODES' and mod.node_group.name.split('.')[0] != 'Surface Deform')) if not include_surface_deform else (get_user(mod.node_group.name) for mod in ob.modifiers if mod.type=='NODES'))
    with File(file, 'a') as hf:
        type_file = hf['PRESETS']['GEOMETRY_NODES']
        mod_stack_file = type_file["MODIFIER_STACK"]
        if preset_name in get_names(mod_stack_file):
            raise NameExistsError(f'[Preset Name] {preset_name} already exists. Please choose another name.')
        for mod in mods:
            node_group = mod.node_group
            nname = node_group.name.split('.')[0]
            preset_name_ = f"{preset_name}_{nname}"
            user_ = node_group.hf_user
            preset_saved, pname, pid = geometry_node_processing(hf, mod, preset_name_, user_)
            mod_stack_ids.append(pid)
            if preset_saved:
                success.append(pname)
            else:
                fail.append(pname)
        ms_id = hash_list(mod_stack_ids)
        if ms_id not in mod_stack_file.keys():
            mod_stack_file.create_dataset(ms_id, shape=(1, len(mod_stack_ids)), dtype=string_dtype(), data=array(mod_stack_ids, dtype=bytes), compression='gzip', compression_opts=9)
            mod_stack_file[ms_id].attrs["name"] = preset_name
            success.append(preset_name)
        else:
            fail.append(preset_name)
        return success, fail


###################################################################################

# GETTER FUNCTIONS


def get_node_data_by_id(file, id_):
    with File(file, 'r') as hf:
        return loads(hf['NODES'][id_][0])


def get_mat_presets_full_by_mat_id(file, id_):
    with File(file, 'r') as hf:
        for preset in hf['/PRESETS/MATERIALS/FULL'][id_][:].astype(str):
            yield (hf['/PRESETS/MATERIALS/TRANSACTIONS'][preset].attrs.get('name'), preset, '')


def get_mat_presets_values_by_mat_id(file, id_):
    with File(file, 'r') as hf:
        for preset in hf['/PRESETS/MATERIALS/VALUES'][id_][:].astype(str):
            yield (hf['/PRESETS/MATERIALS/DATA'][preset].attrs.get('name'), preset, '')


def get_mat_values_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        return loads(hf['/PRESETS/MATERIALS/DATA'][id_][0])


def get_mat_preset_data_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        trans = hf['/PRESETS/MATERIALS/TRANSACTIONS'][id_][0].astype(str)
        ntd = loads(hf['/PRESETS/MATERIALS/INFO'][trans[0]][0])
        nst = loads(hf['NODE_STACK'][trans[2]][0])
        ndata = {ntype: [[n, loads(hf['NODES'][nst[ntype][i]][0])] for i, n in enumerate(ntd[ntype])] for ntype in ntd}
        return {'values': loads(hf['/PRESETS/MATERIALS/DATA'][trans[1]][0]), 'nodes': ndata}


def set_mat_preset_data_by_preset_id(file, id_, material):
    with File(file, 'r') as hf:
        trans = hf['/PRESETS/MATERIALS/TRANSACTIONS'][id_][0].astype(str)
        ntd = loads(hf['/PRESETS/MATERIALS/INFO'][trans[0]][0])
        nst = loads(hf['NODE_STACK'][trans[2]][0])
        set_mat_node_data(material.name, loads(hf['/PRESETS/MATERIALS/DATA'][trans[1]][0]))
        for node_type in ntd:
            func = set_nodes_func_dict()[node_type]
            for i, node in enumerate(ntd[node_type]):
                data = loads(hf['NODES'][nst[node_type][i]][0])
                if len(node) == 1:
                    data = func(material.node_tree.nodes[node[0]], data)
                else:
                    data = func(get_mat_group_groups(material.name, node), data)


def export_mat_preset_data_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        mtrans = hf['/PRESETS/MATERIALS/TRANSACTIONS']
        minfo = hf['/PRESETS/MATERIALS/INFO']
        pname = mtrans[id_].attrs.get('name')
        trans = mtrans[id_][0].astype(str)
        mname = minfo[trans[0]].attrs.get('name')
        mclass = minfo[trans[0]].attrs.get('class')
        muser = minfo[trans[0]].attrs.get('user')
        ntd = loads(minfo[trans[0]][0])
        nst = loads(hf['NODE_STACK'][trans[2]][0])
        ndata = {ntype: [[n, loads(hf['NODES'][nst[ntype][i]][0]), hf['NODES'][nst[ntype][i]].attrs.get('name'), nst[ntype][i]] for i, n in enumerate(ntd[ntype])] for ntype in ntd}
        return {
            'name': pname, 
            'id': id_, 
            'transaction': trans, 
            'group': {'name': mname, 'class': mclass, 'user': muser}, 
            'node_stack': nst, 
            'data': {'values': loads(hf['/PRESETS/MATERIALS/DATA'][trans[1]][0]), 'nodes': ndata},
            }


def get_gn_presets_full_by_gn_id(file, id_):
    with File(file, 'r') as hf:
        for preset in hf['/PRESETS/GEOMETRY_NODES/FULL'][id_][:].astype(str):
            yield (hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][preset].attrs.get('name'), preset, '')


def get_gn_presets_values_by_gn_id(file, id_):
    with File(file, 'r') as hf:
        for preset in hf['/PRESETS/GEOMETRY_NODES/VALUES'][id_][:].astype(str):
            yield (hf['/PRESETS/GEOMETRY_NODES/DATA'][preset].attrs.get('name'), preset, '')


def get_gn_values_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        return loads(hf['/PRESETS/GEOMETRY_NODES/DATA'][id_][0])


def get_gn_preset_data_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        trans = hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][id_][0].astype(str)
        ntd = loads(hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]][0])
        nst = loads(hf['NODE_STACK'][trans[2]][0])
        ndata = {ntype: [[n, loads(hf['NODES'][nst[ntype][i]][0])] for i, n in enumerate(ntd[ntype])] for ntype in ntd}
        return {'values': loads(hf['DATA'][trans[1]][0]), 'nodes': ndata}


def load_mod_stack_preset_data_by_preset_id(file, id_):
    with File(file, 'r') as hf:
       return hf['/PRESETS/GEOMETRY_NODES/MODIFIER_STACK'][id_][0].astype(str)


def get_node_group_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        ng = hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][id_][0].astype(str)[0]
        name = hf['/PRESETS/GEOMETRY_NODES/INFO'][ng].attrs.get('name')
        user = hf['/PRESETS/GEOMETRY_NODES/INFO'][ng].attrs.get('user')
        return name, user


def load_mod_stack_by_preset_id(zip_file, preset_file, id_):
    presets = get_from_zip(zip_file, preset_file, False, load_mod_stack_preset_data_by_preset_id, id_)
    for preset in presets:
        name, user = get_from_zip(zip_file, preset_file, False, get_node_group_by_preset_id, preset)
        if user == 'HAIR_FACTORY':
            hair_factory.load_hair_factory_node(name=name)
        if user == 'BLENDER':
            hair_factory.load_geometry_node(name=name)
        if user == 'USER':
            hair_factory.load_user_node(name=name)
        get_from_zip(zip_file, preset_file, False, set_node_group_preset_data_by_preset_id, bpy.context.object.modifiers.active, preset)


###################################################################################

# SETTER FUNCTIONS

def set_node_group_values(node_group, data):
    items_tree = node_group.interface.items_tree
    for item in data:
        items_tree[item].default_value = data[item]


def set_gn_preset_data_by_preset_id(file, id_, node_group):
    with File(file, 'r') as hf:
        trans = hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][id_][0].astype(str)
        ntd = loads(hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]][0])
        nst = loads(hf['NODE_STACK'][trans[2]][0])
        set_node_group_values(node_group, loads(hf['/PRESETS/GEOMETRY_NODES/DATA'][trans[1]][0]))
        for node_type in ntd:
            func = set_nodes_func_dict()[node_type]
            for i, node in enumerate(ntd[node_type]):
                data = loads(hf['NODES'][nst[node_type][i]][0])
                if len(node) == 1:
                    data = func(node_group.nodes[node[0]], data)
                else:
                    data = func(get_node_group_groups(node_group.name, node), data)


###################################################################################

# EXPORT FUNCTIONS

def export_gn_preset_data_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        pname = hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][id_].attrs.get('name')
        trans = hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][id_][0].astype(str)
        gname = hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]].attrs.get('name')
        gclass = hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]].attrs.get('class')
        guser = hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]].attrs.get('user')
        ntd = loads(hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]][0])
        nst = loads(hf['NODE_STACK'][trans[2]][0])
        ndata = {ntype: [[n, loads(hf['NODES'][nst[ntype][i]][0]), hf['NODES'][nst[ntype][i]].attrs.get('name'), nst[ntype][i]] for i, n in enumerate(ntd[ntype])] for ntype in ntd}
        return {
            'name': pname, 
            'id': id_, 
            'transaction': trans, 
            'group': {'name': gname, 'class': gclass, 'user': guser}, 
            'node_stack': nst, 
            'data': {'values': loads(hf['/PRESETS/GEOMETRY_NODES/DATA'][trans[1]][0]), 'nodes': ndata},
            }


def export_mod_stack_preset_data_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        data = hf['/PRESETS/GEOMETRY_NODES/MODIFIER_STACK'][id_][:].astype(str)[0]
        name = hf['/PRESETS/GEOMETRY_NODES/MODIFIER_STACK'][id_].attrs.get('name')
        data_dict = {'name': name, 'id': id_, 'data': {i:{} for i in data}}
        for i_ in data:
            pname = hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][i_].attrs.get('name')
            trans = hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][i_][0].astype(str)
            gname = hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]].attrs.get('name')
            gclass = hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]].attrs.get('class')
            guser = hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]].attrs.get('user')
            ntd = loads(hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]][0])
            nst = loads(hf['NODE_STACK'][trans[2]][0])
            ndata = {ntype: [[n, loads(hf['NODES'][nst[ntype][i]][0]), hf['NODES'][nst[ntype][i]].attrs.get('name'), nst[ntype][i]] for i, n in enumerate(ntd[ntype])] for ntype in ntd}
            data_dict['data'][i_] = {
                'name': pname, 
                'id': i_, 
                'transaction': trans, 
                'group': {'name': gname, 'class': gclass, 'user': guser}, 
                'node_stack': nst, 
                'data': {'values': loads(hf['/PRESETS/GEOMETRY_NODES/DATA'][trans[1]][0]), 'nodes': ndata},
                }
        return data_dict


def export_node_preset_data_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        node = hf['NODES'][id_]
        return {
            'id': id_, 
            'name': node.attrs.get('name'), 
            'type': node.attrs.get('type'), 
            'data': loads(node[0])
            }


###################################################################################

# JSON FUNCTIONS

def preset_list_array(data_gen):
    return array([*data_gen], dtype=[('name', StrDType),('id', StrDType),('description', StrDType)])


class NUMPYEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, integer):
            return int(obj)
        if isinstance(obj, floating):
            return float(obj)
        if isinstance(obj, ndarray):
            return obj.tolist()
        else:
            return super(NUMPYEncoder, self).default(obj)


def write_json(file, data):
    with open(file, 'w') as jf:
        dump(data, jf)


def read_json(file):
    with open(file, 'r') as jf:
        data = jload(jf)
        return data


###################################################################################

# IMPORT FUNCTIONS

def import_mat_preset_data(file, preset_data):
    preset_saved = False
    pname = None
    preset_name = preset_data['name']
    pid = preset_data['id']
    mat_id = preset_data['transaction'][0]
    mat_name = preset_data['group']['name']
    mat_class = preset_data['group']['class']
    mat_user = preset_data['group']['user']
    node_values = preset_data['data']['values']
    values_id = preset_data['transaction'][1]
    ni_id = preset_data['transaction'][2]
    node_stack = preset_data['node_stack']
    nodes = preset_data['data']['nodes']
    # FILES
    with File(file, 'a') as hf:
        type_file = hf['PRESETS']['MATERIALS']
        info_file = type_file['INFO']
        data_file = type_file['DATA']
        node_file = hf['NODES']
        node_stack_file = hf['NODE_STACK']
        trans_file = type_file['TRANSACTIONS']
        if (pid in trans_file.keys()):
            return preset_saved, trans_file[pid].attrs.get('name')
        if (preset_name in get_names(trans_file)):
            preset_name = get_match_series_highest(preset_name, get_names(trans_file))
        # TRANSACTIONS
        pdata = trans_file.create_dataset(pid, shape=(1, 3), dtype=string_dtype(), data=array([mat_id, values_id, ni_id], dtype=bytes), compression='gzip', compression_opts=9)
        pdata.attrs['name'] = preset_name
        preset_saved = True
        pname = pdata.attrs.get('name')
        # INFO
        if (mat_id not in info_file.keys()):
            ntd = {n: [d[:2] for d in nodes[n]] for n in nodes}
            minfo = info_file.create_dataset(mat_id, shape=(1,), dtype=string_dtype(), data=array([dumps(ntd)], dtype=bytes), compression='gzip', compression_opts=9)
            minfo.attrs['name'] = mat_name
            minfo.attrs['class'] = mat_class
            minfo.attrs['user'] = mat_user
        # DATA
        if (values_id not in data_file.keys()):
            mdata = data_file.create_dataset(values_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_values)], dtype=bytes), compression='gzip', compression_opts=9)
            values_name = preset_name
            if values_name in get_names(data_file):
                values_name = get_match_series_highest(values_name, get_names(data_file))
            mdata.attrs['name'] = values_name
        # NODES
        for node_type in nodes:
            ngroup_name = f'/PRESETS/{node_type}'
            ct = hf[ngroup_name].len()
            for node in nodes[node_type]:
                abbr = node_type_abbr_dict()[node_type]
                data = node[2]
                nid = node[4]
                if (nid not in node_file.keys()):
                    ndata = node_file.create_dataset(nid, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
                    suggested_name = node[3]
                    if suggested_name in get_names(node_file):
                        suggested_name = get_match_series_highest(suggested_name, get_names(node_file))
                    ndata.attrs['name'] = suggested_name
                    ndata.attrs['type'] = f'{node_type}'
                    ct += 1
                if nid not in hf[ngroup_name][:].astype(str):
                    hf[ngroup_name].resize((hf[ngroup_name].shape[0] + 1,))
                    hf[ngroup_name][-1:] = array([nid], dtype=bytes)
        if (ni_id not in node_stack_file.keys()):
            node_ids = {n: [d[4] for d in nodes[n]] for n in nodes}
            nid_data = node_stack_file.create_dataset(ni_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_ids)], dtype=bytes), compression='gzip', compression_opts=9)
        # LINKS
        pful_name = '/PRESETS/MATERIALS/FULL'
        pval_name = '/PRESETS/MATERIALS/VALUES'
        pful_file = hf[pful_name]
        pval_file = hf[pval_name]
        if mat_id not in pful_file.keys():
            pf_data = pful_file.create_dataset(mat_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([pid], dtype=bytes), compression='gzip', compression_opts=9)
            pv_data = pval_file.create_dataset(mat_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([values_id], dtype=bytes), compression='gzip', compression_opts=9)
        else:
            if pid not in pful_file[mat_id][:].astype(str):
                pful_file[mat_id].resize((pful_file[mat_id].shape[0] + 1,))
                pful_file[mat_id][-1:] = array([pid], dtype=bytes)
            if values_id not in pval_file[mat_id][:].astype(str):
                pval_file[mat_id].resize((pval_file[mat_id].shape[0] + 1,))
                pval_file[mat_id][-1:] = array([values_id], dtype=bytes)
    return preset_saved, pname


def import_node_preset_data(file, preset_data):
    preset_saved = False
    suggested_name = preset_data['name']
    nid = preset_data['id']
    node_type = preset_data['type']
    data = preset_data['data']
    # FILES
    with File(file, 'a') as hf:
        node_file = hf['NODES']
        ngroup_name = f'/PRESETS/{node_type}'
        if (nid not in node_file.keys()):
            ndata = node_file.create_dataset(nid, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
            if suggested_name in get_names(node_file):
                suggested_name = get_match_series_highest(suggested_name, get_names(node_file))
            ndata.attrs['name'] = suggested_name
            ndata.attrs['type'] = f'{node_type}'
            preset_saved = True
        suggested_name = node_file[nid].attrs.get('name')
        if nid not in hf[ngroup_name][:].astype(str):
            hf[ngroup_name].resize((hf[ngroup_name].shape[0] + 1,))
            hf[ngroup_name][-1:] = array([nid], dtype=bytes)
        return preset_saved, suggested_name


def import_gn_preset_data(file, preset_data):
    preset_saved = False
    pname = None
    preset_name = preset_data['name']
    pid = preset_data['id']
    ng_id = preset_data['transaction'][0]
    gn_name = preset_data['group']['name']
    gn_class = preset_data['group']['class']
    gn_user = preset_data['group']['user']
    node_values = preset_data['data']['values']
    values_id = preset_data['transaction'][1]
    ni_id = preset_data['transaction'][2]
    node_stack = preset_data['node_stack']
    nodes = preset_data['data']['nodes']
    # FILES
    with File(file, 'a') as hf:
        type_file = hf['PRESETS']['GEOMETRY_NODES']
        info_file = type_file['INFO']
        data_file = type_file['DATA']
        node_file = hf['NODES']
        node_stack_file = hf['NODE_STACK']
        trans_file = type_file['TRANSACTIONS']
        if (pid in trans_file.keys()):
            return preset_saved, trans_file[pid].attrs.get('name')
        if (preset_name in get_names(trans_file)):
            preset_name = get_match_series_highest(preset_name, get_names(trans_file))
        # TRANSACTIONS
        pdata = trans_file.create_dataset(pid, shape=(1, 3), dtype=string_dtype(), data=array([ng_id, values_id, ni_id], dtype=bytes), compression='gzip', compression_opts=9)
        pdata.attrs['name'] = preset_name
        preset_saved = True
        pname = pdata.attrs.get('name')
        # INFO
        if (ng_id not in info_file.keys()):
            ntd = {n: [d[:2] for d in nodes[n]] for n in nodes}
            minfo = info_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), data=array([dumps(ntd)], dtype=bytes), compression='gzip', compression_opts=9)
            minfo.attrs['name'] = gn_name
            minfo.attrs['class'] = gn_class
            minfo.attrs['user'] = gn_user
        # DATA
        if (values_id not in data_file.keys()):
            mdata = data_file.create_dataset(values_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_values)], dtype=bytes), compression='gzip', compression_opts=9)
            values_name = preset_name
            if values_name in get_names(data_file):
                values_name = get_match_series_highest(values_name, get_names(data_file))
            mdata.attrs['name'] = values_name
        # NODES
        for node_type in nodes:
            ngroup_name = f'/PRESETS/{node_type}'
            ct = hf[ngroup_name].len()
            for node in nodes[node_type]:
                abbr = node_type_abbr_dict()[node_type]
                data = node[2]
                nid = node[4]
                if (nid not in node_file.keys()):
                    ndata = node_file.create_dataset(nid, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
                    suggested_name = node[3]
                    if suggested_name in get_names(node_file):
                        suggested_name = get_match_series_highest(suggested_name, get_names(node_file))
                    ndata.attrs['name'] = suggested_name
                    ndata.attrs['type'] = f'{node_type}'
                    ct += 1
                if nid not in hf[ngroup_name][:].astype(str):
                    hf[ngroup_name].resize((hf[ngroup_name].shape[0] + 1,))
                    hf[ngroup_name][-1:] = array([nid], dtype=bytes)
        if (ni_id not in node_stack_file.keys()):
            node_ids = {n: [d[4] for d in nodes[n]] for n in nodes}
            nid_data = node_stack_file.create_dataset(ni_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_ids)], dtype=bytes), compression='gzip', compression_opts=9)
        # LINKS
        pful_name = '/PRESETS/GEOMETRY_NODES/FULL'
        pval_name = '/PRESETS/GEOMETRY_NODES/VALUES'
        pful_file = hf[pful_name]
        pval_file = hf[pval_name]
        if ng_id not in pful_file.keys():
            pf_data = pful_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([pid], dtype=bytes), compression='gzip', compression_opts=9)
            pv_data = pval_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([values_id], dtype=bytes), compression='gzip', compression_opts=9)
        else:
            if pid not in pful_file[ng_id][:].astype(str):
                pful_file[ng_id].resize((pful_file[ng_id].shape[0] + 1,))
                pful_file[ng_id][-1:] = array([pid], dtype=bytes)
            if values_id not in pval_file[ng_id][:].astype(str):
                pval_file[ng_id].resize((pval_file[ng_id].shape[0] + 1,))
                pval_file[ng_id][-1:] = array([values_id], dtype=bytes)
    return preset_saved, pname


def import_mod_stack_preset_data(file, preset_data):
    success = []
    fail = []
    stack_preset_name = preset_data['name']
    ms_id = preset_data['id']
    ng_data = preset_data['data']
    with File(file, 'a') as hf:
        type_file = hf['PRESETS']['GEOMETRY_NODES']
        mod_stack_file = type_file["MODIFIER_STACK"]
        info_file = type_file['INFO']
        data_file = type_file['DATA']
        node_file = hf['NODES']
        node_stack_file = hf['NODE_STACK']
        trans_file = type_file['TRANSACTIONS']
        #
        if (ms_id in mod_stack_file.keys()):
            return [], [ng_data[i]['name'] for i in ng_data]
        if (stack_preset_name in get_names(mod_stack_file)):
            stack_preset_name = get_match_series_highest(stack_preset_name, get_names(mod_stack_file))
        if ms_id not in mod_stack_file.keys():
            mod_stack_ids = list(ng_data.keys())
            mod_stack_file.create_dataset(ms_id, shape=(1, len(mod_stack_ids)), dtype=string_dtype(), data=array(mod_stack_ids, dtype=bytes), compression='gzip', compression_opts=9)
            mod_stack_file[ms_id].attrs["name"] = stack_preset_name
            success.append(stack_preset_name)
        else:
            fail.append(stack_preset_name)
        #
        for id_ in ng_data:
            p_data = ng_data[id_]
            preset_name = p_data['name']
            pid = p_data['id']
            ng_id = p_data['transaction'][0]
            gn_name = p_data['group']['name']
            gn_class = p_data['group']['class']
            gn_user = p_data['group']['user']
            node_values = p_data['data']['values']
            values_id = p_data['transaction'][1]
            ni_id = p_data['transaction'][2]
            node_stack = p_data['node_stack']
            nodes = p_data['data']['nodes']
            #
            preset_saved = False
            pname = None
            if (pid in trans_file.keys()):
                fail.append(trans_file[pid].attrs.get('name'))
            else:
                if (preset_name in get_names(trans_file)):
                    preset_name = get_match_series_highest(preset_name, get_names(trans_file))
                # TRANSACTIONS
                pdata = trans_file.create_dataset(pid, shape=(1, 3), dtype=string_dtype(), data=array([ng_id, values_id, ni_id], dtype=bytes), compression='gzip', compression_opts=9)
                pdata.attrs['name'] = preset_name
                preset_saved = True
                pname = pdata.attrs.get('name')
                # INFO
                if (ng_id not in info_file.keys()):
                    ntd = {n: [d[:2] for d in nodes[n]] for n in nodes}
                    minfo = info_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), data=array([dumps(ntd)], dtype=bytes), compression='gzip', compression_opts=9)
                    minfo.attrs['name'] = gn_name
                    minfo.attrs['class'] = gn_class
                    minfo.attrs['user'] = gn_user
                # DATA
                if (values_id not in data_file.keys()):
                    mdata = data_file.create_dataset(values_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_values)], dtype=bytes), compression='gzip', compression_opts=9)
                    values_name = preset_name
                    if values_name in get_names(data_file):
                        values_name = get_match_series_highest(values_name, get_names(data_file))
                    mdata.attrs['name'] = values_name
                # NODES
                for node_type in nodes:
                    ngroup_name = f'/PRESETS/{node_type}'
                    ct = hf[ngroup_name].len()
                    for node in nodes[node_type]:
                        abbr = node_type_abbr_dict()[node_type]
                        data = node[2]
                        nid = node[4]
                        if (nid not in node_file.keys()):
                            ndata = node_file.create_dataset(nid, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
                            suggested_name = node[3]
                            if suggested_name in get_names(node_file):
                                suggested_name = get_match_series_highest(suggested_name, get_names(node_file))
                            ndata.attrs['name'] = suggested_name
                            ndata.attrs['type'] = f'{node_type}'
                            ct += 1
                        if nid not in hf[ngroup_name][:].astype(str):
                            hf[ngroup_name].resize((hf[ngroup_name].shape[0] + 1,))
                            hf[ngroup_name][-1:] = array([nid], dtype=bytes)
                if (ni_id not in node_stack_file.keys()):
                    node_ids = {n: [d[4] for d in nodes[n]] for n in nodes}
                    nid_data = node_stack_file.create_dataset(ni_id, shape=(1,), dtype=string_dtype(), data=array([dumps(node_ids)], dtype=bytes), compression='gzip', compression_opts=9)
                # LINKS
                pful_name = '/PRESETS/GEOMETRY_NODES/FULL'
                pval_name = '/PRESETS/GEOMETRY_NODES/VALUES'
                pful_file = hf[pful_name]
                pval_file = hf[pval_name]
                if ng_id not in pful_file.keys():
                    pf_data = pful_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([pid], dtype=bytes), compression='gzip', compression_opts=9)
                    pv_data = pval_file.create_dataset(ng_id, shape=(1,), dtype=string_dtype(), maxshape=(None,), data=array([values_id], dtype=bytes), compression='gzip', compression_opts=9)
                else:
                    if pid not in pful_file[ng_id][:].astype(str):
                        pful_file[ng_id].resize((pful_file[ng_id].shape[0] + 1,))
                        pful_file[ng_id][-1:] = array([pid], dtype=bytes)
                    if values_id not in pval_file[ng_id][:].astype(str):
                        pval_file[ng_id].resize((pval_file[ng_id].shape[0] + 1,))
                        pval_file[ng_id][-1:] = array([values_id], dtype=bytes)
            if preset_saved:
                success.append(pname)
            else:
                fail.append(pname)
    return success, fail


def import_phy_data(file, preset_data):
    preset_saved = False
    pname = None
    phy_id = preset_data['id']
    preset_name = preset_data['name']
    ptype = preset_data['ptype']
    data = preset_data['data']
    with File(file, 'a') as hf:
        trans_file = hf['PHYSICS'][ptype]
        if preset_name in get_names(trans_file):
            preset_name = get_match_series_highest(preset_name, get_names(trans_file))
        if (phy_id not in trans_file.keys()):
            pdata = trans_file.create_dataset(phy_id, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
            pdata.attrs['name'] = preset_name
            preset_saved = True
            pname = preset_name
        else:
            pname = trans_file[phy_id].attrs.get('name')
    return preset_saved, pname


def import_collision_data(file, preset_data):
    preset_saved = False
    pname = None
    phy_id = preset_data['id']
    preset_name = preset_data['name']
    data = preset_data['data']
    with File(file, 'a') as hf:
        trans_file = hf['PHYSICS']['COLLISION']
        if preset_name in get_names(trans_file):
            preset_name = get_match_series_highest(preset_name, get_names(trans_file))
        if (phy_id not in trans_file.keys()):
            pdata = trans_file.create_dataset(phy_id, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
            pdata.attrs['name'] = preset_name
            preset_saved = True
            pname = preset_name
        else:
            pname = trans_file[phy_id].attrs.get('name')
    return preset_saved, pname


def import_hair_data(file, preset_data):
    preset_saved = False
    pname = None
    h_id = preset_data['id']
    preset_name = preset_data['name']
    points = preset_data['points']
    sizes = preset_data['sizes']
    with File(file, 'a') as hf:
        points_file = hf['HAIR']['POINTS']
        sizes_file = hf['HAIR']['SIZES']
        if preset_name in get_names(points_file):
            preset_name = get_match_series_highest(preset_name, get_names(trans_file))
        if (h_id not in points_file.keys()):
            pdata = points_file.create_dataset(h_id, len(points), dtype='f2', data=array(points), compression='gzip', compression_opts=9)
            pdata.attrs['name'] = preset_name
            sdata = sizes_file.create_dataset(h_id, shape=len(sizes), dtype='u2', data=array(sizes), compression='gzip', compression_opts=9)
            preset_saved = True
            pname = preset_name
        else:
            pname = points_file[h_id].attrs.get('name')
    return preset_saved, pname


def double_toggle():
    bpy.ops.object.editmode_toggle()
    bpy.ops.object.editmode_toggle()


def import_func_dict():
    return {
        'Material': import_mat_preset_data,
        'Node': import_node_preset_data,
        'Geometry_Node': import_gn_preset_data,
        'Modifier_Stack': import_mod_stack_preset_data,
        'Physics': import_phy_data,
        'Collision': import_collision_data,
        'Hair': import_hair_data,
    }


###################################################################################

# PHYSICS FUNCTIONS


def get_cloth_settings(ob):
    phy = next((m for m in ob.modifiers if m.type=="CLOTH"))
    settings = phy.settings
    collision_settings = phy.collision_settings
    data = {
        'quality': settings.quality,
        'time_scale': settings.time_scale,
        'mass': settings.mass,
        'air_damping': settings.air_damping,
        'bending_model': settings.bending_model,
        'tension_stiffness': settings.tension_stiffness,
        'shear_stiffness': settings.shear_stiffness,
        'bending_stiffness': settings.bending_stiffness,
        'tension_damping': settings.tension_damping,
        'shear_damping': settings.shear_damping,
        'bending_damping': settings.bending_damping,
        'use_internal_springs': settings.use_internal_springs,
        'internal_spring_max_length': settings.internal_spring_max_length,
        'internal_spring_max_diversion': settings.internal_spring_max_diversion,
        'internal_spring_normal_check': settings.internal_spring_normal_check,
        'internal_tension_stiffness': settings.internal_tension_stiffness,
        'internal_compression_stiffness': settings.internal_compression_stiffness,
        'vertex_group_intern': settings.vertex_group_intern,
        'internal_tension_stiffness_max': settings.internal_tension_stiffness_max,
        'internal_compression_stiffness_max': settings.internal_compression_stiffness_max,
        'use_pressure': settings.use_pressure,
        'uniform_pressure_force': settings.uniform_pressure_force,
        'use_pressure_volume': settings.use_pressure_volume,
        'target_volume': settings.target_volume,
        'pressure_factor': settings.pressure_factor,
        'fluid_density': settings.fluid_density,
        'vertex_group_pressure': settings.vertex_group_pressure,
        'vertex_group_mass': settings.vertex_group_mass,
        'pin_stiffness': settings.pin_stiffness,
        'use_collision': collision_settings.use_collision,
        'collision_quality': collision_settings.collision_quality,
        'distance_min': collision_settings.distance_min,
        'impulse_clamp': collision_settings.impulse_clamp,
        'vertex_group_object_collisions': collision_settings.vertex_group_object_collisions,
        'use_self_collision': collision_settings.use_self_collision,
        'self_distance_min': collision_settings.self_distance_min,
        'self_impulse_clamp': collision_settings.self_impulse_clamp,
        'vertex_group_self_collisions': collision_settings.vertex_group_self_collisions,
    }
    if settings.bending_model == 'ANGULAR':
        data.update({'compression_stiffness': settings.compression_stiffness, 'compression_damping': settings.compression_damping})
    return data


def set_cloth_settings(ob, data):
    phy = next((m for m in ob.modifiers if m.type=="CLOTH"))
    settings = phy.settings
    collision_settings = phy.collision_settings
    settings.quality = data['quality']
    settings.time_scale = data['time_scale']
    settings.mass = data['mass']
    settings.air_damping = data['air_damping']
    settings.bending_model = data['bending_model']
    settings.tension_stiffness = data['tension_stiffness']
    settings.shear_stiffness = data['shear_stiffness']
    settings.bending_stiffness = data['bending_stiffness']
    settings.tension_damping = data['tension_damping']
    settings.shear_damping = data['shear_damping']
    settings.bending_damping = data['bending_damping']
    settings.use_internal_springs = data['use_internal_springs']
    settings.internal_spring_max_length = data['internal_spring_max_length']
    settings.internal_spring_max_diversion = data['internal_spring_max_diversion']
    settings.internal_spring_normal_check = data['internal_spring_normal_check']
    settings.internal_tension_stiffness = data['internal_tension_stiffness']
    settings.internal_compression_stiffness = data['internal_compression_stiffness']
    settings.vertex_group_intern = data['vertex_group_intern']
    settings.internal_tension_stiffness_max = data['internal_tension_stiffness_max']
    settings.internal_compression_stiffness_max = data['internal_compression_stiffness_max']
    settings.use_pressure = data['use_pressure']
    settings.uniform_pressure_force = data['uniform_pressure_force']
    settings.use_pressure_volume = data['use_pressure_volume']
    settings.target_volume = data['target_volume']
    settings.pressure_factor = data['pressure_factor']
    settings.fluid_density = data['fluid_density']
    settings.vertex_group_pressure = data['vertex_group_pressure']
    settings.vertex_group_mass = data['vertex_group_mass']
    settings.pin_stiffness = data['pin_stiffness']
    collision_settings.use_collision = data['use_collision']
    collision_settings.collision_quality = data['collision_quality']
    collision_settings.distance_min = data['distance_min']
    collision_settings.impulse_clamp = data['impulse_clamp']
    collision_settings.vertex_group_object_collisions = data['vertex_group_object_collisions']
    collision_settings.use_self_collision = data['use_self_collision']
    collision_settings.self_distance_min = data['self_distance_min']
    collision_settings.self_impulse_clamp = data['self_impulse_clamp']
    collision_settings.vertex_group_self_collisions = data['vertex_group_self_collisions']
    if data['bending_model'] == 'ANGULAR':
        settings.compression_stiffness = data['compression_stiffness']
        settings.compression_damping = data['compression_damping']



def get_soft_body_settings(ob):
    phy = next((m for m in ob.modifiers if m.type=="SOFT_BODY"))
    settings = phy.settings
    data = {
        'friction': settings.friction,
        'mass': settings.mass,
        'vertex_group_mass': settings.vertex_group_mass,
        'speed': settings.speed,
        'use_goal': settings.use_goal,
        'vertex_group_goal': settings.vertex_group_goal,
        'goal_spring': settings.goal_spring,
        'goal_friction': settings.goal_friction,
        'goal_default': settings.goal_default,
        'goal_min': settings.goal_min,
        'goal_max': settings.goal_max,
        'use_edges': settings.use_edges,
        'vertex_group_spring': settings.vertex_group_spring,
        'pull': settings.pull,
        'push': settings.push,
        'damping': settings.damping,
        'plastic': settings.plastic,
        'bend': settings.bend,
        'spring_length': settings.spring_length,
        'use_edge_collision': settings.use_edge_collision,
        'use_face_collision': settings.use_face_collision,
        'aerodynamics_type': settings.aerodynamics_type,
        'aero': settings.aero,
        'use_stiff_quads': settings.use_stiff_quads,
        'shear': settings.shear,
        'use_self_collision': settings.use_self_collision,
        'collision_type': settings.collision_type,
        'ball_size': settings.ball_size,
        'ball_stiff': settings.ball_stiff,
        'ball_damp': settings.ball_damp,
        'step_min': settings.step_min,
        'step_max': settings.step_max,
        'use_auto_step': settings.use_auto_step,
        'error_threshold': settings.error_threshold,
        'choke': settings.choke,
        'fuzzy': settings.fuzzy,
    }
    return data


def set_soft_body_settings(ob, data):
    phy = next((m for m in ob.modifiers if m.type=="SOFT_BODY"))
    settings = phy.settings
    settings.friction = data['friction']
    settings.mass = data['mass']
    settings.vertex_group_mass = data['vertex_group_mass']
    settings.speed = data['speed']
    settings.use_goal = data['use_goal']
    settings.vertex_group_goal = data['vertex_group_goal']
    settings.goal_spring = data['goal_spring']
    settings.goal_friction = data['goal_friction']
    settings.goal_default = data['goal_default']
    settings.goal_min = data['goal_min']
    settings.goal_max = data['goal_max']
    settings.use_edges = data['use_edges']
    settings.vertex_group_spring = data['vertex_group_spring']
    settings.pull = data['pull']
    settings.push = data['push']
    settings.damping = data['damping']
    settings.plastic = data['plastic']
    settings.bend = data['bend']
    settings.spring_length = data['spring_length']
    settings.use_edge_collision = data['use_edge_collision']
    settings.use_face_collision = data['use_face_collision']
    settings.aerodynamics_type = data['aerodynamics_type']
    settings.aero = data['aero']
    settings.use_stiff_quads = data['use_stiff_quads']
    settings.shear = data['shear']
    settings.use_self_collision = data['use_self_collision']
    settings.collision_type = data['collision_type']
    settings.ball_size = data['ball_size']
    settings.ball_stiff = data['ball_stiff']
    settings.ball_damp = data['ball_damp']
    settings.step_min = data['step_min']
    settings.step_max = data['step_max']
    settings.use_auto_step = data['use_auto_step']
    settings.error_threshold = data['error_threshold']
    settings.choke = data['choke']
    settings.fuzzy = data['fuzzy']


def get_collision_settings(ob):
    collision = ob.collision
    data = {
        'absorption': collision.absorption,
        'thickness_outer': collision.thickness_outer,
        'damping': collision.damping,
        'cloth_friction': collision.cloth_friction,
    }
    return data


def set_collision_settings(ob, data):
    collision = ob.collision
    collision.absorption = data['absorption']
    collision.thickness_outer = data['thickness_outer']
    collision.damping = data['damping']
    collision.cloth_friction = data['cloth_friction']



def physics_preset_processing(file, ptype, data, preset_name):
    preset_saved = False
    pname = None
    with File(file, 'a') as hf:
        trans_file = hf['PHYSICS'][ptype]
        if preset_name in get_names(trans_file):
            raise NameExistsError(f'[Preset Name] {preset_name} already exists. Please choose another name.')
        phy_id = hash_dict(data)
        if (phy_id not in trans_file.keys()):
            pdata = trans_file.create_dataset(phy_id, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
            pdata.attrs['name'] = preset_name
            preset_saved = True
            pname = preset_name
        else:
            pname = trans_file[phy_id].attrs.get('name')
    return preset_saved, pname


def set_phy_preset_data_by_preset_id(file, id_, ob, ptype):
    with File(file, 'r') as hf:
        data = hf[f'/PHYSICS/{ptype}'][id_][:].astype(str)[0]
        (set_cloth_settings(ob['PHY_MESH'], loads(data)) if ptype == 'CLOTH' else set_soft_body_settings(ob['PHY_MESH'], loads(data)))


def export_phy_preset_data_by_preset_id(file, id_, ptype):
    with File(file, 'r') as hf:
        data = hf[f'/PHYSICS/{ptype}'][id_][:].astype(str)[0]
        name = hf[f'/PHYSICS/{ptype}'][id_].attrs.get('name')
        return {
            'id': id_,
            'name': name,
            'ptype': ptype,
            'data': loads(data),
            }


def collision_preset_processing(file, data, preset_name):
    preset_saved = False
    pname = None
    with File(file, 'a') as hf:
        trans_file = hf['PHYSICS']['COLLISION']
        if preset_name in get_names(trans_file):
            raise NameExistsError(f'[Preset Name] {preset_name} already exists. Please choose another name.')
        phy_id = hash_dict(data)
        if (phy_id not in trans_file.keys()):
            pdata = trans_file.create_dataset(phy_id, shape=(1,), dtype=string_dtype(), data=array([dumps(data)], dtype=bytes), compression='gzip', compression_opts=9)
            pdata.attrs['name'] = preset_name
            preset_saved = True
            pname = preset_name
        else:
            pname = trans_file[phy_id].attrs.get('name')
    return preset_saved, pname


def set_col_preset_data_by_preset_id(file, id_, ob):
    with File(file, 'r') as hf:
        data = hf[f'/PHYSICS/COLLISION'][id_][:].astype(str)[0]
        set_collision_settings(ob.parent, loads(data))


def export_col_preset_data_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        data = hf[f'/PHYSICS/COLLISION'][id_][:].astype(str)[0]
        name = hf[f'/PHYSICS/COLLISION'][id_].attrs.get('name')
        return {
            'id': id_,
            'name': name,
            'data': loads(data),
            }


###################################################################################

# HAIR FUNCTIONS

def hair_preset_processing(file, data, preset_name):
    preset_saved = False
    pname = None
    with File(file, 'a') as hf:
        points_file = hf['HAIR']['POINTS']
        sizes_file = hf['HAIR']['SIZES']
        if preset_name in get_names(points_file):
            raise NameExistsError(f'[Preset Name] {preset_name} already exists. Please choose another name.')
        h_id = hash_dict(data)
        if (h_id not in points_file.keys()):
            pdata = points_file.create_dataset(h_id, shape=data['points'].shape, dtype='f2', data=data['points'], compression='gzip', compression_opts=9)
            pdata.attrs['name'] = preset_name
            sdata = sizes_file.create_dataset(h_id, shape=data['sizes'].shape, dtype='u2', data=data['sizes'], compression='gzip', compression_opts=9)
            preset_saved = True
            pname = preset_name
        else:
            pname = points_file[h_id].attrs.get('name')
    return preset_saved, pname


def set_hair_preset_data_by_preset_id(file, id_, ob):
    with File(file, 'r') as hf:
        points = hf[f'/HAIR/POINTS'][id_][:]
        name = hf[f'/HAIR/POINTS'][id_].attrs.get('name')
        sizes = hf[f'/HAIR/SIZES'][id_][:]
        return create_hair_curve(name, ob, points=points, sizes=sizes)


def export_hair_preset_data_by_preset_id(file, id_):
    with File(file, 'r') as hf:
        data = {
            'id': id_,
            'name': hf[f'/HAIR/POINTS'][id_].attrs.get('name'),
            'points': hf[f'/HAIR/POINTS'][id_][:],
            'sizes': hf[f'/HAIR/SIZES'][id_][:],
        }
        return data



#######################################################################################


# NODE OPERATORS

class HAIRFACTORY_OT_save_node(Operator):
    """
    """
    bl_idname = "hair_factory.save_node"
    bl_label = "Save Node Data"
    bl_description = "Save node data."
    bl_options = {'REGISTER', 'UNDO'}
    
    node: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set
    
    def execute(self, context):
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        node = eval(self.node)
        node_tree, classification, mat_name = get_node_source_data(node)
        if not node_tree:
            self.report({'ERROR'}, f"Node: {node.name} node_tree not found!")
            return {'CANCELLED'}
        preset_name = node.hf_node_preset_name
        if is_string_blank(preset_name):
            self.report({'ERROR'}, f"Preset name missing.")
            return {'CANCELLED'}
        if string_has_space(preset_name) or string_startswith_space(preset_name):
            self.report({'ERROR'}, f"Preset name contains spaces.")
            return {'CANCELLED'}
        if preset_name.upper() == 'NONE':
            self.report({'ERROR'}, f"Preset name can not be used")
            return {'CANCELLED'}
        try:
            result = modify_in_zip(zip_file, preset_file, node_preset_processing, node, node_tree, preset_name, classification=classification, mat_name=mat_name)
        except NameExistsError as ne_error:
            self.report({'ERROR'}, f"{ne_error}")
            return {'CANCELLED'}
        if result == None:
            self.report({'ERROR'}, f"Preset for Node {node.name} was not saved. Check presets for matching name or preset could be saved under a different name.")
            return {'CANCELLED'}
        preset_saved, pname = result
        if preset_saved:
            self.report({'INFO'}, f"{preset_name} saved for node {node.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Preset for node {node.name} already exists using name {pname}.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_node(Operator):
    """
    """
    bl_idname = "hair_factory.load_node"
    bl_label = "Load Node Data"
    bl_description = "Load node data."
    bl_options = {'REGISTER', 'UNDO'}
    
    node: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set
    
    def execute(self, context):
        global NODE_PREVIEW_CACHE
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        pfile = 'NODES'
        node = eval(self.node)
        id_ = str(node.hf_node_presets)
        if id_ == 'None':
            if node in NODE_PREVIEW_CACHE.keys():
                set_nodes_func_dict()[node.type](node, NODE_PREVIEW_CACHE[node])
                self.report({'INFO'}, f"Cached data reloaded for node {node.name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Must select preset name.")
                return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, get_node_data_by_id, id_)
            set_nodes_func_dict()[node.type](node, data)
            preset_name = get_from_zip(zip_file, preset_file, False, get_name_by_id, pfile, id_)
            self.report({'INFO'}, f"{preset_name} loaded for node {node.name}")
            return {'FINISHED'}
        except Exception as ld_error:
            self.report({'ERROR'}, f"{ld_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_rename_node_preset(Operator):
    """
    """
    bl_idname = "hair_factory.rename_node_preset"
    bl_label = "Rename Node Preset"
    bl_description = "Rename node preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    node: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set
    
    def execute(self, context):
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        node = eval(self.node)
        id_ = str(node.hf_node_presets)
        name = node.hf_node_preset_rename
        pfile = 'NODES'
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(name):
            self.report({'ERROR'}, f"New name missing.")
            return {'CANCELLED'}
        if string_has_space(name) or string_startswith_space(name):
            self.report({'ERROR'}, f"New name contains spaces.")
            return {'CANCELLED'}
        if name.upper() == 'NONE':
            self.report({'ERROR'}, f"New name can not be used")
            return {'CANCELLED'}
        if name in get_from_zip(zip_file, preset_file, True, get_node_preset_names):
            self.report({'ERROR'}, f"New name {name} already used. Please Choose another name.")
            return {'CANCELLED'}
        try:
            prev_name = modify_in_zip(zip_file, preset_file, change_preset_name, pfile, id_, name)
            self.report({'INFO'}, f"{prev_name} changed to {name} for node {node.name}")
            return {'FINISHED'}
        except NameExistsError as rn_error:
            self.report({'ERROR'}, f"{rn_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_export_node_preset(Operator):
    """
    """
    bl_idname = "hair_factory.export_node_preset"
    bl_label = "Export Node Preset"
    bl_description = "Export node preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    node: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set
    
    def execute(self, context):
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        node = eval(self.node)
        id_ = str(node.hf_node_presets)
        export_path = bpy.path.abspath(node.hf_node_export_path)
        items = update_node_names_enum(node, context)
        name = get_from_zip(zip_file, preset_file, False, get_name_by_id, 'NODES', id_)
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(export_path):
            self.report({'ERROR'}, f"Export path missing.")
            return {'CANCELLED'}
        if string_startswith_space(export_path):
            self.report({'ERROR'}, f"Export path starts with space.")
            return {'CANCELLED'}
        export_path = Path(export_path)
        if not export_path.is_dir():
            self.report({'ERROR'}, f"Directory {str(export_path)} does not exist.")
            return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, export_node_preset_data_by_preset_id, id_)
            jfile = export_path.joinpath(f'{name}.json')
            with open(jfile, 'w') as jf:
                export_data = {
                    'META': {
                        'NAME': node.name,
                        'TYPE': 'Node',
                    },
                    'DATA': data,
                }
                dump(export_data, jf, cls=NUMPYEncoder)
            self.report({'INFO'}, f"Exported Node data for {node.name} to file {jfile}.")
            return {'FINISHED'}
        except Exception as ep_error:
            self.report({'ERROR'}, f"{ep_error}")
            return {'CANCELLED'}


# NODE GROUP OPERATORS

class HAIRFACTORY_OT_save_node_group(Operator):
    """
    """
    bl_idname = "hair_factory.save_node_group"
    bl_label = "Save Node Group Data"
    bl_description = "Save node group data."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            return False
        ob = context.object
        if not ob:
            return False
        if len(ob.modifiers) == 0:
            return False
        if ob.modifiers.active.type != 'NODES':
            return False
        if not getattr(ob.modifiers.active, "node_group", None):
            return False
        return True
    
    def execute(self, context):
        modifier = context.object.modifiers.active
        node_group = modifier.node_group
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        preset_name = node_group.hf_node_group_preset_name
        if is_string_blank(preset_name):
            self.report({'ERROR'}, f"Preset name missing.")
            return {'CANCELLED'}
        if string_has_space(preset_name) or string_startswith_space(preset_name):
            self.report({'ERROR'}, f"Preset name contains spaces.")
            return {'CANCELLED'}
        if preset_name.upper() == 'NONE':
            self.report({'ERROR'}, f"Preset name can not be used")
            return {'CANCELLED'}
        try:
            if node_group.hf_user == '':
                hair_factory.get_node_user(node_group=node_group.name)
            user_ = node_group.hf_user
            result = modify_in_zip(zip_file, preset_file, geometry_node_preset_processing, node_group, preset_name, user_)
        except (NameExistsError, TypeError) as ne_error:
            self.report({'ERROR'}, f"{ne_error}")
            return {'CANCELLED'}
        if result == None:
            self.report({'ERROR'}, f"Preset for Node Group {node_group.name} was not saved. Check presets for matching name or preset could be saved under a different name.")
            return {'CANCELLED'}
        preset_saved, pname = result
        if preset_saved:
            self.report({'INFO'}, f"{preset_name} saved for node {node_group.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Preset for node group {node_group.name} already exists using name {pname}.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_node_group(Operator):
    """
    """
    bl_idname = "hair_factory.load_node_group"
    bl_label = "Load Node Group Data"
    bl_description = "Load node group data."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            return False
        ob = context.object
        if not ob:
            return False
        if len(ob.modifiers) == 0:
            return False
        if ob.modifiers.active.type != 'NODES':
            return False
        if not getattr(ob.modifiers.active, "node_group", None):
            return False
        return True
    
    def execute(self, context):
        global NODE_GROUP_PREVIEW_CACHE
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        pfile = '/PRESETS/GEOMETRY_NODES/TRANSACTIONS'
        modifier = context.object.modifiers.active
        node_group = modifier.node_group
        id_ = str(node_group.hf_node_group_presets)
        if id_ == 'None':
            if node_group in NODE_GROUP_PREVIEW_CACHE.keys():
                set_node_group_input_data(modifier, NODE_GROUP_PREVIEW_CACHE[node_group]['DATA'])
                if len(NODE_GROUP_PREVIEW_CACHE[node_group]['NODES']) > 0:
                    set_node_presets(node_group, NODE_GROUP_PREVIEW_CACHE[node_group]['NODES'])
                self.report({'INFO'}, f"Cached data reloaded for node group {node_group.name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Must select preset name.")
                return {'CANCELLED'}
        try:
            get_from_zip(zip_file, preset_file, False, set_node_group_preset_data_by_preset_id, modifier, id_)
            preset_name = get_from_zip(zip_file, preset_file, False, get_name_by_id, pfile, id_)
            double_toggle()
            self.report({'INFO'}, f"{preset_name} loaded for node {node_group.name}")
            return {'FINISHED'}
        except Exception as ld_error:
            self.report({'ERROR'}, f"{ld_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_rename_node_group_preset(Operator):
    """
    """
    bl_idname = "hair_factory.rename_node_group_preset"
    bl_label = "Rename Node Group Preset"
    bl_description = "Rename node group preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            return False
        ob = context.object
        if not ob:
            return False
        if len(ob.modifiers) == 0:
            return False
        if ob.modifiers.active.type != 'NODES':
            return False
        if not getattr(ob.modifiers.active, "node_group", None):
            return False
        return True
    
    def execute(self, context):
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        modifier = context.object.modifiers.active
        node_group = modifier.node_group
        id_ = str(node_group.hf_node_group_presets)
        name = node_group.hf_node_group_preset_rename
        pfile = '/PRESETS/GEOMETRY_NODES/TRANSACTIONS'
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(name):
            self.report({'ERROR'}, f"New name missing.")
            return {'CANCELLED'}
        if string_has_space(name) or string_startswith_space(name):
            self.report({'ERROR'}, f"New name contains spaces.")
            return {'CANCELLED'}
        if name.upper() == 'NONE':
            self.report({'ERROR'}, f"New name can not be used")
            return {'CANCELLED'}
        if name in get_from_zip(zip_file, preset_file, True, get_node_group_preset_names, node_group):
            self.report({'ERROR'}, f"New name {name} already used. Please Choose another name.")
            return {'CANCELLED'}
        try:
            prev_name = modify_in_zip(zip_file, preset_file, change_preset_name, pfile, id_, name)
            self.report({'INFO'}, f"{prev_name} changed to {name} for node {node_group.name}")
            return {'FINISHED'}
        except Exception as rn_error:
            self.report({'ERROR'}, f"{rn_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_export_node_group_preset(Operator):
    """
    """
    bl_idname = "hair_factory.export_node_group_preset"
    bl_label = "Export Node Group Preset"
    bl_description = "Export node group preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            return False
        ob = context.object
        if not ob:
            return False
        if len(ob.modifiers) == 0:
            return False
        if ob.modifiers.active.type != 'NODES':
            return False
        if not getattr(ob.modifiers.active, "node_group", None):
            return False
        return True
    
    def execute(self, context):
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        modifier = context.object.modifiers.active
        node_group = modifier.node_group
        id_ = str(node_group.hf_node_group_presets)
        export_path = bpy.path.abspath(node_group.hf_node_group_export_path)
        name = get_from_zip(zip_file, preset_file, False, get_name_by_id, '/PRESETS/GEOMETRY_NODES/TRANSACTIONS', id_)
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(export_path):
            self.report({'ERROR'}, f"Export path missing.")
            return {'CANCELLED'}
        if string_startswith_space(export_path):
            self.report({'ERROR'}, f"Export path starts with space.")
            return {'CANCELLED'}
        export_path = Path(export_path)
        if not export_path.is_dir():
            self.report({'ERROR'}, f"Directory {str(export_path)} does not exist.")
            return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, export_gn_preset_data_by_preset_id, id_)
            jfile = export_path.joinpath(f'{name}.json')
            with open(jfile, 'w') as jf:
                export_data = {
                    'META': {
                        'NAME': node_group.name,
                        'TYPE': 'Geometry_Node',
                    },
                    'DATA': data,
                }
                dump(export_data, jf, cls=NUMPYEncoder)
            self.report({'INFO'}, f"Exported Node Group data for {node_group.name} to file {jfile}.")
            return {'FINISHED'}
        except Exception as ep_error:
            self.report({'ERROR'}, f"{ep_error}")
            return {'CANCELLED'}


# MODIFIER STACK OPERATORS


class HAIRFACTORY_OT_save_mod_stack(Operator):
    """
    """
    bl_idname = "hair_factory.save_mod_stack"
    bl_label = "Save Modifier Stack Data"
    bl_description = "Save modifier stack data."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            return False
        ob = context.object
        if not ob:
            return False
        if len(ob.modifiers) == 0:
            return False
        return True
    
    def execute(self, context):
        ob = context.object
        scene = context.scene
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        preset_name = scene.hf_mod_stack_preset_name
        if is_string_blank(preset_name):
            self.report({'ERROR'}, f"Preset name missing.")
            return {'CANCELLED'}
        if string_has_space(preset_name) or string_startswith_space(preset_name):
            self.report({'ERROR'}, f"Preset name contains spaces.")
            return {'CANCELLED'}
        if preset_name.upper() == 'NONE':
            self.report({'ERROR'}, f"Preset name can not be used")
            return {'CANCELLED'}
        try:
            result = modify_in_zip(zip_file, preset_file, modifier_stack_preset_processing, ob, preset_name, include_surface_deform=scene.hf_mod_stack_include)
        except NameExistsError as ne_error:
            self.report({'ERROR'}, f"{ne_error}")
            return {'CANCELLED'}
        if result == None:
            self.report({'ERROR'}, f"Preset for Modifier Stack for {ob.name} was not saved. Check presets for matching name or preset could be saved under a different name.")
            return {'CANCELLED'}
        success, fail = result    
        self.report({'INFO'}, f"Presets {success} saved for modifier stack.")
        self.report({'INFO'}, f"Presets {fail} not saved for modifier stack.")
        return {'FINISHED'}


class HAIRFACTORY_OT_load_mod_stack(Operator):
    """
    """
    bl_idname = "hair_factory.load_mod_stack"
    bl_label = "Load Modifier Stack Data"
    bl_description = "Load modifier stack data."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            return False
        ob = context.object
        if not ob:
            return False
        return True
    
    def execute(self, context):
        ob = context.object
        scene = context.scene
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        pfile = '/PRESETS/GEOMETRY_NODES/MODIFIER_STACK'
        id_ = str(scene.hf_mod_stack_presets)
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        try:
            load_mod_stack_by_preset_id(zip_file, preset_file, id_)
            preset_name = get_from_zip(zip_file, preset_file, False, get_name_by_id, pfile, id_)
            double_toggle()
            self.report({'INFO'}, f"{preset_name} loaded for {ob.name}")
            return {'FINISHED'}
        except Exception as ld_error:
            self.report({'ERROR'}, f"{ld_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_rename_mod_stack_preset(Operator):
    """
    """
    bl_idname = "hair_factory.rename_mod_stack_preset"
    bl_label = "Rename Modifier Stack Preset"
    bl_description = "Rename modifier stack preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            return False
        ob = context.object
        if not ob:
            return False
        return True
    
    def execute(self, context):
        scene = context.scene
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        id_ = str(scene.hf_mod_stack_presets)
        name = scene.hf_mod_stack_preset_rename
        pfile = '/PRESETS/GEOMETRY_NODES/MODIFIER_STACK'
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(name):
            self.report({'ERROR'}, f"New name missing.")
            return {'CANCELLED'}
        if string_has_space(name) or string_startswith_space(name):
            self.report({'ERROR'}, f"New name contains spaces.")
            return {'CANCELLED'}
        if name.upper() == 'NONE':
            self.report({'ERROR'}, f"New name can not be used")
            return {'CANCELLED'}
        if name in get_from_zip(zip_file, preset_file, True, get_mod_stack_preset_names):
            self.report({'ERROR'}, f"New name {name} already used. Please Choose another name.")
            return {'CANCELLED'}
        try:
            prev_name = modify_in_zip(zip_file, preset_file, change_preset_name, pfile, id_, name)
            self.report({'INFO'}, f"{prev_name} changed to {name} for node {node_group.name}")
            return {'FINISHED'}
        except Exception as rn_error:
            self.report({'ERROR'}, f"{rn_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_export_mod_stack_preset(Operator):
    """
    """
    bl_idname = "hair_factory.export_mod_stack_preset"
    bl_label = "Export Modifier Stack Preset"
    bl_description = "Export modifier stack preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            return False
        ob = context.object
        if not ob:
            return False
        return True
    
    def execute(self, context):
        scene = context.scene
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        id_ = str(scene.hf_mod_stack_presets)
        export_path = bpy.path.abspath(scene.hf_mod_stack_export_path)
        name = get_from_zip(zip_file, preset_file, False, get_name_by_id, '/PRESETS/GEOMETRY_NODES/MODIFIER_STACK', id_)
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(export_path):
            self.report({'ERROR'}, f"Export path missing.")
            return {'CANCELLED'}
        if string_startswith_space(export_path):
            self.report({'ERROR'}, f"Export path starts with space.")
            return {'CANCELLED'}
        export_path = Path(export_path)
        if not export_path.is_dir():
            self.report({'ERROR'}, f"Directory {str(export_path)} does not exist.")
            return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, export_mod_stack_preset_data_by_preset_id, id_)
            jfile = export_path.joinpath(f'{name}.json')
            with open(jfile, 'w') as jf:
                export_data = {
                    'META': {
                        'NAME': name,
                        'TYPE': 'Modifier_Stack',
                    },
                    'DATA': data,
                }
                dump(export_data, jf, cls=NUMPYEncoder)
            self.report({'INFO'}, f"Exported Modifier Stack data for {context.object.name} to file {jfile}.")
            return {'FINISHED'}
        except Exception as ep_error:
            self.report({'ERROR'}, f"{ep_error}")
            return {'CANCELLED'}


# MATERIAL OPERATORS

class HAIRFACTORY_OT_save_mat(Operator):
    """
    """
    bl_idname = "hair_factory.save_mat"
    bl_label = "Save Material Data"
    bl_description = "Save material data."
    bl_options = {'REGISTER', 'UNDO'}
    
    material: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set
    
    def execute(self, context):
        material = eval(self.material)
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        preset_name = material.hf_mat_preset_name
        if is_string_blank(preset_name):
            self.report({'ERROR'}, f"Preset name missing.")
            return {'CANCELLED'}
        if string_has_space(preset_name) or string_startswith_space(preset_name):
            self.report({'ERROR'}, f"Preset name contains spaces.")
            return {'CANCELLED'}
        if preset_name.upper() == 'NONE':
            self.report({'ERROR'}, f"Preset name can not be used")
            return {'CANCELLED'}
        try:
            hair_factory.get_mat_user(material=material.name)
            user_ = material.hf_user
            result = modify_in_zip(zip_file, preset_file, material_preset_processing, material, preset_name, user_)
        except (NameExistsError, TypeError) as ne_error:
            self.report({'ERROR'}, f"{ne_error}")
            return {'CANCELLED'}
        if result == None:
            self.report({'ERROR'}, f"Preset for Material {material.name} was not saved. Check presets for matching name or preset could be saved under a different name.")
            return {'CANCELLED'}
        preset_saved, pname = result
        if preset_saved:
            self.report({'INFO'}, f"{preset_name} saved for material {material.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Preset for material {material.name} already exists using name {pname}.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_mat(Operator):
    """
    """
    bl_idname = "hair_factory.load_mat"
    bl_label = "Load Material Data"
    bl_description = "Load material data."
    bl_options = {'REGISTER', 'UNDO'}
    
    material: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set
    
    def execute(self, context):
        global MAT_PREVIEW_CACHE
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        pfile = '/PRESETS/MATERIALS/TRANSACTIONS'
        material = eval(self.material)
        id_ = str(material.hf_mat_presets)
        if id_ == 'None':
            if material in MAT_PREVIEW_CACHE.keys():
                set_mat_node_data(material.name, MAT_PREVIEW_CACHE[material]['DATA'])
                for node_type in MAT_PREVIEW_CACHE[material]['NODES']:
                    func = set_nodes_func_dict()[node_type]
                    for node in MAT_PREVIEW_CACHE[material]['NODES'][node_type]:
                        node_data = node[1]
                        if isinstance(node_data, type(None)):
                            func(material.node_tree.nodes[node[0]], node[2])
                        else:
                            func(get_mat_group_groups(material.name, node_data.split("|")).node_tree.nodes[node[0]], node[2])
                self.report({'INFO'}, f"Cached data reloaded for node {material.name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Must select preset name.")
                return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, set_mat_preset_data_by_preset_id, id_, material)
            preset_name = get_from_zip(zip_file, preset_file, False, get_name_by_id, pfile, id_)
            self.report({'INFO'}, f"{preset_name} loaded for node {material.name}")
            return {'FINISHED'}
        except Exception as ld_error:
            self.report({'ERROR'}, f"{ld_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_rename_mat_preset(Operator):
    """
    """
    bl_idname = "hair_factory.rename_mat_preset"
    bl_label = "Rename Material Preset"
    bl_description = "Rename material preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    material: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set
    
    def execute(self, context):
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        material = eval(self.material)
        id_ = str(material.hf_mat_presets)
        name = material.hf_mat_preset_rename
        pfile = '/PRESETS/MATERIALS/TRANSACTIONS'
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(name):
            self.report({'ERROR'}, f"New name missing.")
            return {'CANCELLED'}
        if string_has_space(name) or string_startswith_space(name):
            self.report({'ERROR'}, f"New name contains spaces.")
            return {'CANCELLED'}
        if name.upper() == 'NONE':
            self.report({'ERROR'}, f"New name can not be used")
            return {'CANCELLED'}
        if name in get_from_zip(zip_file, preset_file, True, get_mat_preset_names):
            self.report({'ERROR'}, f"New name {name} already used. Please Choose another name.")
            return {'CANCELLED'}
        try:
            prev_name = modify_in_zip(zip_file, preset_file, change_preset_name, pfile, id_, name)
            self.report({'INFO'}, f"{prev_name} changed to {name} for node {material.name}")
            return {'FINISHED'}
        except NameExistsError as rn_error:
            self.report({'ERROR'}, f"{rn_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_export_mat_preset(Operator):
    """
    """
    bl_idname = "hair_factory.export_mat_preset"
    bl_label = "Export Material Preset"
    bl_description = "Export material preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    material: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.is_preset_path_set
    
    def execute(self, context):
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        material = eval(self.material)
        id_ = str(material.hf_mat_presets)
        export_path = bpy.path.abspath(material.hf_mat_export_path)
        name = get_from_zip(zip_file, preset_file, False, get_name_by_id, '/PRESETS/MATERIALS/TRANSACTIONS', id_)
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(export_path):
            self.report({'ERROR'}, f"Export path missing.")
            return {'CANCELLED'}
        if string_startswith_space(export_path):
            self.report({'ERROR'}, f"Export path starts with space.")
            return {'CANCELLED'}
        export_path = Path(export_path)
        if not export_path.is_dir():
            self.report({'ERROR'}, f"Directory {str(export_path)} does not exist.")
            return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, export_mat_preset_data_by_preset_id, id_)
            jfile = export_path.joinpath(f'{name}.json')
            with open(jfile, 'w') as jf:
                export_data = {
                    'META': {
                        'NAME': material.name,
                        'TYPE': 'Material',
                    },
                    'DATA': data,
                }
                dump(export_data, jf, cls=NUMPYEncoder)
            self.report({'INFO'}, f"Exported Material data for {material.name} to file {jfile}.")
            return {'FINISHED'}
        except Exception as ep_error:
            self.report({'ERROR'}, f"{ep_error}")
            return {'CANCELLED'}



# PHYSICS OPERATORS

def phy_poll(cls, context):
    if not context.preferences.addons[__package__].preferences.is_preset_path_set:
        return False
    ob = context.object
    if not ob:
        return False
    if "PHY_MESH" not in dict(ob).keys():
        return False
    if 'CLOTH' not in (m.type for m in ob["PHY_MESH"].modifiers) and 'SOFT_BODY' not in (m.type for m in ob["PHY_MESH"].modifiers):
        return False
    return True


class HAIRFACTORY_OT_save_phy(Operator):
    """
    """
    bl_idname = "hair_factory.save_phy"
    bl_label = "Save Physics Data"
    bl_description = "Save physics data."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return phy_poll(cls, context)
    
    def execute(self, context):
        ob = context.object
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        preset_name = ob.data.hf_phy_preset_name
        ptype = ob.data.hf_phy_ptype
        if is_string_blank(preset_name):
            self.report({'ERROR'}, f"Preset name missing.")
            return {'CANCELLED'}
        if string_has_space(preset_name) or string_startswith_space(preset_name):
            self.report({'ERROR'}, f"Preset name contains spaces.")
            return {'CANCELLED'}
        if preset_name.upper() == 'NONE':
            self.report({'ERROR'}, f"Preset name can not be used")
            return {'CANCELLED'}
        try:
            data = (get_cloth_settings(ob['PHY_MESH']) if ptype == 'CLOTH' else get_soft_body_settings(ob['PHY_MESH']))
            result = modify_in_zip(zip_file, preset_file, physics_preset_processing, ptype, data, preset_name)
        except (NameExistsError) as ne_error:
            self.report({'ERROR'}, f"{ne_error}")
            return {'CANCELLED'}
        if result == None:
            self.report({'ERROR'}, f"Preset for {ptype} for {ob['PHY_MESH'].name} was not saved. Check presets for matching name or preset could be saved under a different name.")
            return {'CANCELLED'}
        preset_saved, pname = result
        if preset_saved:
            self.report({'INFO'}, f"{preset_name} saved for physics mesh {ob['PHY_MESH'].name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Preset for physics mesh {ob['PHY_MESH'].name} already exists using name {pname}.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_phy(Operator):
    """
    """
    bl_idname = "hair_factory.load_phy"
    bl_label = "Load Physics Data"
    bl_description = "Load physics data."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return phy_poll(cls, context)
    
    def execute(self, context):
        global PHY_PREVIEW_CACHE
        ob = context.object
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        ptype = ob.data.hf_phy_ptype
        pfile = f'/PHYSICS/{ptype}'
        id_ = str(ob.data.hf_phy_presets)
        if id_ == 'None':
            if ob.data in PHY_PREVIEW_CACHE.keys():
                (set_cloth_settings(ob['PHY_MESH'], PHY_PREVIEW_CACHE[ob.data]) if ptype == 'CLOTH' else set_soft_body_settings(ob['PHY_MESH'], PHY_PREVIEW_CACHE[ob.data]))
                self.report({'INFO'}, f"Cached data reloaded for physics mesh {ob['PHY_MESH'].name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Must select preset name.")
                return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, set_phy_preset_data_by_preset_id, id_, ob, ptype)
            preset_name = get_from_zip(zip_file, preset_file, False, get_name_by_id, pfile, id_)
            self.report({'INFO'}, f"{preset_name} loaded for physics mesh {ob['PHY_MESH'].name}")
            return {'FINISHED'}
        except Exception as ld_error:
            self.report({'ERROR'}, f"{ld_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_rename_phy_preset(Operator):
    """
    """
    bl_idname = "hair_factory.rename_phy_preset"
    bl_label = "Rename Physics Preset"
    bl_description = "Rename physics preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return phy_poll(cls, context)
    
    def execute(self, context):
        ob = context.object
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        ptype = ob.data.hf_phy_ptype
        id_ = str(ob.data.hf_phy_presets)
        name = ob.data.hf_phy_preset_rename
        pfile = f'/PRESETS/{ptype}'
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(name):
            self.report({'ERROR'}, f"New name missing.")
            return {'CANCELLED'}
        if string_has_space(name) or string_startswith_space(name):
            self.report({'ERROR'}, f"New name contains spaces.")
            return {'CANCELLED'}
        if name.upper() == 'NONE':
            self.report({'ERROR'}, f"New name can not be used")
            return {'CANCELLED'}
        if name in get_from_zip(zip_file, preset_file, True, get_phy_preset_names, ob):
            self.report({'ERROR'}, f"New name {name} already used. Please Choose another name.")
            return {'CANCELLED'}
        try:
            prev_name = modify_in_zip(zip_file, preset_file, change_preset_name, pfile, id_, name)
            self.report({'INFO'}, f"{prev_name} changed to {name} for physics mesh {ob['PHY_MESH'].name}")
            return {'FINISHED'}
        except NameExistsError as rn_error:
            self.report({'ERROR'}, f"{rn_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_export_phy_preset(Operator):
    """
    """
    bl_idname = "hair_factory.export_phy_preset"
    bl_label = "Export Physicsl Preset"
    bl_description = "Export physics preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return phy_poll(cls, context)
    
    def execute(self, context):
        ob = context.object
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        ptype = ob.data.hf_phy_ptype
        id_ = str(ob.data.hf_phy_presets)
        export_path = bpy.path.abspath(ob.data.hf_phy_export_path)
        name = get_from_zip(zip_file, preset_file, False, get_name_by_id, f'/PHYSICS/{ptype}', id_)
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(export_path):
            self.report({'ERROR'}, f"Export path missing.")
            return {'CANCELLED'}
        if string_startswith_space(export_path):
            self.report({'ERROR'}, f"Export path starts with space.")
            return {'CANCELLED'}
        export_path = Path(export_path)
        if not export_path.is_dir():
            self.report({'ERROR'}, f"Directory {str(export_path)} does not exist.")
            return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, export_phy_preset_data_by_preset_id, id_, ptype)
            jfile = export_path.joinpath(f'{name}.json')
            with open(jfile, 'w') as jf:
                export_data = {
                    'META': {
                        'TYPE': 'Physics',
                    },
                    'DATA': data,
                }
                dump(export_data, jf, cls=NUMPYEncoder)
            self.report({'INFO'}, f"Exported {ptype} data for {ob['PHY_MESH'].name} to file {jfile}.")
            return {'FINISHED'}
        except Exception as ep_error:
            self.report({'ERROR'}, f"{ep_error}")
            return {'CANCELLED'}


# COLLISION OPERATORS

def col_poll(cls, context):
    if not context.preferences.addons[__package__].preferences.is_preset_path_set:
        return False
    ob = context.object
    if not ob:
        return False
    if ob.parent == None:
        return False
    return True


class HAIRFACTORY_OT_save_col(Operator):
    """
    """
    bl_idname = "hair_factory.save_col"
    bl_label = "Save Collision Data"
    bl_description = "Save collision data."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return col_poll(cls, context)
    
    def execute(self, context):
        ob = context.object
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        preset_name = ob.data.hf_col_preset_name
        if is_string_blank(preset_name):
            self.report({'ERROR'}, f"Preset name missing.")
            return {'CANCELLED'}
        if string_has_space(preset_name) or string_startswith_space(preset_name):
            self.report({'ERROR'}, f"Preset name contains spaces.")
            return {'CANCELLED'}
        if preset_name.upper() == 'NONE':
            self.report({'ERROR'}, f"Preset name can not be used")
            return {'CANCELLED'}
        try:
            data = get_collision_settings(ob.parent)
            result = modify_in_zip(zip_file, preset_file, collision_preset_processing, data, preset_name)
        except NameExistsError as ne_error:
            self.report({'ERROR'}, f"{ne_error}")
            return {'CANCELLED'}
        if result == None:
            self.report({'ERROR'}, f"Preset for collision mesh {ob.parent.name} was not saved. Check presets for matching name or preset could be saved under a different name.")
            return {'CANCELLED'}
        preset_saved, pname = result
        if preset_saved:
            self.report({'INFO'}, f"{preset_name} saved for collision mesh {ob.parent.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Preset for collision mesh {ob.parent.name} already exists using name {pname}.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_col(Operator):
    """
    """
    bl_idname = "hair_factory.load_col"
    bl_label = "Load Collision Data"
    bl_description = "Load collision data."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return col_poll(cls, context)
    
    def execute(self, context):
        global COL_PREVIEW_CACHE
        ob = context.object
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        pfile = '/PHYSICS/COLLISION'
        id_ = str(ob.data.hf_col_presets)
        if id_ == 'None':
            if ob.data in COL_PREVIEW_CACHE.keys():
                set_collision_settings(ob.parent, COL_PREVIEW_CACHE[ob.data])
                self.report({'INFO'}, f"Cached data reloaded for collision mesh {ob.parent.name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Must select preset name.")
                return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, set_col_preset_data_by_preset_id, id_, ob)
            preset_name = get_from_zip(zip_file, preset_file, False, get_name_by_id, pfile, id_)
            self.report({'INFO'}, f"{preset_name} loaded for collision mesh {ob.parent.name}")
            return {'FINISHED'}
        except Exception as ld_error:
            self.report({'ERROR'}, f"{ld_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_rename_col_preset(Operator):
    """
    """
    bl_idname = "hair_factory.rename_col_preset"
    bl_label = "Rename Collision Preset"
    bl_description = "Rename collision preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return col_poll(cls, context)
    
    def execute(self, context):
        ob = context.object
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        id_ = str(ob.data.hf_col_presets)
        name = ob.data.hf_col_preset_rename
        pfile = f'/PRESETS/COLLISION'
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(name):
            self.report({'ERROR'}, f"New name missing.")
            return {'CANCELLED'}
        if string_has_space(name) or string_startswith_space(name):
            self.report({'ERROR'}, f"New name contains spaces.")
            return {'CANCELLED'}
        if name.upper() == 'NONE':
            self.report({'ERROR'}, f"New name can not be used")
            return {'CANCELLED'}
        if name in get_from_zip(zip_file, preset_file, True, get_col_preset_names):
            self.report({'ERROR'}, f"New name {name} already used. Please Choose another name.")
            return {'CANCELLED'}
        try:
            prev_name = modify_in_zip(zip_file, preset_file, change_preset_name, pfile, id_, name)
            self.report({'INFO'}, f"{prev_name} changed to {name} for collision mesh {ob.parent.name}")
            return {'FINISHED'}
        except NameExistsError as rn_error:
            self.report({'ERROR'}, f"{rn_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_export_col_preset(Operator):
    """
    """
    bl_idname = "hair_factory.export_col_preset"
    bl_label = "Export Collision Preset"
    bl_description = "Export collision preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return col_poll(cls, context)
    
    def execute(self, context):
        ob = context.object
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        id_ = str(ob.data.hf_col_presets)
        export_path = bpy.path.abspath(ob.data.hf_col_export_path)
        name = get_from_zip(zip_file, preset_file, False, get_name_by_id, f'/PHYSICS/COLLISION', id_)
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(export_path):
            self.report({'ERROR'}, f"Export path missing.")
            return {'CANCELLED'}
        if string_startswith_space(export_path):
            self.report({'ERROR'}, f"Export path starts with space.")
            return {'CANCELLED'}
        export_path = Path(export_path)
        if not export_path.is_dir():
            self.report({'ERROR'}, f"Directory {str(export_path)} does not exist.")
            return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, export_col_preset_data_by_preset_id, id_)
            jfile = export_path.joinpath(f'{name}.json')
            with open(jfile, 'w') as jf:
                export_data = {
                    'META': {
                        'TYPE': 'Collision',
                    },
                    'DATA': data,
                }
                dump(export_data, jf, cls=NUMPYEncoder)
            self.report({'INFO'}, f"Exported Collision data for {ob.parent.name} to file {jfile}.")
            return {'FINISHED'}
        except Exception as ep_error:
            self.report({'ERROR'}, f"{ep_error}")
            return {'CANCELLED'}


# HAIR OPERATORS

def hair_poll(cls, context):
    if not context.preferences.addons[__package__].preferences.is_preset_path_set:
        return False
    ob = context.object
    if not ob:
        return False
    if ob.type != 'CURVES':
        return False
    return True


class HAIRFACTORY_OT_save_hair(Operator):
    """
    """
    bl_idname = "hair_factory.save_hair"
    bl_label = "Save Hair Data"
    bl_description = "Save hair data."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return hair_poll(cls, context)
    
    def execute(self, context):
        ob = context.object
        scene = context.scene
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        preset_name = scene.hf_hair_preset_name
        if is_string_blank(preset_name):
            self.report({'ERROR'}, f"Preset name missing.")
            return {'CANCELLED'}
        if string_has_space(preset_name) or string_startswith_space(preset_name):
            self.report({'ERROR'}, f"Preset name contains spaces.")
            return {'CANCELLED'}
        if preset_name.upper() == 'NONE':
            self.report({'ERROR'}, f"Preset name can not be used")
            return {'CANCELLED'}
        try:
            data = get_hair_pts(ob)
            result = modify_in_zip(zip_file, preset_file, hair_preset_processing, data, preset_name)
        except (NameExistsError, TypeError) as ne_error:
            self.report({'ERROR'}, f"{ne_error}")
            return {'CANCELLED'}
        if result == None:
            self.report({'ERROR'}, f"Preset for Hair curve {ob.name} was not saved. Check presets for matching name or preset could be saved under a different name.")
            return {'CANCELLED'}
        preset_saved, pname = result
        if preset_saved:
            self.report({'INFO'}, f"{preset_name} saved for hair curve {ob.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Preset for hair curve {ob.name} already exists using name {pname}.")
            return {'CANCELLED'}


class HAIRFACTORY_OT_load_hair(Operator):
    """
    """
    bl_idname = "hair_factory.load_hair"
    bl_label = "Load Hair"
    bl_description = "Load hair."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            return False
        ob = context.object
        if not ob:
            return False
        if ob.type != 'MESH':
            return False
        return True
    
    def execute(self, context):
        ob = context.object
        scene = context.scene
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        id_ = str(scene.hf_hair_presets)
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        try:
            hair = get_from_zip(zip_file, preset_file, False, set_hair_preset_data_by_preset_id, id_, ob)
            self.report({'INFO'}, f"Hair curve {hair.name} loaded.")
            return {'FINISHED'}
        except Exception as ld_error:
            self.report({'ERROR'}, f"{ld_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_rename_hair_preset(Operator):
    """
    """
    bl_idname = "hair_factory.rename_hair_preset"
    bl_label = "Rename Hair | Preset"
    bl_description = "Rename hair | preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.preferences.addons[__package__].preferences.is_preset_path_set:
            if context.scene.hf_rename_hair_curve:
                return True
            return False
        ob = context.object
        if not ob:
            return False
        if ob.type != 'CURVES':
            return False
        return True
    
    def execute(self, context):
        ob = context.object
        scene = context.scene
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        id_ = str(scene.hf_hair_presets)
        name = scene.hf_hair_preset_rename
        pfile = f'/HAIR/POINTS'
        if id_ == 'None':
            if not scene.hf_rename_hair_curve:
                self.report({'ERROR'}, f"Must select preset name.")
                return {'CANCELLED'}
        if is_string_blank(name):
            self.report({'ERROR'}, f"New name missing.")
            return {'CANCELLED'}
        if string_has_space(name) or string_startswith_space(name):
            self.report({'ERROR'}, f"New name contains spaces.")
            return {'CANCELLED'}
        if name.upper() == 'NONE':
            self.report({'ERROR'}, f"New name can not be used")
            return {'CANCELLED'}
        if not scene.hf_rename_hair_curve:
            if name in get_from_zip(zip_file, preset_file, True, get_hair_preset_names):
                self.report({'ERROR'}, f"New name {name} already used. Please Choose another name.")
                return {'CANCELLED'}
        try:
            if scene.hf_rename_hair_curve:
                old = ob.name
                ob.name = name
                ob.data.name = name
                self.report({'INFO'}, f"{old} changed to {name} for hair curve {ob.name}.")
                return {'FINISHED'}
            prev_name = modify_in_zip(zip_file, preset_file, change_preset_name, pfile, id_, name)
            self.report({'INFO'}, f"{prev_name} changed to {name} for hair curve {ob.name} preset.")
            return {'FINISHED'}
        except NameExistsError as rn_error:
            self.report({'ERROR'}, f"{rn_error}")
            return {'CANCELLED'}


class HAIRFACTORY_OT_export_hair_preset(Operator):
    """
    """
    bl_idname = "hair_factory.export_hair_preset"
    bl_label = "Export Hair Preset"
    bl_description = "Export hair preset."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return hair_poll(cls, context)
    
    def execute(self, context):
        ob = context.object
        scene = context.scene
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        id_ = str(scene.hf_hair_presets)
        export_path = bpy.path.abspath(scene.hf_hair_export_path)
        name = get_from_zip(zip_file, preset_file, False, get_name_by_id, f'/HAIR/POINTS', id_)
        if id_ == 'None':
            self.report({'ERROR'}, f"Must select preset name.")
            return {'CANCELLED'}
        if is_string_blank(export_path):
            self.report({'ERROR'}, f"Export path missing.")
            return {'CANCELLED'}
        if string_startswith_space(export_path):
            self.report({'ERROR'}, f"Export path starts with space.")
            return {'CANCELLED'}
        export_path = Path(export_path)
        if not export_path.is_dir():
            self.report({'ERROR'}, f"Directory {str(export_path)} does not exist.")
            return {'CANCELLED'}
        try:
            data = get_from_zip(zip_file, preset_file, False, export_hair_preset_data_by_preset_id, id_)
            jfile = export_path.joinpath(f'{name}.json')
            with open(jfile, 'w') as jf:
                export_data = {
                    'META': {
                        'NAME': name,
                        'TYPE': 'Hair',
                    },
                    'DATA': data,
                }
                dump(export_data, jf, cls=NUMPYEncoder)
            self.report({'INFO'}, f"Exported Hair data for {ob.name} to file {jfile}.")
            return {'FINISHED'}
        except Exception as ep_error:
            self.report({'ERROR'}, f"{ep_error}")
            return {'CANCELLED'}


# UTILS

def format_enum_items(items, cache_):
    try:
        cache_.clear()
        def item_string(s):
            if not isinstance(s, str):
                return s
            if s not in cache_.keys():
                cache_[s] = s
            return cache_[s]
        return (tuple(item_string(s) for s in item) for item in items)
    except TypeError as te:
        pass


def update_node_names_enum(self, context):
    try:
        global NODE_ENUM_CACHE
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        node_type = self.type
        data = [("None", "None", "")] + list(format_enum_items(get_from_zip(zip_file, preset_file, True, get_node_names_enum, node_type, self.hf_node_preset_search), NODE_ENUM_CACHE))
        return data
    except TypeError as te:
        return [("None", "None", "")]


def update_node_preview(self, context):
    if context.preferences.addons[__package__].preferences.is_preset_path_set:
        global NODE_PREVIEW_CACHE
        if not self.hf_node_preview:
            if self in NODE_PREVIEW_CACHE.keys():
                del NODE_PREVIEW_CACHE[self]
        else:
            if self not in NODE_PREVIEW_CACHE.keys():
                NODE_PREVIEW_CACHE[self] = get_nodes_func_dict()[self.type](self)


def get_special_node_data(node_group):
    ntd_ = node_type_dict(node_group)
    for node_type in ntd_:
        func = get_nodes_func_dict()[node_type]
        for i, node in enumerate(ntd_[node_type]):
            if len(node) == 1:
                data = func(node_group.nodes[node[0]])
            else:
                data = func(get_node_group_groups(node_group.name, node))
            ntd_[node_type][i] = [node, data]
    return ntd_


def update_node_group_preview(self, context):
    if context.preferences.addons[__package__].preferences.is_preset_path_set:
        global NODE_GROUP_PREVIEW_CACHE
        if not self.hf_node_group_preview:
            if self in NODE_GROUP_PREVIEW_CACHE.keys():
                del NODE_GROUP_PREVIEW_CACHE[self]
        else:
            if self not in NODE_GROUP_PREVIEW_CACHE.keys():
                nodes = {}
                if self.hf_node_group_load_type == 'FULL':
                    nodes = get_special_node_data(self)
                NODE_GROUP_PREVIEW_CACHE[self] = {
                    'DATA': dict(get_node_group_input_data(self)),
                    'NODES': nodes,
                    }


def update_mat_preview(self, context):
    if context.preferences.addons[__package__].preferences.is_preset_path_set:
        global MAT_PREVIEW_CACHE
        if not self.hf_mat_preview:
            if self in MAT_PREVIEW_CACHE.keys():
                del MAT_PREVIEW_CACHE[self]
        else:
            if self not in MAT_PREVIEW_CACHE.keys():
                ntd_ = node_type_dict(self.node_tree, classification='Material')
                for node_type in ntd_:
                    func = get_nodes_func_dict()[node_type]
                    for i, node in enumerate(ntd_[node_type]):
                        if len(node) == 1:
                            data = func(self.node_tree.nodes[node[0]])
                        else:
                            data = func(get_mat_group_groups(self.name, node))
                        ntd_[node_type][i].append(data)
                MAT_PREVIEW_CACHE[self] = {
                    'DATA': list(format_mat_node_data(self)),
                    'NODES': ntd_,
                    }


def update_phy_preview(self, context):
    if context.preferences.addons[__package__].preferences.is_preset_path_set:
        global PHY_PREVIEW_CACHE
        ob = context.object
        ptype = ob.data.hf_phy_ptype
        if not ob.data.hf_phy_preview:
            if ob.data in PHY_PREVIEW_CACHE.keys():
                del PHY_PREVIEW_CACHE[ob.data]
        else:
            if 'PHY_MESH' in dict(ob).keys():
                if ob.data not in PHY_PREVIEW_CACHE.keys():
                    PHY_PREVIEW_CACHE[ob.data] = (get_cloth_settings(ob['PHY_MESH']) if ptype == 'CLOTH' else get_soft_body_settings(ob['PHY_MESH']))


def update_col_preview(self, context):
    if context.preferences.addons[__package__].preferences.is_preset_path_set:
        global COL_PREVIEW_CACHE
        ob = context.object
        if not ob.data.hf_col_preview:
            if ob.data in COL_PREVIEW_CACHE.keys():
                del COL_PREVIEW_CACHE[ob.data]
        else:
            if ob.parent != None:
                if ob.data not in COL_PREVIEW_CACHE.keys():
                    COL_PREVIEW_CACHE[ob.data] = get_collision_settings(ob.parent)


def get_node_group_input_data(node_group, modifier=None):
    ignore_sockets = ['NodeSocketGeometry', 'NodeSocketObject', 'NodeSocketMaterial']
    if modifier == None:
        modifier = bpy.context.object.modifiers.active
    if hasattr(node_group, 'interface'):
        items_tree = node_group.interface.items_tree
        it_dict = dict(items_tree)
        for item in it_dict:
            if hasattr(it_dict[item], 'socket_type'):
                if it_dict[item].socket_type not in ignore_sockets:
                    sock = getattr(it_dict[item], 'identifier', None)
                    if sock:
                        if sock in dict(modifier).keys():
                            value = modifier[sock]
                            if value:
                                if not is_basic_type(value):
                                    value = list(value)
                                yield sock, value


def set_node_group_input_data(modifier, data):
    for item in data:
        try:
            modifier[item] = data[item]
        except:
            continue


def set_node_preset(node_group, node_type, addr, data):
    if len(addr) == 1:
        node = node_group.nodes[addr[0]]
    else:
        node = get_node_group_groups(node_group.name, addr)
    set_nodes_func_dict()[node_type](node, data)


def set_node_presets(node_group, node_data_dict):
    for node_type in node_data_dict:
        for node in node_data_dict[node_type]:
            set_node_preset(node_group, node_type, *node)


def get_node_preset_names(file):
    with File(file, 'r') as hf:
        for id_ in hf['NODES'].keys():
            yield hf['NODES'][id_].attrs.get('name')


def set_node_group_preset_data_by_preset_id(file, modifier, id_):
    with File(file, 'r') as hf:
        trans = hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][id_][0].astype(str)
        values = loads(hf['/PRESETS/GEOMETRY_NODES/DATA'][trans[1]][0])
        set_node_group_input_data(modifier, values)
        node_group = modifier.node_group
        if node_group.hf_node_group_load_type == 'FULL':
            ntd = loads(hf['/PRESETS/GEOMETRY_NODES/INFO'][trans[0]][0])
            nst = loads(hf['NODE_STACK'][trans[2]][0])
            ndata = {ntype: [[n, loads(hf['NODES'][nst[ntype][i]][0])] for i, n in enumerate(ntd[ntype])] for ntype in ntd}
            set_node_presets(node_group, ndata)


def get_node_group_presets(file, node_group, search_text):
    ng_id = hash_dict(get_all_nodes(node_group))
    with File(file, 'r') as hf:
        for id_ in hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'].keys():
            if ng_id == hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][id_][0].astype(str)[0]:
                name = hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][id_].attrs.get('name')
                if char.find(name, search_text).item() > -1:
                    yield (id_, name, '')


def get_node_group_preset_names(file, node_group):
    ng_id = hash_dict(get_all_nodes(node_group))
    with File(file, 'r') as hf:
        for id_ in hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'].keys():
            if ng_id == hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][id_][0].astype(str)[0]:
                yield hf['/PRESETS/GEOMETRY_NODES/TRANSACTIONS'][id_].attrs.get('name')


def node_group_items(self, context):
    try:
        global NODE_GROUP_ENUM_CACHE
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        data = [("None", "None", "")] + list(format_enum_items(get_from_zip(zip_file, preset_file, True, get_node_group_presets, self, self.hf_node_group_preset_search), NODE_GROUP_ENUM_CACHE))
        return data
    except TypeError as te:
        return [("None", "None", "")]


def get_mod_stack_presets(file, search_text):
    with File(file, 'r') as hf:
        for id_ in hf['/PRESETS/GEOMETRY_NODES/MODIFIER_STACK'].keys():
            name = hf['/PRESETS/GEOMETRY_NODES/MODIFIER_STACK'][id_].attrs.get('name')
            if char.find(name, search_text).item() > -1:
                yield (id_, name, '')


def get_mod_stack_preset_names(file):
    with File(file, 'r') as hf:
        for id_ in hf['/PRESETS/GEOMETRY_NODES/MODIFIER_STACK'].keys():
            yield hf['/PRESETS/GEOMETRY_NODES/MODIFIER_STACK'][id_].attrs.get('name')


def mod_stack_items(self, context):
    try:
        global MOD_STACK_ENUM_CACHE
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        data = [("None", "None", "")] + list(format_enum_items(get_from_zip(zip_file, preset_file, True, get_mod_stack_presets, self.hf_mod_stack_preset_search), MOD_STACK_ENUM_CACHE))
        return data
    except TypeError as te:
        return [("None", "None", "")]


def get_mat_preset_names(file):
    with File(file, 'r') as hf:
        for id_ in hf['/PRESETS/MATERIALS/TRANSACTIONS'].keys():
            yield hf['/PRESETS/MATERIALS/TRANSACTIONS'][id_].attrs.get('name')


def get_mat_presets(file, material, search_text):
    mat_id = hash_dict(get_all_nodes(material.node_tree))
    with File(file, 'r') as hf:
        for id_ in hf['/PRESETS/MATERIALS/TRANSACTIONS'].keys():
            if mat_id == hf['/PRESETS/MATERIALS/TRANSACTIONS'][id_][0].astype(str)[0]:
                name = hf['/PRESETS/MATERIALS/TRANSACTIONS'][id_].attrs.get('name')
                if char.find(name, search_text).item() > -1:
                    yield (id_, name, '')


def mat_items(self, context):
    try:
        global MAT_ENUM_CACHE
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        data = [("None", "None", "")] + list(format_enum_items(get_from_zip(zip_file, preset_file, True, get_mat_presets, self, self.hf_mat_preset_search), MAT_ENUM_CACHE))
        return data
    except TypeError as te:
        return [("None", "None", "")]


def get_phy_preset_names(file, ob):
    ptype = ob.data.hf_phy_ptype
    with File(file, 'r') as hf:
        for id_ in hf[f'/PHYSICS/{ptype}'].keys():
            yield hf[f'/PHYSICS/{ptype}'][id_].attrs.get('name')


def get_phy_presets(file, ob, search_text):
    ptype = ob.data.hf_phy_ptype
    with File(file, 'r') as hf:
        for id_ in hf[f'/PHYSICS/{ptype}'].keys():
            name = hf[f'/PHYSICS/{ptype}'][id_].attrs.get('name')
            if char.find(name, search_text).item() > -1:
                yield (id_, name, '')


def phy_items(self, context):
    try:
        global PHY_ENUM_CACHE
        ob = context.object
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        data = [("None", "None", "")] + list(format_enum_items(get_from_zip(zip_file, preset_file, True, get_phy_presets, ob, ob.data.hf_phy_preset_search), PHY_ENUM_CACHE))
        return data
    except TypeError as te:
        return [("None", "None", "")]


def get_col_preset_names(file):
    with File(file, 'r') as hf:
        for id_ in hf['/PHYSICS/COLLISION'].keys():
            yield hf['/PHYSICS/COLLISION'][id_].attrs.get('name')


def get_col_presets(file, ob, search_text):
    with File(file, 'r') as hf:
        for id_ in hf['/PHYSICS/COLLISION'].keys():
            name = hf['/PHYSICS/COLLISION'][id_].attrs.get('name')
            if char.find(name, search_text).item() > -1:
                yield (id_, name, '')


def col_items(self, context):
    try:
        global COL_ENUM_CACHE
        ob = context.object
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        data = [("None", "None", "")] + list(format_enum_items(get_from_zip(zip_file, preset_file, True, get_col_presets, ob, ob.data.hf_col_preset_search), COL_ENUM_CACHE))
        return data
    except TypeError as te:
        return [("None", "None", "")]


def get_hair_preset_names(file):
    with File(file, 'r') as hf:
        for id_ in hf['/HAIR/POINTS'].keys():
            yield hf['/HAIR/POINTS'][id_].attrs.get('name')


def get_hair_presets(file, search_text):
    with File(file, 'r') as hf:
        for id_ in hf['/HAIR/POINTS'].keys():
            name = hf['/HAIR/POINTS'][id_].attrs.get('name')
            if char.find(name, search_text).item() > -1:
                yield (id_, name, '')


def hair_items(self, context):
    try:
        global HAIR_ENUM_CACHE
        zip_file = get_zip_file()
        preset_file = 'Presets.hfdb'
        data = [("None", "None", "")] + list(format_enum_items(get_from_zip(zip_file, preset_file, True, get_hair_presets, context.scene.hf_hair_preset_search), HAIR_ENUM_CACHE))
        return data
    except TypeError as te:
        return [("None", "None", "")]


#######################################################################################


classes = [
    # NODE
    HAIRFACTORY_OT_save_node,
    HAIRFACTORY_OT_load_node,
    HAIRFACTORY_OT_rename_node_preset,
    HAIRFACTORY_OT_export_node_preset,
    # NODE GROUP
    HAIRFACTORY_OT_save_node_group,
    HAIRFACTORY_OT_load_node_group,
    HAIRFACTORY_OT_rename_node_group_preset,
    HAIRFACTORY_OT_export_node_group_preset,
    # MODIFIER STACK
    HAIRFACTORY_OT_save_mod_stack,
    HAIRFACTORY_OT_load_mod_stack,
    HAIRFACTORY_OT_rename_mod_stack_preset,
    HAIRFACTORY_OT_export_mod_stack_preset,
    # MATERIAL
    HAIRFACTORY_OT_save_mat,
    HAIRFACTORY_OT_load_mat,
    HAIRFACTORY_OT_rename_mat_preset,
    HAIRFACTORY_OT_export_mat_preset,
    # PHYSICS
    HAIRFACTORY_OT_save_phy,
    HAIRFACTORY_OT_load_phy,
    HAIRFACTORY_OT_rename_phy_preset,
    HAIRFACTORY_OT_export_phy_preset,
    # COLLISION
    HAIRFACTORY_OT_save_col,
    HAIRFACTORY_OT_load_col,
    HAIRFACTORY_OT_rename_col_preset,
    HAIRFACTORY_OT_export_col_preset,
    # HAIR
    HAIRFACTORY_OT_save_hair,
    HAIRFACTORY_OT_load_hair,
    HAIRFACTORY_OT_rename_hair_preset,
    HAIRFACTORY_OT_export_hair_preset,
]


def register():
    for cls in classes:
        register_class(cls)
    
    # NODE
    ShaderNode.hf_node_preview = BoolProperty(
        name = "Preview Preset",
        description = "Cache the current node settings so that they can be restored",
        update=update_node_preview,
    )
    ShaderNode.hf_node_preset_name = StringProperty(
        name = "Preset Name",
        description = "Set name for node preset.",
    )
    ShaderNode.hf_node_preset_rename = StringProperty(
        name = "Change Preset Name",
        description = "Change name for selected preset.",
    )
    ShaderNode.hf_node_preset_search = StringProperty(
        name = "Search", 
        options = {'TEXTEDIT_UPDATE'},
        description = "Use text to narrow down search of presets. (Case Sensitive)",
    )
    ShaderNode.hf_node_presets = EnumProperty(
        name = "Node Presets",
        description = "Select Preset by name from drop down list.",
        items = update_node_names_enum,
    )
    ShaderNode.hf_node_export_path = StringProperty(
        name = "Node Export Path",
        description = "Path for node preset export.",
        subtype = 'DIR_PATH',
    )
    # Input Color
    FunctionNodeInputColor.hf_node_preview = BoolProperty(
        name = "Preview Preset",
        description = "Cache the current node settings so that they can be restored",
        update=update_node_preview,
    )
    FunctionNodeInputColor.hf_node_preset_name = StringProperty(
        name = "Preset Name",
        description = "Set name for node preset.",
    )
    FunctionNodeInputColor.hf_node_preset_rename = StringProperty(
        name = "Change Preset Name",
        description = "Change name for loaded preset.",
    )
    FunctionNodeInputColor.hf_node_preset_search = StringProperty(
        name = "Search", 
        options = {'TEXTEDIT_UPDATE'},
        description = "Use text to narrow down search of presets. (Case Sensitive)",
    )
    FunctionNodeInputColor.hf_node_presets = EnumProperty(
        name = "Node Presets",
        description = "Select Preset by name from drop down list.",
        items = update_node_names_enum,
    )
    FunctionNodeInputColor.hf_node_export_path = StringProperty(
        name = "Node Export Path",
        description = "Path for node preset export.",
        subtype = 'DIR_PATH',
    )
    # NODE GROUP
    GeometryNodeTree.hf_node_group_preview = BoolProperty(
        name = "Preview Preset",
        description = "Cache the current node group settings so that they can be restored",
        update=update_node_group_preview,
    )
    GeometryNodeTree.hf_node_group_preset_name = StringProperty(
        name = "Preset Name",
        description = "Set name for node group preset.",
    )
    GeometryNodeTree.hf_node_group_preset_rename = StringProperty(
        name = "Change Preset Name",
        description = "Change name for selected preset.",
    )
    GeometryNodeTree.hf_node_group_preset_search = StringProperty(
        name = "Search", 
        options = {'TEXTEDIT_UPDATE'},
        description = "Use text to narrow down search of presets. (Case Sensitive)",
    )
    GeometryNodeTree.hf_node_group_presets = EnumProperty(
        name = "Node Group Presets",
        description = "Select Preset by name from drop down list.",
        items = node_group_items,
    )
    GeometryNodeTree.hf_node_group_export_path = StringProperty(
        name = "Node Group Export Path",
        description = "Path for node group preset export.",
        subtype = 'DIR_PATH',
    )
    GeometryNodeTree.hf_node_group_load_type = EnumProperty(
        name = "Node Group Load Type",
        description = "Select to load node group or full preset data.",
        items = [
            ('FULL', 'Full', 'Load full preset data.'),
            ('NODE_GROUP', 'Node Group', 'Load only node group data.'),
        ],
    )
    # MODIFIER STACK
    Scene.hf_mod_stack_include = BoolProperty(
        name = "Include Surface Deform",
        description = "Include Surface Deform in save and export.",
        default = False,
    )
    Scene.hf_mod_stack_preset_name = StringProperty(
        name = "Preset Name",
        description = "Set name for modifier stack preset.",
    )
    Scene.hf_mod_stack_preset_rename = StringProperty(
        name = "Change Preset Name",
        description = "Change name for selected preset.",
    )
    Scene.hf_mod_stack_preset_search = StringProperty(
        name = "Search", 
        options = {'TEXTEDIT_UPDATE'},
        description = "Use text to narrow down search of presets. (Case Sensitive)",
    )
    Scene.hf_mod_stack_presets = EnumProperty(
        name = "Modifier Stack Presets",
        description = "Select Preset by name from drop down list.",
        items = mod_stack_items,
    )
    Scene.hf_mod_stack_export_path = StringProperty(
        name = "Modifier Stack Export Path",
        description = "Path for modifier stack preset export.",
        subtype = 'DIR_PATH',
    )
    # MATERIAL
    Material.hf_mat_preview = BoolProperty(
        name = "Preview Preset",
        description = "Cache the current node settings so that they can be restored",
        update=update_mat_preview,
    )
    Material.hf_mat_preset_name = StringProperty(
        name = "Preset Name",
        description = "Set name for material preset.",
    )
    Material.hf_mat_preset_rename = StringProperty(
        name = "Change Preset Name",
        description = "Change name for selected preset.",
    )
    Material.hf_mat_preset_search = StringProperty(
        name = "Search", 
        options = {'TEXTEDIT_UPDATE'},
        description = "Use text to narrow down search of presets. (Case Sensitive)",
    )
    Material.hf_mat_presets = EnumProperty(
        name = "Material Presets",
        description = "Select Preset by name from drop down list.",
        items = mat_items,
    )
    Material.hf_mat_export_path = StringProperty(
        name = "Material Export Path",
        description = "Path for material preset export.",
        subtype = 'DIR_PATH',
    )
    # PHYSICS
    Curves.hf_phy_preview = BoolProperty(
        name = "Preview Preset",
        description = "Cache the current physics settings so that they can be restored",
        update=update_phy_preview,
    )
    Curves.hf_phy_preset_name = StringProperty(
        name = "Preset Name",
        description = "Set name for physics preset.",
    )
    Curves.hf_phy_preset_rename = StringProperty(
        name = "Change Preset Name",
        description = "Change name for selected preset.",
    )
    Curves.hf_phy_preset_search = StringProperty(
        name = "Search", 
        options = {'TEXTEDIT_UPDATE'},
        description = "Use text to narrow down search of presets. (Case Sensitive)",
    )
    Curves.hf_phy_presets = EnumProperty(
        name = "Physics Presets",
        description = "Select Preset by name from drop down list.",
        items = phy_items,
    )
    Curves.hf_phy_export_path = StringProperty(
        name = "Physics Export Path",
        description = "Path for physics preset export.",
        subtype = 'DIR_PATH',
    )
    # COLLISION
    Curves.hf_col_preview = BoolProperty(
        name = "Preview Preset",
        description = "Cache the current collision settings so that they can be restored",
        update=update_col_preview,
    )
    Curves.hf_col_preset_name = StringProperty(
        name = "Preset Name",
        description = "Set name for collision preset.",
    )
    Curves.hf_col_preset_rename = StringProperty(
        name = "Change Preset Name",
        description = "Change name for selected preset.",
    )
    Curves.hf_col_preset_search = StringProperty(
        name = "Search", 
        options = {'TEXTEDIT_UPDATE'},
        description = "Use text to narrow down search of presets. (Case Sensitive)",
    )
    Curves.hf_col_presets = EnumProperty(
        name = "Collision Presets",
        description = "Select Preset by name from drop down list.",
        items = col_items,
    )
    Curves.hf_col_export_path = StringProperty(
        name = "Collision Export Path",
        description = "Path for collision preset export.",
        subtype = 'DIR_PATH',
    )
    # HAIR
    Scene.hf_rename_hair_curve = BoolProperty(
        name = "Rename Hair Curve",
        description = "Rename the hair curve instead of the preset.",
        default = False,
    )
    Scene.hf_hair_preset_name = StringProperty(
        name = "Preset Name",
        description = "Set name for hair preset.",
    )
    Scene.hf_hair_preset_rename = StringProperty(
        name = "Change Preset Name",
        description = "Change name for selected preset.",
    )
    Scene.hf_hair_preset_search = StringProperty(
        name = "Search", 
        options = {'TEXTEDIT_UPDATE'},
        description = "Use text to narrow down search of presets. (Case Sensitive)",
    )
    Scene.hf_hair_presets = EnumProperty(
        name = "Hair Presets",
        description = "Select Preset by name from drop down list.",
        items = hair_items,
    )
    Scene.hf_hair_export_path = StringProperty(
        name = "Hair Export Path",
        description = "Path for hair preset export.",
        subtype = 'DIR_PATH',
    )



def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
    
    # NODE
    del ShaderNode.hf_node_preview
    del ShaderNode.hf_node_preset_name
    del ShaderNode.hf_node_preset_rename
    del ShaderNode.hf_node_preset_search
    del ShaderNode.hf_node_presets
    del ShaderNode.hf_node_export_path
    # Input Color
    del FunctionNodeInputColor.hf_node_preview
    del FunctionNodeInputColor.hf_node_preset_name
    del FunctionNodeInputColor.hf_node_preset_rename
    del FunctionNodeInputColor.hf_node_preset_search
    del FunctionNodeInputColor.hf_node_presets
    del FunctionNodeInputColor.hf_node_export_path
    # NODE GROUP
    del GeometryNodeTree.hf_node_group_preview
    del GeometryNodeTree.hf_node_group_preset_name
    del GeometryNodeTree.hf_node_group_preset_rename
    del GeometryNodeTree.hf_node_group_preset_search
    del GeometryNodeTree.hf_node_group_presets
    del GeometryNodeTree.hf_node_group_export_path
    del GeometryNodeTree.hf_node_group_load_type
    # MODIFIER STACK
    del Scene.hf_mod_stack_include
    del Scene.hf_mod_stack_preset_name
    del Scene.hf_mod_stack_preset_rename
    del Scene.hf_mod_stack_preset_search
    del Scene.hf_mod_stack_presets
    del Scene.hf_mod_stack_export_path
    # MATERIAL
    del Material.hf_mat_preview
    del Material.hf_mat_preset_name
    del Material.hf_mat_preset_rename
    del Material.hf_mat_preset_search
    del Material.hf_mat_presets
    del Material.hf_mat_export_path
    # PHYSICS
    del Curves.hf_phy_preview
    del Curves.hf_phy_preset_name
    del Curves.hf_phy_preset_rename
    del Curves.hf_phy_preset_search
    del Curves.hf_phy_presets
    del Curves.hf_phy_export_path
    # COLLISION
    del Curves.hf_col_preview
    del Curves.hf_col_preset_name
    del Curves.hf_col_preset_rename
    del Curves.hf_col_preset_search
    del Curves.hf_col_presets
    del Curves.hf_col_export_path
    # HAIR
    del Scene.hf_rename_hair_curve
    del Scene.hf_hair_preset_name
    del Scene.hf_hair_preset_rename
    del Scene.hf_hair_preset_search
    del Scene.hf_hair_presets
    del Scene.hf_hair_export_path
 

