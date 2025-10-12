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
from bpy.ops import object as object_, nla, hair_factory
from bpy.types import Operator, Curves, Armature
from bpy.props import FloatProperty, EnumProperty, BoolProperty
from bpy.utils import register_class, unregister_class
from numpy import array_split, empty, roll, c_, r_, arange, repeat, isin, subtract, divide, cross, add, multiply, linspace
from numpy.linalg import norm as norm_
from .load_util import add_hair_factory_node, get_hf_node_group_zip
from .bake_materials_util import hair_mesh_mat_bake
from .gui_util import delete_geo_node_modifier, delete_full_node_tree


def format_name(name, post):
    parts = name.split(".")
    if len(parts) == 1:
        return f"{parts[0]}_{post}"
    return f"{parts[0]}_{post}.{parts[1]}"


def get_foreach(target, attr, type, attr_ct=1):
    count = len(target)
    data = empty(count * attr_ct).astype(type)
    target.foreach_get(attr, data)
    if attr_ct == 1:
        return data
    return data.reshape((count, attr_ct))


def add_series_nums(arr):
    def _add_series_nums(arr):
        num = 0
        for n in arr:
            num += n
            yield num
    return r_[*_add_series_nums(arr)]


def split_array_by_counts(arr, counts):
    return array_split(arr, add_series_nums(counts))[:-1]


def edge_chain(indices):
    return c_[indices[:-1], roll(indices, -1)[:-1]]


class HairToMesh:
    __slots__ = ['ob', 'points', 'point_count', 'count', 'co']
    #
    def __init__(self, ob):
        self.ob = ob
        self.points = get_foreach(ob.data.position_data, "vector", float, attr_ct=3)
        self.point_count = len(ob.data.position_data)
        self.count = len(ob.data.curves)
        self.co = split_array_by_counts(self.points, list(self.sizes))
    """
    """
    def get_point(self, index):
        return list(self.ob.data.position_data[index].vector)
    """
    """
    @property
    def sizes(self):
        for c in  self.ob.data.curves:
            yield c.points_length
    """
    """
    @property
    def split_edges(self):
        indices = arange(self.point_count)
        split_idx = split_array_by_counts(indices, list(self.sizes))
        for idx in split_idx:
            yield edge_chain(idx)
    """
    """
    @property
    def edges(self):
        return r_[*self.split_edges]
    """
    """
    @property
    def edge_order(self):
        for idx, ec in enumerate(self.split_edges):
            ct = len(ec)
            for eo in c_[repeat(idx, ct).reshape((ct, -1)), arange(ct).reshape((ct, -1)), ec]:
                yield eo
    """
    """
    @property
    def roots(self):
        for c in  self.ob.data.curves:
            yield c.first_point_index
    """
    """
    @property
    def pin_factor(self):
        for s in self.sizes:
            yield from linspace(0,1,s, dtype='f2')




# OBJECT
####################


def new_mesh(Name, verts=[], edges=[], faces=[]):
    mesh = bpy.data.meshes.new(Name)
    mesh.from_pydata(verts, edges, faces)
    return mesh


def new_object(Name, mesh_data):
    ob = bpy.data.objects.new(Name, mesh_data)
    return ob


def link_ob(ob, collection=None):
    if not collection:
        collection = bpy.context.collection
    collection.objects.link(ob)
    return ob


def create_ob(Name, verts=[], edges=[], faces=[], collection=None):
    mesh_data = new_mesh(Name, verts, edges, faces)
    ob = new_object(Name, mesh_data)
    link_ob(ob, collection=collection)
    return ob


def set_cloth_physics_mesh_offset(ob, offset=0.05):
    vt = ob.data.vertices
    ct = len(vt)
    co = empty(ct*3)
    vt.foreach_get('co', co)
    co = co.reshape((ct, 3))
    count = ct//3
    co_split = co.reshape((3, count, 3))
    verts, verts2, verts3 = co_split
    norm2 = subtract(verts2, verts)
    norm2 = divide(norm2, norm_(norm2, axis=1).reshape((count, 1)))
    norm3 = subtract(verts3, verts)
    norm3 = divide(norm3, norm_(norm3, axis=1).reshape((count, 1)))
    verts2 = add(verts, multiply(norm2, offset))
    verts3 = add(verts, multiply(norm3, offset))
    co = r_[verts, verts2, verts3]
    co = co.ravel()
    vt.foreach_set('co', co)
    ob.data.update()
    return


