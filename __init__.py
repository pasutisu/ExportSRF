# ========================================
# SURF/DynaModel Plugin for Blender
#
# Copyright (c) 2016 Mr Mofumofu
# ========================================

import os

import bpy
import bmesh
import mathutils
from bpy.props import (BoolProperty, FloatProperty, StringProperty, EnumProperty)
from bpy_extras.io_utils import (ImportHelper, ExportHelper)

# Infomation
bl_info = {
    'name'       : 'SURF/DynaModel Format',
    'description': 'Import/Export SURF/DynaModel Format.',
    'author'     : 'Mr Mofumofu',
    'version'    : (3, 6),
    'blender'    : (2, 75, 0),
    'location'   : 'File > Import-Export',
    'warning'    : '',
    'wiki_url'   : '',
    'category'   : 'Import-Export'
}

# Surface Class
class Surface:
    # Getting Data
    def __init__(self, obj, scene, scale=1.0, parts=False):
        self.obj = obj
        # Apply Modifier
        bpy.context.scene.objects.active = obj
        bpy.ops.object.modifier_apply(modifier='EdgeSplit')
        # Set Location and Scale
        self.location = obj.location
        self.scale = scale
        # File name
        self.name = '{}.srf'.format(self.obj.name)
        if parts:
            self.name = 'parts/{}.srf'.format(self.obj.name)
        # ID
        self.uid = SurfMan().getUID()
        SurfMan().addUID()
        self.children = []

        for objs in (ob for ob in obj.children if ob.is_visible(scene) and ob.type == 'MESH'):
            self.children.append(SurfMan().getUID())
            SurfMan().addList(Surface(objs, scene, scale, parts))

    # PCK Node
    def pck(self, parts=False, ground=False):
        # ==============================
        # Getting Data
        # ==============================
        # Convert to BMesh(For N-Sided Polygon)
        bm = bmesh.new()
        bm.from_mesh(self.obj.data)
        # Transform
        ys_matrix = mathutils.Matrix((
            (-1.0 * self.scale,  0.0,  0.0,  0.0),
            ( 0.0,  0.0,  1.0 * self.scale,  0.0),
            ( 0.0, -1.0 * self.scale,  0.0,  0.0),
            ( 0.0,  0.0,  0.0,  1.0),
        ))
        bm.transform(ys_matrix * self.obj.matrix_world)
        bm.normal_update()
        # Set Axis
        local_axis = ys_matrix.to_3x3() * self.obj.location
        # Vertexs and Faces
        verts = bm.verts
        faces = bm.faces

        # ==============================
        # Output
        # ==============================
        output = ''
        za = ''
        zacount = 0

        # Header
        output += 'SURF\n'

        # Vertexs
        for vert in verts:
            vertex = vert.co - local_axis
            output += 'V {:.5f} {:.5f} {:.5f} '.format(*vertex)
            # Smoothing
            for face in vert.link_faces:
                if face.smooth:
                    output += 'R'
                    break
            output += '\n'

        # Faces
        for face in faces:
            output += 'F\n'

            # Has Material?
            if len(self.obj.material_slots):
                # Getting Material
                material = self.obj.material_slots[face.material_index].material
                # Color
                color = material.diffuse_color * 255.0
                output += 'C {:.0f} {:.0f} {:.0f}\n'.format(*color)
                # Lighting
                if material.emit > 0.0:
                    output += 'B\n'
                # Transparent
                if material.alpha < 1.0:
                    if zacount == 0:
                        za += 'ZA {:d} {:.0f}'.format(face.index, (1.0 - material.alpha) * 228.0)
                    elif zacount % 8 == 0:
                        za += '\nZA {:d} {:.0f}'.format(face.index, (1.0 - material.alpha) * 228.0)
                    else:
                        za += ' {:d} {:.0f}'.format(face.index, (1.0 - material.alpha) * 228.0)
                    zacount = zacount + 1

            # Median and Normal
            median = face.calc_center_median_weighted() - local_axis
            normal = -face.normal
            if SurfMan().flip:
                normal = face.normal
            output += 'N {:.5f} {:.5f} {:.5f} '.format(*median)
            output += '{:.5f} {:.5f} {:.5f}\n'.format(*normal)

            # Vertexs consist Face
            output += 'V'
            face_verts = ''
            for vid in face.verts:
                face_verts = ' {:d}{}'.format(vid.index, face_verts)
            output += face_verts
            output += '\n'
            output += 'E\n'

        # Footer
        output += 'E\n'

        # For Transparent
        if za != '':
            output += za + '\n'

        # Finalize
        length = len(output.split('\n')) - 1
        result = 'PCK {} {:d}\n{}\n'.format(self.name, length, output)
        if parts:
            result = output
        if ground:
            result = 'PCK {}.srf {:d}\n{}\n'.format(self.name.split('.')[0], length, output)

        # ==============================
        # Close
        # ==============================
        bm.free()

        return result

    #　SRF Node
    def srf(self):
        # ==============================
        # Getting Data
        # ==============================
        # Transform
        ys_matrix = mathutils.Matrix((
            (-1.0 * self.scale,  0.0,  0.0,  0.0),
            ( 0.0,  0.0,  1.0 * self.scale,  0.0),
            ( 0.0, -1.0 * self.scale,  0.0,  0.0),
            ( 0.0,  0.0,  0.0,  1.0),
        ))
        # Set Axis
        local_axis = ys_matrix.to_3x3() * self.obj.location
        local_rotate = [
            -self.obj.rotation_euler.z * 10430.37835,
            self.obj.rotation_euler.x * 10430.37835,
            -self.obj.rotation_euler.y * 10430.37835,
        ]

        # ==============================
        # Output
        # ==============================
        output = ''

        # Status
        output += 'SRF "{:04d}"\n'.format(self.uid)
        output += 'FIL {}\n'.format(self.name)
        output += 'CLA 0\n'
        output += 'NST 0\n'

        # Support Axis Export
        if self.obj.parent is not None:
            local_axis_parent = ys_matrix.to_3x3() * self.obj.parent.location
            local_axis_pos = local_axis - local_axis_parent
            if local_axis_parent == (0, 0, 0):
                output += 'POS 0.0000 0.0000 0.0000 {:.0f} {:.0f} {:.0f} 1\n'.format(*local_rotate)
                output += 'CNT {:.5f} {:.5f} {:.5f}\n'.format(*local_axis)
            else:
                output += 'POS {:.5f} {:.5f} {:.5f} '.format(*local_axis_pos)
                output += '{:.0f} {:.0f} {:.0f} 1\n'.format(*local_rotate)
                output += 'CNT 0.0000 0.0000 0.0000\n'
        else:
            output += 'POS 0.0000 0.0000 0.0000 {:.0f} {:.0f} {:.0f} 1\n'.format(*local_rotate)
            output += 'CNT {:.5f} {:.5f} {:.5f}\n'.format(*local_axis)

        # Support Parent-Children Relation Export
        output += 'REL DEP\n'
        output += 'NCH {:d}\n'.format(len(self.children))
        for uid in self.children:
            output += 'CLD "{:04d}"\n'.format(uid)
        output += 'END\n'

        return output

