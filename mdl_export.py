import struct
import heapq
from os import path, makedirs

import bpy
from mathutils import Matrix, Vector
from bpy.app.translations import pgettext_tip as tip_

tab = '\t'

# Pre-compiled struct packers for performance optimization during intensive binary writing loops
pack_B = struct.Struct('B').pack
pack_BBBB = struct.Struct('BBBB').pack
pack_H = struct.Struct('H').pack
pack_HHH = struct.Struct('HHH').pack
pack_I = struct.Struct('I').pack
pack_f = struct.Struct('f').pack
pack_ff = struct.Struct('ff').pack
pack_fff = struct.Struct('fff').pack

# Direct3D Flexible Vertex Format (FVF) flags defining the target engine's vertex memory layout
D3DFVF_XYZ = 0x02
D3DFVF_XYZB2 = 0x08
D3DFVF_NORMAL = 0x10
D3DFVF_TEX1 = 0x0100
D3DFVF_LASTBETA_UBYTE4 = 0x1000

# Engine-specific mesh bitflags for rendering pipeline features
MESH_FLAG_LIGHT     = 0b100
MESH_FLAG_SKINNED   = 0b10000
MESH_FLAG_BUMP      = 0b100000000
MESH_FLAG_MATERIAL  = 0b10000000000
MESH_FLAG_SUBSKIN   = 0b100000000000


def add_ext(name, ext, remove=False):
    # Safely enforces, swaps, or removes file extensions without duplicating dots.
    if name.endswith(ext):
        return name[:name.rindex(ext)].replace('.', '') + ('' if remove else ext)
    return name.replace('.', '') + ('' if remove else ext)