# ARMATURE
####################

def new_armature(Name):
    arm = bpy.data.armatures.new(Name)
    return arm


def new_bone(arm, Name, head=[0,0,0], tail=[0,0,1]):
    eb = arm.data.edit_bones
    bone = eb.new(Name)
    bone.head = head
    bone.tail = tail
    return bone


def create_armature(Name, collection=None):
    arm = new_armature(Name)
    ob = new_object(Name, arm)
    link_ob(ob, collection=collection)
    return ob


def add_bone(arm, Name='root', head=[0,0,0], tail=[0,-1,0], parent=None, use_connect=False):
    with bpy.context.temp_override(active_object=arm):
        object_.select_all(action='DESELECT')
        arm.select_set(1)
        bpy.context.view_layer.objects.active = arm
        object_.mode_set(mode='EDIT')
        bone = new_bone(arm, Name, head, tail)
        bone.use_connect = use_connect
        bone.parent = parent
        object_.mode_set(mode='OBJECT')
    return arm


def add_pb_damped_track(pose_bone, target, subtarget):
    dt = pose_bone.constraints.new('DAMPED_TRACK')
    dt.target = target
    dt.subtarget = subtarget
    dt.track_axis = 'TRACK_Y'
    return dt


def set_bone_tracking_all(arm, value=1):
    pb = arm.pose.bones
    for bone in pb:
        for constraint in bone.constraints:
            if constraint.type == 'DAMPED_TRACK':
                constraint.influence = value
    return


def add_hair_armature(ob, Name="Hair_Armature"):
    ha = ob.modifiers.new(Name, "ARMATURE")
    return ha


def add_hair_physics(ob, Name="Hair_Physics"):
    hp = ob.modifiers.new(Name, "CLOTH")
    hp.settings.vertex_group_mass = "Pin"
    return hp


def add_hair_soft_body(ob, Name="Hair_Physics"):
    hp = ob.modifiers.new(Name, "SOFT_BODY")
    hp.settings.vertex_group_mass = "Pin"
    hp.settings.mass = 0.2
    hp.settings.use_edges = True
    hp.settings.use_goal = True
    hp.settings.vertex_group_goal = "Roots"
    hp.settings.goal_friction = 10
    hp.settings.effector_weights.wind = 0.1
    return hp


def add_collision(ob):
    cl = ob.modifiers.new("Hair_Collision", "COLLISION")
    ob.collision.thickness_outer = 0.001
    return cl


def add_armature_bone(arm, Name='root', head=[0,0,0], tail=[0,-1,0], parent=None, use_connect=False):
    bone = new_bone(arm, Name, head, tail)
    bone.use_connect = use_connect
    bone.parent = parent
    return bone



def add_physics_bones(arm, edge_order, points, target):
    active_ob = bpy.context.view_layer.objects.active
    with bpy.context.temp_override(active_object=arm, selected_objects=[arm]):
        object_.select_all(action='DESELECT')
        arm.select_set(1)
        bpy.context.view_layer.objects.active = arm
        object_.mode_set(mode='EDIT')
        bp = None
        for bdata in edge_order:
            c, s, h, t = bdata
            bone = add_armature_bone(arm, Name=f"{c}_{s}", head=points[h], tail=points[t], parent=(None if s == 0 else bp), use_connect=(True if s != 0 else False))
            bp = bone
        bp = None
        object_.mode_set(mode='POSE')
        pb = arm.pose.bones
        for bone in pb:
            add_pb_damped_track(bone, target, bone.name)
        object_.mode_set(mode='OBJECT')
    object_.select_all(action='DESELECT')
    active_ob.select_set(1)
    bpy.context.view_layer.objects.active = active_ob
    return arm


def create_physics_arm(surface, Name, data_ob, target, collection=None):
    arm = create_armature(Name, collection=collection)
    points = get_ob_space_points(surface, data_ob.points)
    return add_physics_bones(arm, data_ob.edge_order, points, target)