# Surface Manager
class SurfMan(object):
    _instance = None
    _list = []
    _saved = []
    _uid = 0
    flip = False

    # Singleton
    def __new__(this, *argarray, **argdict):
        if this._instance is None:
            this._instance = object.__new__(this, *argarray, **argdict)
        return this._instance

    # Add List
    def addList(self, obj):
        if not obj.name in self._saved:
            self._list.append(obj)
            self._saved.append(obj.name)

    # Get List
    def getList(self):
        return self._list

    # Add UID
    def addUID(self):
        self._uid = self._uid + 1

    # Get UID
    def getUID(self):
        return self._uid

    # Finalize
    def free(self):
        self._list = []
        self._saved = []
        self._uid = 0

# Import SURF
class ImportSRF(bpy.types.Operator, ImportHelper):
    # Settings
    bl_idname = 'import_model.srf'
    bl_label = 'Import SURF'
    filter_glob = StringProperty(
        default = '*.srf',
        options = {'HIDDEN'},
    )
    check_extension = True
    filename_ext = '.srf'

    # On Click Save Button
    def execute(self, context):
        # Generate
        mesh = self.load(context, self.filepath)
        obj = bpy.data.objects.new(mesh.name, mesh)
        # Currently Scene
        scene = bpy.context.scene
        scene.objects.link(obj)
        scene.update()

        return {'FINISHED'}

    def load(self, context, filename):
        file_path = os.fsencode(filename)
        with open(file_path, 'r') as file_stream:
            # Stacks
            verts = []
            faces = []
            materials = {}
            # Flags
            vert_flag = True
            face_flag = False
            # Temps
            mat_tmp = {}
            face_tmp = {}

            # Reader
            for line_raw in file_stream:
                # Split with space
                line_split = line_raw.rstrip().split(' ')
                # Line idents like 'V' and 'F'...
                line_ident = line_split[0]
                # Vertex
                if line_ident == 'V':
                    if vert_flag:
                        smoothing = False
                        if len(line_split) == 5:
                            smoothing = True
                        verts.append({
                            'vert' : [
                                float(line_split[1]),
                                float(line_split[2]),
                                float(line_split[3]),
                            ],
                            'round' : smoothing,
                        })
                    else:
                        for vert_no in line_split[1:]:
                            face_tmp['vert'].append(int(vert_no))
                # Face
                elif line_ident == 'F':
                    vert_flag = False
                    face_flag = True
                    face_tmp['vert'] = []
                # Color
                elif line_ident == 'C':
                    if len(line_split) > 2:
                        mat_tmp = {
                            'color' : [
                                int(line_split[1])/255,
                                int(line_split[2])/255,
                                int(line_split[3])/255,
                            ],
                            'bright' : 0.0,
                        }
                    else:
                        c=int(line_split[1]) & 32767
                        g=((c>>10)&31)/31
                        r=((c>> 5)&31)/31
                        b=((c    )&31)/31
                        mat_tmp = {
                            'color' : [
                                r,
                                g,
                                b,
                            ],
                            'bright' : 0.0,
                        }
                # Self Brighting
                elif line_ident == 'B':
                    mat_tmp['bright'] = 2.0
                # End of Statement
                elif line_ident == 'E':
                    # End of Face
                    if face_flag:
                        # Material Matching
                        if mat_tmp not in materials.values():
                            # Create Material
                            materials[len(materials.values()) + 1] = mat_tmp
                            face_tmp['mats'] = len(materials.values())
                        # Material Key Finding
                        else:
                            for key, var in materials.items():
                                if var == mat_tmp:
                                    face_tmp['mats'] = key
                        faces.append(face_tmp)
                        # Temp Cleaning
                        face_tmp = {}
                        mat_tmp = {}
                        face_flag = False
                    # End of SURF
                    else:
                        break

            # Generate Mesh
            file_name = bpy.path.display_name_from_filepath(file_path)
            mesh = bpy.data.meshes.new(
                name = file_name,
            )
            # Convert Mesh
            mesh.from_pydata(
                [vert['vert'] for vert in verts],
                [],
                [vert['vert'] for vert in faces],
            )

            # Convert Material
            for key, var in materials.items():
                material = bpy.data.materials.new('{}{}'.format(file_name, key))
                material.diffuse_color = [
                    var['color'][0],
                    var['color'][1],
                    var['color'][2],
                ]
                material.emit = var['bright']
                mesh.materials.append(material)

            # Set Material
            for orig, blender in zip(faces, mesh.polygons):
                blender.material_index = orig['mats'] - 1
                for face_count in orig['vert']:
                    if verts[face_count - 1]['round']:
                        blender.use_smooth = True

            # Fix Mesh
            bm = bmesh.new()
            bm.from_mesh(mesh)
            # Transform
            ys_matrix = mathutils.Matrix((
                (-1.0,  0.0,  0.0,  0.0),
                ( 0.0,  0.0, -1.0,  0.0),
                ( 0.0,  1.0,  0.0,  0.0),
                ( 0.0,  0.0,  0.0, -1.0),
            ))
            bm.transform(ys_matrix)
            # Calc Normal
            bm.normal_update()
            # Calc Normal
            for face in bm.faces:
                face.normal_flip()
            bm.to_mesh(mesh)
            return mesh

