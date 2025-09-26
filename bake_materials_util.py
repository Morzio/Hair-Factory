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
from bpy.ops import object as object_
from bpy.types import Operator, PropertyGroup, Scene
from bpy.props import IntProperty, EnumProperty, PointerProperty, StringProperty, BoolProperty, FloatProperty
from bpy.utils import register_class, unregister_class
from pathlib import Path
from numpy import array, where


def bake_material(ob, mat, image_size, image_type, save_mode, image_destination, samples=10, use_denoising=False, active_uv='UVMap', remove_extra_uvs=True):
    layers = ob.data.uv_layers
    if active_uv in [l.name for l in layers]:
        if remove_extra_uvs:
            for layer in layers:
                if layer.name != active_uv:
                    layers.remove(layer)
        layers[active_uv].active_render = True
    img_name = f"{ob.name.replace('.', '_')}_{image_type.title()}"
    img = bpy.data.images.new(img_name, image_size, image_size)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    alt_image_types = {'ALPHA': 'EMIT', 'ROOT': 'DIFFUSE'}
    image_type_ = (image_type if image_type not in alt_image_types.keys() else alt_image_types[image_type])
    soc_reset = False
    if image_type in alt_image_types.keys():
        out, orig_out_soc, alpha, root = get_bake_links_layout(mat)
        if image_type == 'ALPHA':
            if alpha is not None:
                links.new(alpha, out)
                soc_reset = True
        if image_type == 'ROOT':
            if root is not None:
                links.new(root, out)
                soc_reset = True
    for node in nodes:
        node.select = False
    texture_node = nodes.new('ShaderNodeTexImage')
    texture_node.name = "Material_Bake"
    texture_node.select = True
    nodes.active = texture_node
    texture_node.image = img
    bpy.context.view_layer.objects.active = ob
    # bake settings
    render_engine = bpy.context.scene.render.engine
    bpy.context.scene.render.engine = 'CYCLES'
    bake_type = bpy.context.scene.cycles.bake_type
    samples_ = bpy.context.scene.cycles.samples
    use_adaptive_sampling = bpy.context.scene.cycles.use_adaptive_sampling
    use_denoising_ = bpy.context.scene.cycles.use_denoising
    bpy.context.scene.cycles.bake_type = image_type_
    bpy.context.scene.cycles.samples = samples
    bpy.context.scene.cycles.use_adaptive_sampling = False
    bpy.context.scene.cycles.use_denoising = use_denoising
    try:
        use_pass_direct = bpy.context.scene.render.bake.use_pass_direct
        use_pass_indirect = bpy.context.scene.render.bake.use_pass_indirect
        use_pass_color = bpy.context.scene.render.bake.use_pass_color
        view_from = bpy.context.scene.render.bake.view_from
        bpy.context.scene.render.bake.use_pass_direct = False
        bpy.context.scene.render.bake.use_pass_indirect = False
        bpy.context.scene.render.bake.use_pass_color = True
        bpy.context.scene.render.bake.view_from = 'ABOVE_SURFACE'
    except:
        pass
    # bake process
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        object_.bake(type=image_type_, save_mode=save_mode)
    file = Path(image_destination).joinpath(f"{img.name}.png")
    if file.is_file():
        file.unlink()
    try:
        img.pixels.update()
        img.save_render(filepath=str(file))
    except Exception as bake_error:
        print(f"Bake Error: {bake_error}")
    finally:
        nodes.remove(texture_node)
        if soc_reset:
            links.new(orig_out_soc, out)
        bpy.context.scene.cycles.bake_type = bake_type
        bpy.context.scene.cycles.samples = samples_
        bpy.context.scene.cycles.use_adaptive_sampling = use_adaptive_sampling
        bpy.context.scene.cycles.use_denoising = use_denoising_
    try:
        bpy.context.scene.render.bake.use_pass_direct = use_pass_direct
        bpy.context.scene.render.bake.use_pass_indirect = use_pass_indirect
        bpy.context.scene.render.bake.use_pass_color = use_pass_color
        bpy.context.scene.render.bake.view_from = view_from
        bpy.context.scene.render.engine = render_engine
    except:
        pass
    return img.name