def create_physics_soft_body_mesh(surface, Name, data_ob, collection=None):
    verts = get_ob_space_points(surface, data_ob.points)
    ob = create_ob(Name, verts=verts, edges=data_ob.edges, faces=[], collection=collection)
    count = verts.shape[0]
    index = arange(count)
    pidx = index[isin(index, data_ob.roots, invert=True)].tolist()
    idx = index.tolist()
    # Pin
    nvg = ob.vertex_groups.new(name="Pin")
    nvg.add(pidx, 1.0, 'REPLACE')
    # Root
    rvg = ob.vertex_groups.new(name="Roots")
    rvg.add(idx, 1.0, 'REPLACE')
    # Track Groups
    for eo in data_ob.edge_order:
        c, s, h, t = eo
        gvg = ob.vertex_groups.new(name=f"{c}_{s}")
        gvg.add([int(t)], 1.0, 'REPLACE')
    return ob


def get_ob_space_points(ob, points):
    return subtract(points, list(ob.location))


def get_normalized_vec_and_mag(src, target):
    vec = subtract(src, target)
    mag = norm_(vec)
    if mag == 0:
        return None, None
    return divide(vec, norm_(vec)), norm_(vec)


def get_point_aligned_to_surface_norms(surface, points):
    for point in points:
        _, loc, norm, idx = surface.closest_point_on_mesh(point, depsgraph=bpy.context.evaluated_depsgraph_get())
        yield [r_[loc], r_[norm]]


def get_physics_mesh_tangents(edge_order, points, roots):
    data = {i: None for i in range(points.shape[0])}
    for eo in edge_order:
        c, s, h, t = eo
        tangent, _ = get_normalized_vec_and_mag(points[t], points[h])
        data[h] = tangent
    if not any(not isinstance(data[i], type(None)) for i in data):
        raise ValueError("Segments must have lengths greater than zero.")
    if not all(not isinstance(data[root], type(None)) for root in roots):
        raise ValueError("All Roots must have lengths greater than zero.")
    for i in data:
        if isinstance(data[i], type(None)):
            check = False
            while not check:
                for n in range(i + 1):
                    d = data[i - n]
                    if not isinstance(d, type(None)):
                        yield d
                        check = True
                        break
        else:
            yield data[i]


def get_tangents(ob, node_group):
    temp_curve = bpy.data.objects.new(f"temp_{ob.name}", ob.data)
    bpy.context.collection.objects.link(temp_curve)
    modifier = add_hair_factory_node(temp_curve, get_hf_node_group_zip(), "TANGENTS.py")
    node_group = modifier.node_group
    temp_eval = temp_curve.evaluated_get(bpy.context.evaluated_depsgraph_get())
    tangents = get_foreach(temp_eval.data.attributes["tangents"].data, "vector", float, attr_ct=3)
    bpy.data.node_groups.remove(node_group)
    temp_curve.modifiers.remove(modifier)
    bpy.data.objects.remove(temp_curve)
    return tangents


def get_physics_mesh_normals(surface, edge_order, points, roots):
    last = None
    for t, sn in zip(get_physics_mesh_tangents(edge_order, points, roots), get_point_aligned_to_surface_norms(surface, points)):
        n = cross(t, sn[1])
        yield n


def make_physics_cloth_faces(edges, count):
    faces = []
    for edge in edges:
        f, l = edge
        faces.append([f, f + count, l + count, l])
        faces.append([f + (count*2), f, l, l + (count*2)])
    return faces


def create_physics_cloth_mesh(surface, Name, data_ob, offset=0.05, collection=None):
    verts = get_ob_space_points(surface, data_ob.points)
    norms = r_[[*get_physics_mesh_normals(surface, data_ob.edge_order, verts, data_ob.roots)]] * offset
    pts = r_[verts, verts + norms, verts - norms]
    count = verts.shape[0]
    faces = make_physics_cloth_faces(data_ob.edges, count)
    ob = create_ob(Name, verts=pts, edges=[], faces=faces, collection=collection)
    pf = ob.data.attributes.new('Pin_Factor', 'FLOAT', 'POINT')
    pf_data = [*data_ob.pin_factor, *data_ob.pin_factor, *data_ob.pin_factor]
    pf.data.foreach_set('value', pf_data)
    index = arange(count)
    idx = r_[index, index + count, index + (2 * count)].tolist()
    # Pin
    nvg = ob.vertex_groups.new(name="Pin")
    nvg.add(idx, 1.0, 'REPLACE')
    # Track Groups
    for eo in data_ob.edge_order:
        c, s, h, t = eo
        gvg = ob.vertex_groups.new(name=f"{c}_{s}")
        gvg.add([int(t)], 1.0, 'REPLACE')
    return ob