# Import DNM
class ImportDNM(bpy.types.Operator, ImportHelper):
    # Settings
    bl_idname = 'import_model.dnm'
    bl_label = 'Import DNM'
    filter_glob = StringProperty(
        default = '*.dnm',
        options = {'HIDDEN'},
    )
    check_extension = True
    filename_ext = '.dnm'

    # On Click Save Button
    def execute(self, context):
        # Generate
        self.load(context, self.filepath)
        # Scene Update
        context.scene.update()
        return {'FINISHED'}

    def load(self, context, filename):
        file_path = os.fsencode(filename)
        with open(file_path, 'r') as file_stream:
            # Stacks
            verts = []
            faces = []
            materials = {}
            material_blender = []
            # Flags
            vert_flag = True
            face_flag = False
            # Temps
            surf_name = ""
            mat_tmp = {}
            face_tmp = {}

            # Reader
            for line_raw in file_stream:
                # Split with space
                line_split = line_raw.rstrip().split(' ')
                # Line idents like 'V' and 'F'...
                line_ident = line_split[0]
                # PCK Node
                if line_ident == 'PCK':
                    surf_name = line_split[1]
                # Vertex
                elif line_ident == 'V':
                    if vert_flag:
                        smoothing = False
                        if len(line_split) == 5:
                            smoothing = True
                        verts.append({
                            'vert' : [
                                float(line_split[1]),
                                float(line_split[2]),
                                float(line_split[3]),
                            ],
                            'round' : smoothing,
                        })
                    else:
                        face_tmp['vert'] = [int(vert) for vert in line_split[1:]]
                # Face
                elif line_ident == 'F':
                    vert_flag = False
                    face_flag = True
                # Color
                elif line_ident == 'C':
                    if len(line_split) > 2:
                        mat_tmp = {
                            'color' : [
                                int(line_split[1])/255,
                                int(line_split[2])/255,
                                int(line_split[3])/255,
                            ],
                            'bright' : 0.0,
                        }
                    else:
                        c=int(line_split[1]) & 32767
                        g=((c>>10)&31)/31
                        r=((c>> 5)&31)/31
                        b=((c    )&31)/31
                        mat_tmp = {
                            'color' : [
                                r,
                                g,
                                b,
                            ],
                            'bright' : 0.0,
                        }
                # Self Brighting
                elif line_ident == 'B':
                    mat_tmp['bright'] = 2.0
                # End of Statement
                elif line_ident == 'E':
                    # End of Face
                    if face_flag:
                        # Material Matching
                        if mat_tmp not in materials.values():
                            # Create Material
                            materials[len(materials.values()) + 1] = mat_tmp
                            face_tmp['mats'] = len(materials.values())
                            # Convert Material
                            material = bpy.data.materials.new('Material{}'.format(len(materials.values())))
                            material.diffuse_color = [
                                mat_tmp['color'][0],
                                mat_tmp['color'][1],
                                mat_tmp['color'][2],
                            ]
                            material.emit = mat_tmp['bright']
                            material_blender.append(material)
                        # Material Key Finding
                        else:
                            for key, var in materials.items():
                                if var == mat_tmp:
                                    face_tmp['mats'] = key
                        faces.append(face_tmp)
                        # Temp Cleaning
                        face_tmp = {}
                        mat_tmp = {}
                        face_flag = False
                    # End of SURF
                    else:
                        # Generate Mesh
                        mesh = bpy.data.meshes.new(
                            name = surf_name.split('.')[0],
                        )
                        # Convert Mesh
                        mesh.from_pydata(
                            [vert['vert'] for vert in verts],
                            [],
                            [vert['vert'] for vert in faces],
                        )

                        # Set Material
                        for orig, blender in zip(faces, mesh.polygons):
                            blender.material_index = orig['mats'] - 1
                            for face_count in orig['vert']:
                                if verts[face_count - 1]['round']:
                                    blender.use_smooth = True


                        for var in material_blender:
                            mesh.materials.append(var)

                        # Fix Mesh
                        bm = bmesh.new()
                        bm.from_mesh(mesh)
                        # Transform
                        ys_matrix = mathutils.Matrix((
                            (-1.0,  0.0,  0.0,  0.0),
                            ( 0.0,  0.0, -1.0,  0.0),
                            ( 0.0,  1.0,  0.0,  0.0),
                            ( 0.0,  0.0,  0.0, -1.0),
                        ))
                        bm.transform(ys_matrix)
                        # Calc Normal
                        bm.normal_update()
                        bm.to_mesh(mesh)
                        # Create Object
                        obj = bpy.data.objects.new(mesh.name, mesh)
                        scene = bpy.context.scene
                        scene.objects.link(obj)

                        #Cleaning
                        verts = []
                        faces = []
                        vert_flag = True
                        face_flag = False
                        surf_name = ""
            return True