def bake_multi_material(ob, image_size, image_type, save_mode, image_destination, samples=10, use_denoising=False, active_uv='UVMap', remove_extra_uvs=True):
    layers = ob.data.uv_layers
    if active_uv in [l.name for l in layers]:
        if remove_extra_uvs:
            for layer in layers:
                if layer.name != active_uv:
                    layers.remove(layer)
        layers[active_uv].active_render = True
    img_name = f"{ob.name.replace('.', '_')}_{image_type.title()}"
    img = bpy.data.images.new(img_name, image_size, image_size)
    # bake settings
    alt_image_types = {'ALPHA': 'EMIT', 'ROOT': 'DIFFUSE'}
    image_type_ = (image_type if image_type not in alt_image_types.keys() else alt_image_types[image_type])
    render_engine = bpy.context.scene.render.engine
    bpy.context.scene.render.engine = 'CYCLES'
    bake_type = bpy.context.scene.cycles.bake_type
    samples_ = bpy.context.scene.cycles.samples
    use_adaptive_sampling = bpy.context.scene.cycles.use_adaptive_sampling
    use_denoising_ = bpy.context.scene.cycles.use_denoising
    bpy.context.scene.cycles.bake_type = image_type_
    bpy.context.scene.cycles.samples = samples
    bpy.context.scene.cycles.use_adaptive_sampling = False
    bpy.context.scene.cycles.use_denoising = use_denoising
    try:
        use_pass_direct = bpy.context.scene.render.bake.use_pass_direct
        use_pass_indirect = bpy.context.scene.render.bake.use_pass_indirect
        use_pass_color = bpy.context.scene.render.bake.use_pass_color
        view_from = bpy.context.scene.render.bake.view_from
        bpy.context.scene.render.bake.use_pass_direct = False
        bpy.context.scene.render.bake.use_pass_indirect = False
        bpy.context.scene.render.bake.use_pass_color = True
        bpy.context.scene.render.bake.view_from = 'ABOVE_SURFACE'
    except:
        pass
    mat_slots = ob.material_slots
    tns = []
    srs = []
    oos = []
    for mat in mat_slots:
        nodes = mat.material.node_tree.nodes
        links = mat.material.node_tree.links
        soc_reset = False
        if image_type in alt_image_types.keys():
            out, orig_out_soc, alpha, root = get_bake_links_layout(mat.material)
            oos.append([orig_out_soc, out])
            if image_type == 'ALPHA':
                if alpha is not None:
                    links.new(alpha, out)
                    soc_reset = True
            if image_type == 'ROOT':
                if root is not None:
                    links.new(root, out)
                    soc_reset = True
        srs.append(soc_reset)
        for node in nodes:
            node.select = False
        texture_node = nodes.new('ShaderNodeTexImage')
        texture_node.name = "Material_Bake"
        texture_node.select = True
        nodes.active = texture_node
        texture_node.image = img
        tns.append(texture_node.name)
    bpy.context.view_layer.objects.active = ob
    # bake process
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        object_.bake(type=image_type_, save_mode=save_mode)
    file = Path(image_destination).joinpath(f"{img.name}.png")
    if file.is_file():
        file.unlink()
    try:
        img.pixels.update()
        img.save_render(filepath=str(file))
    except Exception as bake_error:
        print(f"Bake Error: {bake_error}")
    finally:
        for idx, mat in enumerate(mat_slots):
            nodes = mat.material.node_tree.nodes
            links = mat.material.node_tree.links
            nodes.remove(nodes[tns[idx]])
            if srs[idx]:
                links.new(*oos[idx])
        bpy.context.scene.cycles.bake_type = bake_type
        bpy.context.scene.cycles.samples = samples_
        bpy.context.scene.cycles.use_adaptive_sampling = use_adaptive_sampling
        bpy.context.scene.cycles.use_denoising = use_denoising_
    try:
        bpy.context.scene.render.bake.use_pass_direct = use_pass_direct
        bpy.context.scene.render.bake.use_pass_indirect = use_pass_indirect
        bpy.context.scene.render.bake.use_pass_color = use_pass_color
        bpy.context.scene.render.bake.view_from = view_from
        bpy.context.scene.render.engine = render_engine
    except:
        pass
    return img.name


def get_image_types_enum():
    image_types = ['COMBINED', 'AO', 'SHADOW', 'POSITION', 'NORMAL', 'UV', 'ROUGHNESS', 'EMIT', 'ENVIRONMENT', 'DIFFUSE', 'GLOSSY', 'TRANSMISSION']
    return [(type_, type_, f"Bake {type_.title()} map.") for type_ in image_types]


def get_loaded_materials():
    try:
        return [material.name for material in bpy.data.materials]
    except Exception as mat_error:
        return []