def export(dir, operator, apply_unit_scale, use_mirror):
    try:
        unit_scale = 1
        # Convert Blender's internal units to the specific scale expected by the target engine
        if apply_unit_scale:
            if bpy.context.scene.unit_settings.system == 'METRIC':
                unit_scale = bpy.context.scene.unit_settings.scale_length * 20
            elif bpy.context.scene.unit_settings.system == 'IMPERIAL':
                unit_scale = bpy.context.scene.unit_settings.scale_length * 6.096

        if use_mirror:
            factor = Vector((-unit_scale, unit_scale, unit_scale))
        else:
            factor = Vector((-unit_scale, unit_scale, unit_scale))
                
        children_map = {}
        hierarchy = []
        meshes = {}
        materials = set()
        volumes = []
        obstacles = []
        lights = []
        camera = None
        
        basename = add_ext(bpy.context.scene.name, '')
        
        # Create a dedicated subfolder based on the current Blender file's name.
        # This keeps the exported assets (.mdl, .ply, .mtl, etc.) grouped and organized.
        dir = path.join(dir, path.splitext(path.basename(bpy.data.filepath))[0])
        makedirs(dir, exist_ok=True)
        
        # Generate the engine's primary definition file (.def) if it doesn't already exist.
        # This file registers the asset as a game entity and links it to the main .mdl skeleton.
        if not path.isfile(path.join(dir, f'{basename}.def')):
            with open(path.join(dir, f'{basename}.def'), 'w', encoding='utf-8') as f:
                f.write(
                    '{game_entity\n'
                    f'\t{{extension "{basename}.mdl"}}\n'
                    '}'
                )

        with open(path.join(dir, f'{basename}.mdl'), 'w', encoding='utf-8') as f:
            # Initialize hierarchy map for all objects and bones
            for obj in bpy.context.scene.objects:
                children_map[obj] = []
                if obj.pose:
                    for bone in obj.pose.bones:
                        children_map[bone] = []

            # Rebuild hierarchy: Flattens Blender's split Object/Armature hierarchy into a unified skeleton tree.
            for obj in bpy.context.scene.objects:
                if obj.parent:
                    # The engine expects a continuous bone hierarchy. If an object is parented to a specific bone, 
                    # we link it directly to that bone and skip the Armature object entirely.
                    if obj.parent_type == 'BONE':
                        children_map[obj.parent.pose.bones[obj.parent_bone]].append(obj)
                    else:
                        children_map[obj.parent].append(obj)
                else:
                    hierarchy.append(obj)
                    
                if obj.pose:
                    for bone in obj.pose.bones:
                        if bone.parent:
                            children_map[bone.parent].append(bone)
                        else:
                            children_map[obj].append(bone)
        
            def write_properties(obj, level=1, pos=None):
                # Extracts local transforms. The target engine uses row-major matrices, requiring transposition.
                if type(obj) == bpy.types.PoseBone:
                    matrix = obj.matrix.copy()
                    if pos: 
                        matrix.translation = pos
                    if obj.parent: 
                        matrix = obj.parent.matrix.inverted() @ matrix
                else:
                    matrix = obj.matrix_world.copy()
                    if pos: 
                        matrix.translation = pos
                    if obj.parent: 
                        matrix = obj.parent.matrix_world.inverted() @ matrix

                matrix.translation *= factor
                matrix = matrix.transposed()
                
                if matrix != Matrix():
                    if matrix[3] != Vector((0, 0, 0, 1)):
                        if matrix.to_3x3() != Matrix().to_3x3():
                            # Write full 3x4 transformation matrix (3x3 rotation + 1x3 translation)
                            f.write(tab * level + f'{{matrix34\n')
                            for i in range(4):
                                f.write(tab * (level + 1) + f'{matrix[i][0]:.7g}\t{matrix[i][1]:.7g}\t{matrix[i][2]:.7g}\n')
                            f.write(tab * level + f'}}\n')
                        else:
                            # Optimization: Write translation only if rotation is identity
                            f.write(tab * level + f'{{position {matrix[3][0]:.7g}\t{matrix[3][1]:.7g}\t{matrix[3][2]:.7g}}}\n')
                    else:
                        # Optimization: Write rotation only if translation is zero
                        f.write(tab * level + f'{{orientation\n')
                        for i in range(3):
                            f.write(tab * (level + 1) + f'{matrix[i][0]:.7g}\t{matrix[i][1]:.7g}\t{matrix[i][2]:.7g}\n')
                        f.write(tab * level + f'}}\n')

            def get_children(obj, level=1):
                if type(obj) == bpy.types.PoseBone:
                    obj_type = bpy.types.PoseBone
                else:
                    obj_type = type(obj.data)
                    
                if obj_type == bpy.types.Camera:
                    camera = obj
                elif obj_type == bpy.types.PointLight:
                    lights.append(obj)
                elif obj.name.endswith('.vol'):
                    volumes.append(obj)
                    # A single mesh data block might be shared between a visual object and a collision volume.
                    # We register it here and track flags to ensure it gets exported correctly for both uses.
                    meshes.setdefault(obj.data, {'obj': None, 'mesh': False, 'volume': False})
                    if not meshes[obj.data]['obj']: 
                        meshes[obj.data]['obj'] = obj
                    meshes[obj.data]['volume'] = True
                else:
                    f.write(tab * level + f'{{bone "{add_ext(obj.name, "")}"\n')
                    write_properties(obj, level + 1)
                    
                    if obj_type == bpy.types.Mesh:
                        meshes.setdefault(obj.data, {'obj': None, 'mesh': False, 'volume': False})
                        meshes[obj.data]['mesh'] = True
                        if obj.vertex_groups or not meshes[obj.data]['obj']:
                            meshes[obj.data]['obj'] = obj
                        f.write(tab * (level + 1) + f'{{VolumeView "{add_ext(obj.data.name, ".ply")}"}}\n')
                        
                    for child in children_map[obj]:
                        get_children(child, level + 1)
                    f.write(tab * level + f'}}\n')

            # --- Start MDL Scene Graph ---
            f.write('{Skeleton\n')
            for obj in hierarchy:
                get_children(obj)
            f.write('}')

            # Write basic primitive collision shapes (sphere, cylinder, box) to the .mdl
            for obj in volumes:
                f.write(f'\n{{volume "{add_ext(obj.name, ".vol", remove=True)}"\n')
                if 'volume' in obj.data.keys():
                    vol_type = str(obj.data['volume']).lower()
                    dims = Vector(obj.bound_box[6]) - Vector(obj.bound_box[0])
                    if vol_type in ('1', 'sphere'):
                        f.write(f'\t{{sphere {max(dims)/2*unit_scale:.7g}}}\n')
                    elif vol_type in ('2', 'cylinder'):
                        f.write(f'\t{{cylinder {max(dims[0:2])/2:.7g}\t{dims[2]:.7g}}}\n')
                    elif vol_type in ('3', 'box'):
                        f.write(f'\t{{box {dims[0]*unit_scale:.7g}\t{dims[1]*unit_scale:.7g}\t{dims[2]*unit_scale:.7g}}}\n')
                    
                    # Blender pivot points can be arbitrary, but the engine generates primitives strictly from 
                    # their geometric center. We calculate the true center here and override the position.
                    pos = Vector(obj.location) + Vector(obj.bound_box[0]) + (Vector(obj.bound_box[6]) - Vector(obj.bound_box[0])) / 2
                    write_properties(obj, pos=pos)
                else:
                    f.write(f'\t{{polyhedron "{add_ext(obj.data.name, ".vol")}"}}\n')
                    write_properties(obj)
                f.write(f'\t{{bone "{add_ext(obj.parent.name, "")}"}}\n')
                f.write('}')

        # --- Binary Geometry Export Phase ---
        for mesh in meshes:
            loop_tris = mesh.loop_triangles
            edges_count = len(loop_tris) * 3
            # Limit enforced by standard 16-bit unsigned integer index buffers
            if edges_count > 0xffff: 
                raise Exception(f"Mesh '{mesh.name}'s edges count ({edges_count}) exceeds the limit {0xffff}")

            vertices = mesh.vertices
            coords = [vertex.co * factor for vertex in vertices]

            # Binary Export: Custom polyhedron collision geometry (EVLM format)
            if meshes[mesh]['volume']:
                # Primitives (box/sphere) were already defined purely via dimensions in the .mdl above.
                # We skip them here to avoid uselessly exporting their raw geometry as a custom polyhedron.
                if 'volume' not in mesh.keys():
                    vertices_count = len(vertices)
                    if vertices_count > 0xffff: 
                        raise Exception(f"Mesh '{mesh.name}''s vertices count ({vertices_count}) exceeds the limit {0xffff}")

                    with open(path.join(dir, add_ext(mesh.name, '.vol')), 'w+b') as f:
                        f.write(b'EVLM') 
                        f.write(b'VERT')
                        f.write(pack_I(vertices_count))
                        for co in coords:
                            f.write(pack_fff(*co))

                        f.write(b'INDX')
                        f.write(pack_I(edges_count))
                        for tri in loop_tris:
                            f.write(pack_HHH(*tri.vertices))

                        f.write(b'SIDE')
                        f.write(pack_I(edges_count // 3))
                        for tri in loop_tris:
                            # Material index acts as collision face properties ID
                            f.write(pack_B(tri.material_index + 1)) 

            # Binary Export: Visual render geometry (EPLY format)
            if meshes[mesh]['mesh']:
                loops_count = len(mesh.loops)
                if loops_count > 0xffff: 
                    raise Exception(f"Mesh '{mesh.name}'s loops/UVs count ({loops_count}) exceeds the limit {0xffff}")
                if not mesh.uv_layers.active: 
                    raise Exception(f"Mesh '{mesh.name} has no UV layers")
                if not mesh.materials: 
                    raise Exception(f"Mesh '{mesh.name}' has no materials")
                
                obj = meshes[mesh]['obj']
                bones_count = len(obj.vertex_groups)
                has_skin = bool(bones_count)
                # Max 254 vertex groups supported due to 8-bit bone indexing limits in the shader
                if bones_count > 0xfe: 
                    raise Exception(f"Mesh '{mesh.name}'s vertex groups count ({bones_count}) exceeds the limit {0xfe}")

                with open(path.join(dir, add_ext(mesh.name, '.ply')), 'w+b') as f:
                    f.write(b'EPLY')

                    f.write(b'BNDS')
                    f.write(pack_fff(*obj.bound_box[0]))
                    f.write(pack_fff(*obj.bound_box[6]))

                    weights_count = 0
                    if has_skin:
                        f.write(b'SKIN')
                        weights_count = 2  # Engine assumes max 2 blend weights per vertex
                        f.write(pack_I(bones_count))
                        for bone in obj.vertex_groups:
                            f.write(pack_B(len(bone.name)))
                            f.write(bone.name.encode())

                    tri_start = 0
                    # Group triangles by material to construct contiguous draw calls/sub-meshes
                    tris_by_mat_list = [[] for _ in mesh.materials]
                    for tri in loop_tris:
                        tris_by_mat_list[tri.material_index].append(tri)

                    # Submesh Definition Header Block
                    for i in range(len(tris_by_mat_list)):
                        f.write(b'MESH')
                        # Combine FVF flags to define the vertex memory layout for this subset
                        f.write(pack_I(D3DFVF_NORMAL | D3DFVF_TEX1 | ((D3DFVF_XYZB2 | D3DFVF_LASTBETA_UBYTE4) if has_skin else D3DFVF_XYZ)))
                        f.write(pack_I(tri_start))
                        
                        tri_count = len(tris_by_mat_list[i])
                        f.write(pack_I(tri_count))
                        tri_start += tri_count
                        
                        f.write(pack_I(MESH_FLAG_LIGHT | MESH_FLAG_MATERIAL | MESH_FLAG_BUMP | (MESH_FLAG_SKINNED | MESH_FLAG_SUBSKIN if weights_count else 0)))
                        
                        # Fallback handles empty material slots added by users without a real material assigned
                        try:
                            material_name = mesh.materials[i].name
                        except:
                            material_name = ''
                        
                        # Register material for .mtl generation later
                        materials.add(mesh.materials[i])
                        material_name = add_ext(material_name, '.mtl')
                        
                        f.write(pack_B(len(material_name)))
                        f.write((material_name).encode())
                        if has_skin:
                            f.write(pack_H(bones_count + 1))
                            f.write(struct.pack('B' * bones_count, *(i + 1 for i in range(bones_count))))

                    # Vertex Buffer Block
                    f.write(b'VERT')
                    f.write(pack_I(loops_count))
                    # Stride: 12 (pos) + 12 (norm) + 8 (uv) + 16 (bump). Add 8 for skin weights/indices if skinned.
                    f.write(pack_H(48 + 8 * has_skin)) 
                    f.write(b'\x07\x00')  # Engine-specific padding or unknown alignment flags

                    uvs = [uv.uv for uv in mesh.uv_layers.active.data]
                    if has_skin:
                        # Extract only the two strongest bone weights per vertex (engine hardware limit)
                        vertex_weights = [
                            [(g.weight, g.group + 1) for g in heapq.nlargest(2, vertex.groups, key=lambda g: g.weight)]
                            for vertex in vertices
                        ]

                    for loop in mesh.loops:
                        f.write(pack_fff(*(coords[loop.vertex_index])))
                        if has_skin:
                            weights_list = vertex_weights[loop.vertex_index]
                            
                            # The UBYTE4 flag requires exactly 4 bytes for bone indices in the buffer for 
                            # memory alignment, so we pad it to length 4 even though we only use 2 weights.
                            weights_list.extend([(0, 0)] * (4 - len(weights_list)))
                            
                            # Normalize weights so the top two always equal 1.0 (prevents mesh distortion)
                            try:
                                inv = 1 / (weights_list[0][0] + weights_list[1][0])
                            except:
                                inv = 1
                            f.write(pack_f(weights_list[0][0] * inv))
                            f.write(pack_BBBB(*(weight[1] for weight in weights_list)))
                            
                        f.write(pack_fff(*loop.normal))
                        uv = uvs[loop.index]
                        # 1-uv[1] flips the V coordinate from Blender's OpenGL space (bottom-left) to DirectX space (top-left)
                        f.write(pack_ff(uv[0], 1 - uv[1]))
                        f.write(pack_fff(*loop.tangent))
                        f.write(pack_f(loop.bitangent_sign))

                    # Index Buffer Block
                    f.write(b'INDX')
                    f.write(pack_I(edges_count))
                    for tri_list in tris_by_mat_list:
                        for tri in tri_list:
                            if use_mirror:
                                # Reverse vertex winding order so normals remain correct when scaled negatively
                                f.write(pack_HHH(*tuple(tri.loops)[::-1]))
                            else:
                                f.write(pack_HHH(*tri.loops))
        
        # --- Write Material (.mtl) and Texture Lists (.txt) ---
        for mtl in materials:
            with open(path.join(dir, add_ext(mtl.name, '.mtl')), 'w', encoding='utf-8') as f:
                f.write('{material bump\n')
                f.write(f'\t{{diffuse "{add_ext(mtl.name, "")}"}}\n')
                f.write(f'\t{{bump "{add_ext(mtl.name, "_bp")}"}}\n')
                f.write(f'\t{{specular "{add_ext(mtl.name, "_sp")}"}}\n')
                f.write('\t{color "255 255 255 25"}\n')
                f.write('\t{blend test}\n')
                f.write('}')
            
            # Extract the original image filenames used in the Blender material's node tree.
            # This helper .txt file is incredibly useful for batch converting or tracking external assets.
            with open(path.join(dir, add_ext(mtl.name, '.txt')), 'w', encoding='utf-8') as f:
                for node in mtl.node_tree.nodes:
                    if node.type == 'TEX_IMAGE':
                        if node.image:
                            f.write(f'{path.splitext(path.basename(node.image.name))[0]}\n')
        
        return {'FINISHED'}

    except Exception as e:
        import traceback
        traceback.print_exc()
        operator.report({'ERROR'}, tip_(f"{e}"))
        return {'CANCELLED'}