# Export SURF
class ExportSRF(bpy.types.Operator, ExportHelper):
    # Settings
    bl_idname = 'export_model.srf'
    bl_label = 'Export SURF'
    filter_glob = StringProperty(
        default = '*.srf',
        options = {'HIDDEN'},
    )
    check_extension = True
    filename_ext = '.srf'

    transform = EnumProperty(
        name='Apply Transform(Fix)',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    flip_normal = EnumProperty(
        name='Flip Normal(Fix)',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    twoside_normal = EnumProperty(
        name='Two Side Normal',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    # On Click Save Button
    def execute(self, context):
        # Apply Transform
        if self.transform == 'On':
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            bpy.ops.ed.undo()

        # Currently Scene
        scene = context.scene
        filepath = os.fsencode(self.filepath)
        fp = open(filepath, 'w')

        # Selected Object
        fp.write(self.export(scene.objects.active))

        return {'FINISHED'}

    def export(self, obj):
        # ==============================
        # Getting Data
        # ==============================
        # Convert to BMesh(For N-Sided Polygon)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        # Transform
        ys_matrix = mathutils.Matrix((
            (-1.0,  0.0,  0.0,  0.0),
            ( 0.0,  0.0,  1.0,  0.0),
            ( 0.0, -1.0,  0.0,  0.0),
            ( 0.0,  0.0,  0.0,  1.0),
        ))
        bm.transform(ys_matrix * obj.matrix_world)
        bm.normal_update()
        # Set Axis
        local_axis = ys_matrix.to_3x3() * obj.location
        # Vertexs and Faces
        verts = bm.verts
        faces = bm.faces

        # ==============================
        # Output
        # ==============================
        output = ''
        za = ''
        zacount = 0

        # Header
        output += 'SURF\n'

        # Vertexs
        for vert in verts:
            vertex = vert.co - local_axis
            output += 'V {:.5f} {:.5f} {:.5f} '.format(*vertex)
            # Smoothing
            smooth = True
            for edge in vert.link_edges:
                if edge.smooth == False:
                    smooth = False
                    break
            if smooth:
                for face in vert.link_faces:
                    if face.smooth:
                        output += 'R'
                        break
            output += '\n'

        # Faces
        for face in faces:
            output += 'F\n'

            # Has Material?
            if len(obj.material_slots):
                # Getting Material
                material = obj.material_slots[face.material_index].material
                # Color
                color = material.diffuse_color * 255.0
                output += 'C {:.0f} {:.0f} {:.0f}\n'.format(*color)
                # Lighting
                if material.emit > 0.0:
                    output += 'B\n'
                # Transparent
                if material.alpha < 1.0:
                    if zacount == 0:
                        za += 'ZA {:d} {:.0f}'.format(face.index, (1.0 - material.alpha) * 228.0)
                    elif zacount % 8 == 0:
                        za += '\nZA {:d} {:.0f}'.format(face.index, (1.0 - material.alpha) * 228.0)
                    else:
                        za += ' {:d} {:.0f}'.format(face.index, (1.0 - material.alpha) * 228.0)
                    zacount = zacount + 1

            # Median and Normal
            median = face.calc_center_median_weighted() - local_axis
            # Flip Normal
            if self.flip_normal == 'On':
                normal = face.normal
            else:
                normal = -face.normal
            if self.twoside_normal == 'On':
                output += 'N {:.5f} {:.5f} {:.5f} '.format(*median)
                output += '0.000 0.000 0.000\n'
            else:
                output += 'N {:.5f} {:.5f} {:.5f} '.format(*median)
                output += '{:.5f} {:.5f} {:.5f}\n'.format(*normal)

            # Vertexs consist Face
            output += 'V'
            face_verts = ''
            for vid in face.verts:
                face_verts = ' {:d}{}'.format(vid.index, face_verts)
            output += face_verts
            output += '\n'
            output += 'E\n'

        # Footer
        output += 'E\n'

        # For Transparent
        if za != '':
            output += za + '\n'

        # ==============================
        # Close
        # ==============================
        bm.free()

        return output

# Export DNM
class ExportDNM(bpy.types.Operator, ExportHelper):
    # Settings
    bl_idname = 'export_model.dnm'
    bl_label = 'Export DNM Model'
    filter_glob = StringProperty(
        default = '*.dnm',
        options = {'HIDDEN'},
    )
    check_extension = True
    filename_ext = '.dnm'

    transform = EnumProperty(
        name='Apply Transform(Fix)',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    flip_normal = EnumProperty(
        name='Flip Normal(Fix)',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    scale = FloatProperty(
        name='Scale',
        subtype='UNSIGNED',
        unit='LENGTH',
        default=1.0,
    )


    # On Click Save Button
    def execute(self, context):
        # ==============================
        # Getting Data
        # ==============================
        # Apply Transform
        if self.transform == 'On':
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            bpy.ops.ed.undo()
        # Flip Normal
        if self.flip_normal == 'On':
            SurfMan().flip = True
        # Currently Scene
        scene = context.scene

        # Selected Object
        for obj in (ob for ob in scene.objects if ob.is_visible(scene) and ob.type == 'MESH'):
            if obj.type == 'MESH':
                SurfMan().addList(Surface(obj, scene, self.scale))

        # ==============================
        # Output
        # ==============================
        # Save File
        filepath = os.fsencode(self.filepath)
        fp = open(filepath, 'w')

        # Header
        fp.write('DYNAMODEL\n')
        fp.write('DNMVER 1\n')

        # PCK Node
        for surf in SurfMan().getList():
            fp.write(surf.pck())

        # SRF Node
        for surf in SurfMan().getList():
            fp.write(surf.srf())

        # Footer
        fp.write('END\n')

        # ==============================
        # Close
        # ==============================
        SurfMan().free()
        fp.close()

        return {'FINISHED'}

# Export PCK
class ExportPCK(bpy.types.Operator, ExportHelper):
    # Settings
    bl_idname = 'export_model.pck'
    bl_label = 'Export PCK Node'
    filter_glob = StringProperty(
        default = '*.dnm',
        options = {'HIDDEN'},
    )
    check_extension = True
    filename_ext = '.dnm'

    transform = EnumProperty(
        name='Apply Transform(Fix)',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    flip_normal = EnumProperty(
        name='Flip Normal(Fix)',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    scale = FloatProperty(
        name='Scale',
        subtype='UNSIGNED',
        unit='LENGTH',
        default=1.0,
    )


    # On Click Save Button
    def execute(self, context):
        # ==============================
        # Getting Data
        # ==============================
        # Apply Transform
        if self.transform == 'On':
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            bpy.ops.ed.undo()
        # Flip Normal
        if self.flip_normal == 'On':
            SurfMan().flip = True
        # Currently Scene
        scene = context.scene

        # Selected Object
        for obj in (ob for ob in scene.objects if ob.is_visible(scene) and ob.type == 'MESH'):
            if obj.type == 'MESH':
                SurfMan().addList(Surface(obj, scene, self.scale))

        # ==============================
        # Output
        # ==============================
        # Save File
        filepath = os.fsencode(self.filepath)
        fp = open(filepath, 'w')

        # Header
        fp.write('DYNAMODEL\n')
        fp.write('DNMVER 1\n')

        # PCK Node
        for surf in SurfMan().getList():
            fp.write(surf.pck())

        # ==============================
        # Close
        # ==============================
        SurfMan().free()
        fp.close()

        return {'FINISHED'}

# Explode DNM
class ExplodeDNM(bpy.types.Operator, ExportHelper):
    # Settings
    bl_idname = 'explode_model.dnm'
    bl_label = 'Explode DNM Model'

    filter_glob = StringProperty(
        default = '*.dnm',
        options = {'HIDDEN'},
    )
    check_extension = True
    filename_ext = '.dnm'

    transform = EnumProperty(
        name='Apply Transform(Fix)',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    flip_normal = EnumProperty(
        name='Flip Normal(Fix)',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    scale = FloatProperty(
        name='Scale',
        subtype='UNSIGNED',
        unit='LENGTH',
        default=1.0,
    )

    # On Click Save Button
    def execute(self, context):
        # ==============================
        # Getting Data
        # ==============================
        # Apply Transform
        if self.transform == 'On':
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            bpy.ops.ed.undo()
        # Flip Normal
        if self.flip_normal == 'On':
            SurfMan().flip = True
        # Currently Scene
        scene = context.scene

        # Selected Object
        for obj in (ob for ob in scene.objects if ob.is_visible(scene) and ob.type == 'MESH'):
            if obj.type == 'MESH':
                SurfMan().addList(Surface(obj, scene, self.scale, True))

        # ==============================
        # Output
        # ==============================
        # Save File
        filepath = os.fsencode(self.filepath)
        fp = open(filepath, 'w')

        # Header
        fp.write('DYNAMODEL\n')
        fp.write('DNMVER 1\n')

        # PCK Node
        for surf in SurfMan().getList():
            filepath = os.fsencode('{}/{}'.format(os.path.dirname(self.filepath), surf.name))
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            pck = open(filepath, 'w')
            pck.write(surf.pck(True))
            pck.close()

        # SRF Node
        for surf in SurfMan().getList():
            fp.write(surf.srf())

        # Footer
        fp.write('END\n')

        # ==============================
        # Close
        # ==============================
        SurfMan().free()
        fp.close()

        return {'FINISHED'}

# Explode SRF
class ExplodeSRF(bpy.types.Operator, ExportHelper):
    # Settings
    bl_idname = 'explode_model.srf'
    bl_label = 'Explode DNM Model'

    filter_glob = StringProperty(
        default = '*.dnm',
        options = {'HIDDEN'},
    )
    check_extension = True
    filename_ext = '.dnm'

    transform = EnumProperty(
        name='Apply Transform(Fix)',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    flip_normal = EnumProperty(
        name='Flip Normal(Fix)',
        items=(
            ('On', 'On', ''),
            ('Off', 'Off', ''),
        ),
        default='Off',
    )

    scale = FloatProperty(
        name='Scale',
        subtype='UNSIGNED',
        unit='LENGTH',
        default=1.0,
    )

    # On Click Save Button
    def execute(self, context):
        # ==============================
        # Getting Data
        # ==============================
        # Apply Transform
        if self.transform == 'On':
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            bpy.ops.ed.undo()
        # Flip Normal
        if self.flip_normal == 'On':
            SurfMan().flip = True
        # Currently Scene
        scene = context.scene

        # Selected Object
        for obj in (ob for ob in scene.objects if ob.is_visible(scene) and ob.type == 'MESH'):
            if obj.type == 'MESH':
                SurfMan().addList(Surface(obj, scene, self.scale, True))

        # ==============================
        # Output
        # ==============================
        # PCK Node
        for surf in SurfMan().getList():
            filepath = os.fsencode('{}/{}'.format(os.path.dirname(self.filepath), surf.name))
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            pck = open(filepath, 'w')
            pck.write(surf.pck(True))
            pck.close()

        # ==============================
        # Close
        # ==============================
        SurfMan().free()

        return {'FINISHED'}

# Export FLD
class ExportFLD(bpy.types.Operator, ExportHelper):
    # Settings
    bl_idname = 'export_model.fld'
    bl_label = 'Export FLD'
    filter_glob = StringProperty(
        default = '*.fld',
        options = {'HIDDEN'},
    )
    check_extension = True
    filename_ext = '.fld'

    # On Click Save Button Handler
    def execute(self, context):
        # Get Currently Scene
        scene = context.scene
        # Open
        filepath = os.fsencode(self.filepath)
        fp = open(filepath, 'w')
        pck = 'FIELD\nGND 0 0 128\nSKY 192 224 255\nDEFAREA NOAREA\n'
        pc2 = ''
        gnd = ''
        srf = ''
        saved_pc2 = []
        saved_srf = []

        # All Object
        for obj_pair in sorted(scene.objects.items(), key=lambda x: x[0]):
            # ==============================
            # Get Settings from Object Name
            # ==============================
            # like
            # 001RUNWAY.POLY.20
            # means
            # [Object Name].[Object Type].[Destination]
            obj = obj_pair[1]
            stats = obj.name.split('.')
            if obj.is_visible(scene) and obj.type == 'MESH' and len(stats) >= 3:
                if stats[1] == 'GND':
                    # ==============================
                    # Ground Object
                    # ==============================
                    name = stats[0]
                    iff = int(stats[2])
                    gnd += self.exportGround(obj, name, iff)
                elif stats[1] == 'SRF':
                    # ==============================
                    # SRF Object
                    # ==============================

                    # Get Destination
                    name = stats[0]
                    output = self.exportSRF(obj, scene)

                    # File Output
                    if not name in saved_srf:
                        pck += output[0]
                        saved_srf.append(name)

                    # Node Output
                    srf += output[1]
                else:
                    # Get Destination
                    dst = int(stats[2])
                    name = stats[0]

                    # ==============================
                    # Node Output
                    # ==============================
                    # Transform
                    ys_matrix = mathutils.Matrix((
                        ( 1.0,  0.0,  0.0,  0.0),
                        ( 0.0,  0.0,  1.0,  0.0),
                        ( 0.0,  1.0,  0.0,  0.0),
                        ( 0.0,  0.0,  0.0,  1.0),
                    ))
                    # Axis
                    local_axis = ys_matrix.to_3x3() * obj.location
                    local_rotate = [
                        obj.rotation_euler.z * 10430.37835,
                        obj.rotation_euler.x * 10430.37835,
                        obj.rotation_euler.y * 10430.37835,
                    ]

                    # Header
                    pc2 += 'PC2\n'

                    # FIL
                    pc2 += 'FIL {}.pc2\n'.format(stats[0])

                    # POS
                    pc2 += 'POS {:.2f} 0.00 {:.2f} '.format(local_axis[0], local_axis[2])
                    pc2 += '{:.0f} {:.0f} {:.0f} 1\n'.format(*local_rotate)

                    # ID
                    pc2 += 'ID 0\n'

                    # Footer
                    pc2 += 'END\n\n'

                    # ==============================
                    # File Output
                    # ==============================

                    if not name in saved_pc2:
                        # Reset
                        obj.rotation_euler = (0.0, 0.0, 0.0)
                        # Check Object Type
                        result = 'PICT2\n'
                        if stats[1] == 'POLY':
                            result += self.exportPoly(obj, dst)
                        elif stats[1] == 'LIGHT':
                            result += self.exportLightStatic(obj, dst)
                        elif stats[1] == 'LINE':
                            result += self.exportLine(obj, dst)
                        # End
                        result += "ENDPICT\n"

                        # Write
                        pck += 'PCK "{}.pc2" {}\n{}\n'.format(name, len(result.split('\n')), result)
                        saved_pc2.append(name)

        fp.write(pck + gnd + srf+ pc2)
        fp.close()
        return {'FINISHED'}

    def exportPoly(self, obj, dst):
        # ==============================
        # Getting Data
        # ==============================
        # Convert to BMesh(For N-Sided Polygon)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        # Transform
        ys_matrix = mathutils.Matrix((
            ( 1.0,  0.0,  0.0,  0.0),
            ( 0.0,  0.0,  1.0,  0.0),
            ( 0.0,  1.0,  0.0,  0.0),
            ( 0.0,  0.0,  0.0,  1.0),
        ))
        bm.transform(ys_matrix * obj.matrix_world)
        bm.normal_update()
        # Set Axis
        local_axis = ys_matrix.to_3x3() * obj.location
        # Vertexs and Faces
        verts = bm.verts
        verts.ensure_lookup_table()
        faces = bm.faces

        output = ''

        # ==============================
        # Output
        # ==============================

        # Faces
        for face in faces:
            # Header
            output += 'PLG\n'

            # Destination
            if(dst):
                output += 'DST {:.2f}\n'.format(dst)

            # Getting Material
            if len(obj.material_slots):
                material = obj.material_slots[face.material_index].material
                # Color
                color = material.diffuse_color * 255.0
                output += 'COL {:.0f} {:.0f} {:.0f}\n'.format(*color)
            else:
                output += 'COL 128 128 128\n'

            # Vertex
            for vid in face.verts:
                vertex = verts[vid.index].co - local_axis
                output += 'VER {:.2f} {:.2f}\n'.format(vertex.x, vertex.z)

            # Footer
            output += 'SPEC FALSE\n'
            output += 'ENDO\n'

        # ==============================
        # Close
        # ==============================
        bm.free()

        return output

    def exportLightStatic(self, obj, dst):
        # ==============================
        # Getting Data
        # ==============================
        # Convert to BMesh(For N-Sided Polygon)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        # Transform
        ys_matrix = mathutils.Matrix((
            ( 1.0,  0.0,  0.0,  0.0),
            ( 0.0,  0.0,  1.0,  0.0),
            ( 0.0,  1.0,  0.0,  0.0),
            ( 0.0,  0.0,  0.0,  1.0),
        ))
        bm.transform(ys_matrix * obj.matrix_world)
        bm.normal_update()
        # Set Axis
        local_axis = ys_matrix.to_3x3() * obj.location
        # Vertexs and Faces
        verts = bm.verts
        verts.ensure_lookup_table()

        output = ''

        # ==============================
        # Output
        # ==============================

        # Header
        output += 'PST\n'

        # Destination
        if(dst):
            output += 'DST {:.2f}\n'.format(dst)
        # Getting Material
        if(len(obj.material_slots)):
            material = obj.material_slots[0].material
            # Color
            color = material.diffuse_color * 255.0
            output += 'COL {:.0f} {:.0f} {:.0f}\n'.format(*color)
        else:
            output += 'COL 128 128 128\n'

        # Faces
        for vert in verts:
            vertex = vert.co - local_axis
            output += 'VER {:.2f} {:.2f}\n'.format(vertex.x, vertex.z)

        # Footer
        output += 'ENDO\n'

        # ==============================
        # Close
        # ==============================
        bm.free()

        return output

    def exportLine(self, obj, dst):
        # ==============================
        # Getting Data
        # ==============================
        # Convert to BMesh(For N-Sided Polygon)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        # Transform
        ys_matrix = mathutils.Matrix((
            ( 1.0,  0.0,  0.0,  0.0),
            ( 0.0,  0.0,  1.0,  0.0),
            ( 0.0,  1.0,  0.0,  0.0),
            ( 0.0,  0.0,  0.0,  1.0),
        ))
        bm.transform(ys_matrix * obj.matrix_world)
        bm.normal_update()
        # Set Axis
        local_axis = ys_matrix.to_3x3() * obj.location
        # Vertexs and Faces
        verts = bm.verts
        verts.ensure_lookup_table()
        edges = bm.edges

        output = ''

        # ==============================
        # Output
        # ==============================

        # Faces
        for edge in edges:
            # Header
            output += 'QST\n'

            # Destination
            if(dst):
                output += 'DST {:.2f}\n'.format(dst)

            # Getting Material
            if len(obj.material_slots):
                material = obj.material_slots[0].material
                # Color
                color = material.diffuse_color * 255.0
                output += 'COL {:.0f} {:.0f} {:.0f}\n'.format(*color)
            else:
                output += 'COL 128 128 128\n'

            # Vertex
            for vid in face.verts:
                vertex = verts[vid.index].co - local_axis
                output += 'VER {:.2f} {:.2f}\n'.format(vertex.x, vertex.z)

            # Footer
            output += 'ENDO\n'

        # ==============================
        # Close
        # ==============================
        bm.free()

        return output

    def exportGround(self, obj, name, iff):
        # ==============================
        # Getting Data
        # ==============================
        # Convert to BMesh(For N-Sided Polygon)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        # Transform
        ys_matrix = mathutils.Matrix((
            ( 1.0,  0.0,  0.0,  0.0),
            ( 0.0,  0.0,  1.0,  0.0),
            ( 0.0,  1.0,  0.0,  0.0),
            ( 0.0,  0.0,  0.0,  1.0),
        ))
        bm.transform(ys_matrix * obj.matrix_world)
        bm.normal_update()
        # Vertexs and Faces
        verts = bm.verts
        verts.ensure_lookup_table()
        # Axis
        local_axis = ys_matrix.to_3x3() * obj.location
        local_rotate = [
            obj.rotation_euler.z * 10430.37835,
            obj.rotation_euler.x * 10430.37835,
            obj.rotation_euler.y * 10430.37835,
        ]

        output = ''

        # ==============================
        # Output
        # ==============================

        # Header
        output += 'GOB\n'

        # ID
        output += 'ID 0\n'

        # NAM
        output += 'NAM {}\n'.format(name)

        # POS
        output += 'POS {:.2f} {:.2f} {:.2f} '.format(*local_axis)
        output += '{:.0f} {:.0f} {:.0f} 1\n'.format(*local_rotate)

        # IFF/FLG
        output += 'IFF {}\nFLG 0\n'.format(iff)

        # Footer
        output += 'END\n'

        # ==============================
        # Close
        # ==============================
        bm.free()

        return output

    def exportSRF(self, obj, scene):
        # ==============================
        # Getting Data
        # ==============================
        # Axis
        ys_matrix = mathutils.Matrix((
            ( 1.0,  0.0,  0.0,  0.0),
            ( 0.0,  0.0,  1.0,  0.0),
            ( 0.0,  1.0,  0.0,  0.0),
            ( 0.0,  0.0,  0.0,  1.0),
        ))
        local_axis = ys_matrix.to_3x3() * obj.location
        local_rotate = [
            obj.rotation_euler.z * 10430.37835,
            obj.rotation_euler.x * 10430.37835,
            obj.rotation_euler.y * 10430.37835,
        ]

        # ==============================
        # Output(SURF)
        # ==============================
        # Reset Rotation
        obj.rotation_euler = (0.0, 0.0, 0.0)
        # Export
        surf_obj = Surface(obj, scene)
        pck = surf_obj.pck(False, True)

        # ==============================
        # Output(Node)
        # ==============================
        output = ''

        # Header
        output += 'SRF\n'

        # ID
        output += 'ID 0\n'

        # NAM
        output += 'FIL {}.srf\n'.format(surf_obj.name.split('.')[0])

        # POS
        output += 'POS {:.2f} {:.2f} {:.2f} '.format(*local_axis)
        output += '{:.0f} {:.0f} {:.0f} 1\n'.format(*local_rotate)

        # Footer
        output += 'END\n'

        return [pck, output]

# Menu Button(Import)
def menu_import(self, context):
    self.layout.operator(ImportSRF.bl_idname, text = 'SURF Model (.srf)', icon='PLUGIN')
    self.layout.operator(ImportDNM.bl_idname, text = 'DNM Model (.dnm)', icon='PLUGIN')

# Menu Button(Export)
def menu_export(self, context):
    self.layout.operator(ExportSRF.bl_idname, text = 'SURF Model (.srf)', icon='PLUGIN')
    self.layout.operator(ExportDNM.bl_idname, text = 'DNM Model (.dnm)', icon='PLUGIN')
    self.layout.operator(ExportPCK.bl_idname, text = 'PCK Node (.dnm)', icon='PLUGIN')
    self.layout.operator(ExplodeDNM.bl_idname, text = 'DNM Model(Parts) (.dnm)', icon='PLUGIN')
    self.layout.operator(ExplodeSRF.bl_idname, text = 'PCK Node(Parts) (.srf)', icon='PLUGIN')
    self.layout.operator(ExportFLD.bl_idname, text = 'FLD Field (.fld)', icon='PLUGIN')

# Regist
def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menu_import)
    bpy.types.INFO_MT_file_export.append(menu_export)

# Unregist
def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menu_import)
    bpy.types.INFO_MT_file_export.remove(menu_export)

if __name__ == '__main__':
    register()