def get_loaded_materials_enum():
    materials = ["None"] + get_loaded_materials()
    return [(material, material, material) for material in materials]


def get_bake_links_layout(mat):
    node_tree = mat.node_tree
    links = node_tree.links
    nodes = node_tree.nodes
    from_node = array([l.from_node for l in links])
    from_socket = array([l.from_socket for l in links])
    to_node = array([l.to_node for l in links])
    to_socket = array([l.to_socket for l in links])
    look_up = lambda n, s, nn, sn: next((idx for idx, n_s in enumerate(zip(n, s)) if (n_s[0].name == nn and n_s[1].name == sn)))
    to_out_idx = look_up(to_node, to_socket, 'Material Output', 'Surface')
    orig_out_soc = from_socket[to_out_idx]
    out = nodes['Material Output'].inputs['Surface']
    alpha = (None if 'Alpha Shader' not in [s.name for s in from_node[to_out_idx].outputs] else from_node[to_out_idx].outputs['Alpha Shader'])
    root = (None if 'Root Map' not in [n.name for n in nodes] else nodes['Root Map'].outputs['Color'])
    return out, orig_out_soc, alpha, root


def get_pixels(img):
    data = array(img.pixels)
    return data.reshape((int(data.size//4), 4))


def set_image_alpha(image, alpha, copy_alpha=False, threshold=0.0):
    dp = get_pixels(image)
    ap = get_pixels(alpha)
    if copy_alpha:
        al_ = ap[:,3]
    else:
        al_ = ap[:,0]
    if threshold > 0.0:
        al_[al_ <= threshold] = al_[where(al_ <= threshold)] - threshold/2
        al_[al_ < 0.0] = 0.0
    dp[:,3] = al_
    image.pixels = dp.ravel()
    image.pixels.update()


def modify_image_alpha(dir_path, imgs, threshold=0.0):
    ct = len(imgs)
    if ct >= 4:
        if "Alpha" in imgs[3]:
            if Path(dir_path).joinpath(f"{imgs[3]}.png").is_file():
                alpha = bpy.data.images.load(filepath=str(Path(dir_path).joinpath(f"{imgs[3]}.png")))
                diffuse = bpy.data.images.load(filepath=str(Path(dir_path).joinpath(f"{imgs[0]}.png")))
                normal = bpy.data.images.load(filepath=str(Path(dir_path).joinpath(f"{imgs[1]}.png")))
                roughness = bpy.data.images.load(filepath=str(Path(dir_path).joinpath(f"{imgs[2]}.png")))
                set_image_alpha(diffuse, alpha, copy_alpha=False, threshold=threshold)
                set_image_alpha(normal, alpha, copy_alpha=False, threshold=threshold)
                set_image_alpha(roughness, alpha, copy_alpha=False, threshold=threshold)
                diffuse.save_render(filepath=str(Path(dir_path).joinpath(f"{imgs[0]}.png")))
                normal.save_render(filepath=str(Path(dir_path).joinpath(f"{imgs[1]}.png")))
                roughness.save_render(filepath=str(Path(dir_path).joinpath(f"{imgs[2]}.png")))
                bpy.data.images.remove(diffuse)
                bpy.data.images.remove(normal)
                bpy.data.images.remove(roughness)
                if ct > 4:
                    if "Root" in imgs[4]:
                        if Path(dir_path).joinpath(f"{imgs[4]}.png").is_file():
                            root = bpy.data.images.load(filepath=str(Path(dir_path).joinpath(f"{imgs[4]}.png")))
                            set_image_alpha(root, alpha, copy_alpha=False, threshold=threshold)
                            root.save_render(filepath=str(Path(dir_path).joinpath(f"{imgs[4]}.png")))
                            bpy.data.images.remove(root)
                bpy.data.images.remove(alpha)


def material_bake(self, context):
    ob = context.object
    scene = context.scene
    if scene.hf_ob_socs not in ['OBJECT', 'None']:
        ob = ob.modifiers.active[scene.hf_ob_socs]
    material_name = scene.hf_available_mats
    material = bpy.data.materials.get(material_name)
    if material:
        node_tree = getattr(material, "node_tree", None)
        if node_tree:
            nodes = getattr(node_tree, "nodes", None)
            if nodes:
                    destination = bpy.path.abspath(scene.baker_props.destination_path)
                    image_type = scene.baker_props.image_types
                    image_size = scene.baker_props.image_size
                    save_mode = scene.baker_props.save_mode
                    samples = scene.baker_props.sample_count
                    active_uv = scene.baker_props.active_uv
                    bake_material(ob, material, image_size, image_type, save_mode, destination, samples=samples, active_uv=active_uv, remove_extra_uvs=False)


def hair_mesh_mat_bake(context):
    ob = context.object
    scene = context.scene
    destination = bpy.path.abspath(scene.baker_props.destination_path)
    if destination == '':
        raise ValueError("Must select a destination path!")
    image_types = ['DIFFUSE', 'NORMAL', 'ROUGHNESS'] + ([] if not scene.baker_props.use_alpha else ['ALPHA']) + (['ROOT'] if (scene.baker_props.use_alpha and scene.baker_props.use_root) else [])
    image_size = scene.baker_props.image_size
    save_mode = 'EXTERNAL'
    samples = scene.baker_props.sample_count
    active_uv = "UVMap"
    imgs = []
    mat_slots = ob.material_slots
    count = len(mat_slots)
    if count > 0:
        if count == 1:
            mat = mat_slots[0].material
            for image_type in image_types:
                img = bake_material(ob, mat, image_size, image_type, save_mode, destination, samples=samples, active_uv=active_uv)
                imgs.append(img)
        else:
            for image_type in image_types:
                img = bake_multi_material(ob, image_size, image_type, save_mode, destination, samples=samples, active_uv=active_uv)
                imgs.append(img)
    ob["HF_BAKED"] = True
    if scene.baker_props.use_alpha:
        modify_image_alpha(destination, imgs, threshold=scene.baker_props.threshold)



class BakeProps(PropertyGroup):
    """
    """
    destination_path: StringProperty(name="File Path", description="External path to save bakes.", default="", subtype="FILE_PATH")
    
    image_size: IntProperty(name="Image Size", description="Image size for square render image.", default=1024)

    sample_count: IntProperty(name="Samples", description="Image samples.", default=10)

    use_denoise: BoolProperty(name="Use Denoise", description="Use denoise for image. Not recommended for procedural hair texture baking.", default=False)

    use_alpha: BoolProperty(name="Use Aplha", description="Bake alpha into textures.", default=True)

    use_root: BoolProperty(name="Use Root", description="Bake root textures.", default=False)

    active_uv: StringProperty(name="UV Map", description="UV Map to save bakes.", default="UVMap")

    threshold: FloatProperty(name="Threshold", description="Threshold for alpha falloff.", default=0.0, soft_min=0.0, soft_max=1.0)
    
    image_types: EnumProperty(
        name="Bake type",
        description="The type of image to bake.",
        items=get_image_types_enum(),
        default='DIFFUSE',
    )
    
    save_mode: EnumProperty(
        name="Bake Save Mode",
        description="Choose to save image externally or internally.",
        items=[('EXTERNAL', 'EXTERNAL', 'Save image to given path.'), ('INTERNAL', 'INTERNAL', 'Save image inside current .blend')],
        default='EXTERNAL',
    )
 

 

class HAIRFACTORY_OT_bake_material_texture(Operator):
    """
    """
    bl_idname = "hair_factory.bake_material_texture"
    bl_label = "Bake Material Texture"
    bl_description = "Bake selected material to texture."
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if context.scene.hf_ob_socs not in ['OBJECT', 'None']:
            ob = ob.modifiers.active[context.scene.hf_ob_socs]
        if not ob:
            return False
        if ob.type != 'MESH':
            return False
        materials = bpy.data.materials
        if len(materials) == 0:
            return False
        material = materials.get(context.scene.hf_available_mats)
        if not material:
            return False
        node_tree = getattr(material, "node_tree", None)
        if not node_tree:
            return False
        nodes = getattr(node_tree, "nodes", None)
        if not nodes:
            return False
        return True
    
    def execute(self, context):
        try:
            material_bake(self, context)
            msg = (context.object.name if context.scene.hf_ob_socs in ['OBJECT', 'None'] else context.object.modifiers.active[context.scene.hf_ob_socs])
            self.report({'INFO'}, f"Baked texture for {msg}.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"{e}.")
            return {'CANCELLED'}
 
 
 
classes = [
    BakeProps,
    HAIRFACTORY_OT_bake_material_texture,
 ]
 
 
 
def register():
    for cls in classes:
        register_class(cls)
    
    Scene.baker_props = PointerProperty(type=BakeProps)


def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
    
    del Scene.baker_props
 