def create_physics(ob, surface, ptype='CLOTH', offset=0.05, collection=None):
    htm = HairToMesh(ob)
    pmn = format_name(ob.name, "Mesh")
    pbn = format_name(ob.name, "Bones")
    if ptype == 'CLOTH':
        mob = create_physics_cloth_mesh(surface, pmn, htm, offset=offset, collection=collection)
        modifier = add_hair_factory_node(mob, get_hf_node_group_zip(), "HAIR_PIN_WEIGHTS.py")
        hp = add_hair_physics(mob, Name="Hair_Physics")
    else:
        mob = create_physics_soft_body_mesh(surface, pmn, htm, collection=collection)
        hp = add_hair_soft_body(mob, Name="Hair_Physics")
    collision_ob = ob.parent
    mob.parent = collision_ob
    mob.hide_select = True
    mob.hide_viewport = True
    mob.hide_render = True
    arm = create_physics_arm(surface, pbn, htm, mob, collection=collection)
    arm.parent = collision_ob
    arm.hide_select = True
    arm.hide_viewport = True
    arm.hide_render = True
    if collision_ob:
        if not any((modifier.type == 'COLLISION' for modifier in collision_ob.modifiers)):
            add_collision(collision_ob)
    return mob, arm


def enable_physics(self, context):
    ob = context.object
    ptype = 'CLOTH'
    offset = 0.05
    mob, arm = create_physics(ob, ob.parent, ptype=ptype, offset=offset, collection=context.collection)
    ob['PHY_MESH'] = mob
    ob['PHY_BONES'] = arm
    mob.parent = ob
    arm.parent = ob


def toggle_phy_mesh(ob, phy_ob):
    object_.select_all(action='DESELECT')
    phy_ob.select_set(1)
    bpy.context.view_layer.objects.active = phy_ob
    object_.mode_set(mode='EDIT')
    object_.mode_set(mode='OBJECT')
    object_.select_all(action='DESELECT')
    ob.select_set(1)
    bpy.context.view_layer.objects.active = ob


def update_cloth_mesh_offset(ob, offset):
    verts = get_foreach(ob.data.vertices, 'co', float, attr_ct=3)
    verts = verts.reshape((3, verts.shape[0]//3, 3))
    verts = r_[[
        *verts[0],
        *add(verts[0], multiply(divide(subtract(verts[0], verts[1]), norm_(subtract(verts[0], verts[1]), axis=0)), offset)),
        *add(verts[0], multiply(divide(subtract(verts[0], verts[2]), norm_(subtract(verts[0], verts[2]), axis=0)), offset)),
    ]]
    verts = verts.ravel()
    ob.data.vertices.foreach_set('co', verts)



def update_phy_offset(self, context):
    ob = context.object
    scene = context.scene
    if "PHY_MESH" in dict(ob).keys():
        mob = ob["PHY_MESH"]
        if mob != None:
            if ob.data.hf_phy_ptype == 'CLOTH':
                update_cloth_mesh_offset(mob, ob.data.hf_phy_offset)
                toggle_phy_mesh(ob, mob)




def get_physics_vg_modified_wts(ob, vg_name):
    obe = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    vg = obe.data.attributes[vg_name].data
    ct = len(vg)
    wts = empty(ct)
    vg.foreach_get('value', wts)
    return wts


def update_physics_vg_wts(ob, vg_name):
    wts = (wt for wt in get_physics_vg_modified_wts(ob, vg_name))
    for i, wt in enumerate(wts):
        ob.vertex_group[vg_name].add([i], wt, "REPLACE")





class HAIRFACTORY_OT_enable_physics(Operator):
    """
    """
    bl_idname = "hair_factory.enable_physics"
    bl_label = "Enable Physics"
    bl_description = "Enable physics for the hair curve."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and ob.type == 'CURVES' and 'PHY_MESH' not in dict(ob).keys() and 'PHY_BONES' not in dict(ob).keys()
    
    def execute(self, context):
        try:
            ob = context.object
            mob, arm = create_physics(ob, ob.parent, ptype=ob.data.hf_phy_ptype, offset=ob.data.hf_phy_offset, collection=context.collection)
            ob['PHY_MESH'] = mob
            ob['PHY_BONES'] = arm
            mob.parent = ob
            arm.parent = ob
            mob['PHY_HAIR'] = ob
            arm['PHY_HAIR'] = ob
            # Controller
            pc = "PHYSICS_CONTROL"
            if pc not in [m.name.split(".")[0] for m in ob.modifiers]:
                modifier = add_hair_factory_node(ob, get_hf_node_group_zip(), f"{pc}.py")
                index = (1 if ob.modifiers[0].name.split(".")[0] == "Surface Deform" else 0)
                bpy.ops.object.modifier_move_to_index(modifier=modifier.name, index=index)
                modifier["Socket_2"] = mob
                for mod in ob.modifiers:
                    mod.show_viewport = False
                for mod in ob.modifiers:
                    mod.show_viewport = True
            mob.hide_viewport = False
            mob.hide_viewport = True
            self.report({'INFO'}, f"{ob.name} Physics enabled. MESH: {mob.name}  ARMATURE: {arm.name}")
            return {'FINISHED'}
        except ValueError as ve:
            self.report({'ERROR'}, f"Something wrong with Geometry! {ve}")
            return {'CANCELLED'}



class HAIRFACTORY_OT_disable_physics(Operator):
    """
    """
    bl_idname = "hair_factory.disable_physics"
    bl_label = "Disable Physics"
    bl_description = "Disable physics for the hair curve."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        ob_dict = dict(ob)
        return ob and ob.type == 'CURVES' and 'PHY_MESH' in dict(ob).keys() and 'PHY_BONES' in dict(ob).keys()
    
    def execute(self, context):
        ob = context.object
        try:
            mob = ob['PHY_MESH']
            arm = ob['PHY_BONES']
            mn = mob.name
            an = arm.name
            for m in ob.modifiers:
                if m.type == 'NODES':
                    if m.name.split(".")[0] == "PHYSICS_CONTROL":
                        delete_geo_node_modifier(ob, m)
            bpy.data.meshes.remove(mob.data)
            bpy.data.armatures.remove(arm.data)
            del ob['PHY_MESH']
            del ob['PHY_BONES']
            self.report({'INFO'}, f"{ob.name} Physics disabled and objects removed. MESH: {mn}  ARMATURE: {an}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"[Disable Physics Error] {e}.")
            return{'CANCELLED'}


class HAIRFACTORY_OT_launch_bake_destination(Operator):
    bl_idname = "hair_factory.bake_destination"
    bl_label = "Bake Destination"
    bl_description = "Set Bake destination path for hair converted to mesh textures."
    bl_options = {'REGISTER', 'UNDO'}
    

    def execute(self, context):
        try:
            hair_mesh_mat_bake(context)
            self.report({'INFO'}, f"Baked textures for {context.object.name} to {bpy.path.abspath(context.scene.baker_props.destination_path)}")
            return {'FINISHED'}
        except ValueError as ve:
            self.report({'ERROR'}, f"{ve}")
            return {'CANCELLED'}
    
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
        box.prop(scene.baker_props, 'destination_path')
        box.prop(scene.baker_props, 'image_size')
        box.prop(scene.baker_props, 'sample_count')
        row = box.row()
        row.prop(scene.baker_props, 'threshold')
        row.prop(scene.baker_props, 'use_alpha', text="")


class HAIRFACTORY_OT_convert_hair_to_mesh(Operator):
    """
    """
    bl_idname = "hair_factory.convert_hair_to_mesh"
    bl_label = "Convert Hair to Mesh"
    bl_description = "Convert hair curve to mesh object."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and ob.type == 'CURVES' and ob in context.selected_objects[:]
    
    def execute(self, context):
        ob = context.object
        add_arm = False
        modifiers = ob.modifiers
        groups = (getattr(m, 'node_group') for m in modifiers if m.type == 'NODES')
        try:
            object_.convert(target='MESH', merge_customdata=True)
            if 'PHY_BONES' in dict(ob).keys():
                h_arm = add_hair_armature(ob, Name="Hair_Armature")
                h_arm.object = ob['PHY_BONES']
                h_arm.use_bone_envelopes = True
                h_arm.use_deform_preserve_volume = True
                h_arm.use_vertex_groups = False
                add_arm = True
            if 'PHY_MESH' in dict(ob).keys():
                for m in ob['PHY_MESH'].modifiers:
                    if m.type == 'NODES':
                        delete_geo_node_modifier(ob['PHY_MESH'], m)
                bpy.data.meshes.remove(ob['PHY_MESH'].data)
                del ob['PHY_MESH']
            for ng in groups:
                delete_full_node_tree(ng)
            if len(context.object.material_slots) > 0:
                context.object["HF_BAKED"] = False
                hair_factory.bake_destination('INVOKE_DEFAULT')
            msg = (f" Armature modifier added to {ob.name}" if add_arm else "")
            self.report({'INFO'}, f"{ob.name} converted to mesh.{msg}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"[Hair to Mesh Error] {e}.")
            return{'CANCELLED'}


class HAIRFACTORY_OT_bake_phys(Operator):
    """
    """
    bl_idname = "hair_factory.bake_phys"
    bl_label = "Bake Hair Physics"
    bl_description = "Bake the Hair Physics Simulation to the Active Physics Armature."
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if not ob:
            return False
        if "PHY_HAIR" in dict(ob).keys():
            ob = ob["PHY_HAIR"]
        if "PHY_BONES" not in dict(ob).keys():
            return False
        if ob["PHY_BONES"] == None:
            return False
        if not any([len(b.constraints) > 0 for b in ob["PHY_BONES"].pose.bones]):
            return False
        return True
    
    def execute(self, context):
        scene = context.scene
        ob = context.object
        if not ob:
            self.report({'ERROR'}, "Hair not Selected.")
            return{'CANCELLED'}
        if "PHY_HAIR" in dict(ob).keys():
            ob = ob["PHY_HAIR"]
        arm = ob["PHY_BONES"]
        pc = [getattr(m, 'node_group') for m in ob.modifiers if (m.type == 'NODES' and m.node_group.name.split(".")[0] == "PHYSICS_CONTROL")]
        object_.select_all(action='DESELECT')
        arm.select_set(1)
        context.view_layer.objects.active = arm
        ahv = arm.hide_viewport
        ahs = arm.hide_select
        arm.hide_viewport = False
        arm.hide_select = False
        object_.mode_set(mode='POSE')
        try:
            nla.bake(frame_start=scene.frame_start, frame_end=scene.frame_end, only_selected=arm.data.hf_selected_bones_only, clear_constraints=True, visual_keying=True, bake_types={'POSE'})
            arm.animation_data.action.name = "Hair_Action"
            object_.mode_set(mode='OBJECT')
            object_.select_all(action='DESELECT')
            ob.select_set(1)
            context.view_layer.objects.active = ob
            arm.hide_viewport = ahv
            arm.hide_select = ahs
            try:
                for node_group in pc:
                    delete_full_node_tree(node_group)
            except:
                pass
            return{'FINISHED'}
        except Exception as e:
            object_.mode_set(mode='OBJECT')
            object_.select_all(action='DESELECT')
            ob.select_set(1)
            context.view_layer.objects.active = ob
            arm.hide_viewport = ahv
            arm.hide_select = ahs
            self.report({'ERROR'}, f"[Action Bake Error] {e}.")
            return{'CANCELLED'}


def bake_to_nla():
    ob = bpy.context.object
    scene = bpy.context.scene
    if ob.animation_data and ob.animation_data.action:
        nla.bake(frame_start=scene.frame_start, frame_end=scene.frame_end, only_selected=False, clear_constraints=True, visual_keying=True, bake_types={'POSE'})
        nla.action_add(action=ob.animation_data.action.name)




classes = [
    HAIRFACTORY_OT_enable_physics,
    HAIRFACTORY_OT_disable_physics,
    HAIRFACTORY_OT_launch_bake_destination,
    HAIRFACTORY_OT_convert_hair_to_mesh,
    HAIRFACTORY_OT_bake_phys,
]


def register():
    for cls in classes:
        register_class(cls)
    
    Curves.hf_phy_offset = FloatProperty(
        name = "Offset", 
        description = "Offset from center used for Cloth Physics", 
        default = 0.05, 
        update = update_phy_offset,
        soft_min = 0.0001,
    )
    Curves.hf_phy_ptype = EnumProperty(
        name = "Physics Type",
        description = "The type of physics to use.",
        items = [
            ('SOFT_BODY', "Soft Body", "Use Soft Body Physics."),
            ('CLOTH', "Cloth", "Use Cloth Physics."),
        ],
    )
    Armature.hf_selected_bones_only = BoolProperty(
        name = "Selected Bones Only",
        description = "Bake only selected bones animations.",
        default = False,
    )


def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
    
    del Curves.hf_phy_offset
    del Curves.hf_phy_ptype
    del Armature.hf_selected_bones_only

