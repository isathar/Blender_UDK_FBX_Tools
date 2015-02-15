# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####



# NOTES:
#
# based on the fbx export script included in < Blender v2.68 (6.1 ASCII)
# original script created by and copyright (c) Campbell Barton
#
# Changes by isathar:
#
# - tangent + binormal calculation (*)
# - custom normals support for fbx normals editor and adsn's Recalc Vertex Normals addon
# - Normals are exported as PerPolyVertex
# - list lookup speed optimizations
# - XNA tweaks disabled for now
#
#  UE-specific:
# - for armatures: root bone is parented to the scene instead of an armature object
# - some changes made to rotation handling to accommodate for this
# - axis conversion options altered
# - tangent space close to UDK's auto-generated tangents
#
#
# (*) Tangent space calculation based on:
# Lengyel, Eric. “Computing Tangent Space Basis Vectors for an Arbitrary Mesh”. Terathon Software 3D Graphics Library, 2001. 
# http://www.terathon.com/code/tangent.html
#
# Bugs:
# - mirrored UVs are not handled correctly in either tangent export mode



import os
import time
import math

import bpy
import bmesh
from mathutils import Vector, Matrix

from bpy_extras.io_utils import axis_conversion

from . import exporter_data


# I guess FBX uses degrees instead of radians (Arystan).
# Call this function just before writing to FBX.
# 180 / math.pi == 57.295779513
def tuple_rad_to_deg(eul):
	return eul[0] * 57.295779513, eul[1] * 57.295779513, eul[2] * 57.295779513

# Used to add the scene name into the filepath without using odd chars
sane_name_mapping_ob = {}
sane_name_mapping_ob_unique = set()
sane_name_mapping_mat = {}
sane_name_mapping_tex = {}
sane_name_mapping_take = {}
sane_name_mapping_group = {}

# Make sure reserved names are not used
sane_name_mapping_ob['Scene'] = 'Scene_'
sane_name_mapping_ob_unique.add('Scene_')



def increment_string(t):
	name = t
	num = ''
	while name and name[-1].isdigit():
		num = name[-1] + num
		name = name[:-1]
	if num:
		return '%s%d' % (name, int(num) + 1)
	else:
		return name + '_0'


# todo - Disallow the name 'Scene' - it will bugger things up.
def sane_name(data, dct, unique_set=None):
	#if not data: return None

	if type(data) == tuple:  # materials are paired up with images
		data, other = data
		use_other = True
	else:
		other = None
		use_other = False

	name = data.name if data else None
	orig_name = name

	if other:
		orig_name_other = other.name
		name = '%s #%s' % (name, orig_name_other)
	else:
		orig_name_other = None

	# dont cache, only ever call once for each data type now,
	# so as to avoid namespace collision between types - like with objects <-> bones
	#try:		return dct[name]
	#except:		pass

	if not name:
		name = 'unnamed'  # blank string, ASKING FOR TROUBLE!
	else:

		name = bpy.path.clean_name(name)  # use our own

	name_unique = dct.values() if unique_set is None else unique_set

	while name in name_unique:
		name = increment_string(name)

	if use_other:  # even if other is None - orig_name_other will be a string or None
		dct[orig_name, orig_name_other] = name
	else:
		dct[orig_name] = name

	if unique_set is not None:
		unique_set.add(name)

	return name


def sane_obname(data):
	return sane_name(data, sane_name_mapping_ob, sane_name_mapping_ob_unique)


def sane_matname(data):
	return sane_name(data, sane_name_mapping_mat)


def sane_texname(data):
	return sane_name(data, sane_name_mapping_tex)


def sane_takename(data):
	return sane_name(data, sane_name_mapping_take)


def sane_groupname(data):
	return sane_name(data, sane_name_mapping_group)


def mat4x4str(mat):
	# blender matrix is row major, fbx is col major so transpose on write
	return ("%.15f,%.15f,%.15f,%.15f,"
			"%.15f,%.15f,%.15f,%.15f,"
			"%.15f,%.15f,%.15f,%.15f,"
			"%.15f,%.15f,%.15f,%.15f" %
			tuple([f for v in mat.transposed() for f in v]))


def action_bone_names(obj, action):
	from bpy.types import PoseBone

	names = set()
	path_resolve = obj.path_resolve

	for fcu in action.fcurves:
		try:
			prop = path_resolve(fcu.data_path, False)
		except:
			prop = None

		if prop is not None:
			data = prop.data
			if isinstance(data, PoseBone):
				names.add(data.name)

	return names


# ob must be OB_MESH
def BPyMesh_meshWeight2List(ob, me):
	""" Takes a mesh and return its group names and a list of lists, one list per vertex.
	aligning the each vert list with the group names, each list contains float value for the weight.
	These 2 lists can be modified and then used with list2MeshWeight to apply the changes.
	"""

	# Clear the vert group.
	groupNames = [g.name for g in ob.vertex_groups]
	len_groupNames = len(groupNames)

	if not len_groupNames:
		# no verts? return a vert aligned empty list
		return [[] for i in range(len(me.vertices))], []
	else:
		vWeightList = [[0.0] * len_groupNames for i in range(len(me.vertices))]

	for i, v in enumerate(me.vertices):
		for g in v.groups:
			# possible weights are out of range
			index = g.group
			if index < len_groupNames:
				vWeightList[i][index] = g.weight

	return groupNames, vWeightList


def meshNormalizedWeights(ob, me):
	groupNames, vWeightList = BPyMesh_meshWeight2List(ob, me)

	if not groupNames:
		return [], []

	for i, vWeights in enumerate(vWeightList):
		tot = 0.0
		for w in vWeights:
			tot += w

		if tot:
			for j, w in enumerate(vWeights):
				vWeights[j] = w / tot

	return groupNames, vWeightList

header_comment = \
'''; FBX 7.3.0 project file
; Created by Blender FBX Exporter Customized
;
; ----------------------------------------------------

'''


# This func can be called with just the filepath
def save_single(operator, scene, filepath="",
		global_matrix=None,
		context_objects=None,
		object_types={'ARMATURE', 'MESH'},
		global_scale=1.0,
		use_mesh_modifiers=False,
		mesh_smooth_type='FACE',
		normals_export_mode='AUTO',
		export_tangentspace_base='NONE',
		tangentspace_uvlnum=0,
		merge_vertexcollayers=False,
		use_armature_deform_only=False,
		use_anim=False,
		use_anim_optimize=False,
		anim_optimize_precision=6,
		use_anim_action_all=False,
		use_mesh_edges=False,
		use_default_take=False,
	):
	
	import bpy_extras.io_utils
	
	# Only used for camera and lamp rotations
	mtx_x90 = Matrix.Rotation(math.pi / 2.0, 3, 'X')
	# Used for mesh and armature rotations
	mtx4_z90 = Matrix.Rotation(math.pi / 2.0, 4, 'Z')
	# Rotation does not work for XNA animations.  I do not know why but they end up a mess! (JCB)
	
	# UE rotation matrix adjustment
	mtx4_y90 = Matrix.Rotation(math.pi / 2.0, 4, 'Y')
	
	if global_matrix is None:
		global_matrix = Matrix()
		#global_scale = 1.0
	#else:
	#	global_scale = global_matrix.median_scale
	
	# Use this for working out paths relative to the export location
	base_src = os.path.dirname(bpy.data.filepath)
	base_dst = os.path.dirname(filepath)

	# collect images to copy
	copy_set = set()
	
	last_geometryID = 4000000
	last_MeshID = 500000
	last_BoneID = 600000
	last_MaterialID = 700000

	# ----------------------------------------------
	# storage classes
	class my_bone_class(object):
		__slots__ = ("blenName",
					 "blenBone",
					 "blenMeshes",
					 "restMatrix",
					 "parent",
					 "blenName",
					 "fbxName",
					 "fbxArm",
					 "__pose_bone",
					 "__anim_poselist")

		def __init__(self, blenBone, fbxArm):

			# This is so 2 armatures dont have naming conflicts since FBX bones use object namespace
			self.fbxName = sane_obname(blenBone)

			self.blenName = blenBone.name
			self.blenBone = blenBone
			self.blenMeshes = {}  # fbxMeshObName : mesh
			self.fbxArm = fbxArm
			self.restMatrix = blenBone.matrix_local

			# not used yet
			#~ self.restMatrixInv = self.restMatrix.inverted()
			#~ self.restMatrixLocal = None # set later, need parent matrix

			self.parent = None

			# not public
			pose = fbxArm.blenObject.pose
			self.__pose_bone = pose.bones[self.blenName]

			# store a list if matrices here, (poseMatrix, head, tail)
			# {frame:posematrix, frame:posematrix, ...}
			self.__anim_poselist = {}

		'''
		def calcRestMatrixLocal(self):
			if self.parent:
				self.restMatrixLocal = self.restMatrix * self.parent.restMatrix.inverted()
			else:
				self.restMatrixLocal = self.restMatrix.copy()
		'''
		def setPoseFrame(self, f):
			# cache pose info here, frame must be set beforehand

			# Didnt end up needing head or tail, if we do - here it is.
			'''
			self.__anim_poselist[f] = (\
				self.__pose_bone.poseMatrix.copy(),\
				self.__pose_bone.head.copy(),\
				self.__pose_bone.tail.copy() )
			'''

			self.__anim_poselist[f] = self.__pose_bone.matrix.copy()

		def getPoseBone(self):
			return self.__pose_bone

		# get pose from frame.
		def getPoseMatrix(self, f):  # ----------------------------------------------
			return self.__anim_poselist[f]
		'''
		def getPoseHead(self, f):
			#return self.__pose_bone.head.copy()
			return self.__anim_poselist[f][1].copy()
		def getPoseTail(self, f):
			#return self.__pose_bone.tail.copy()
			return self.__anim_poselist[f][2].copy()
		'''
		# end

		def getAnimParRelMatrix(self, frame):
			#arm_mat = self.fbxArm.matrixWorld
			#arm_mat = self.fbxArm.parRelMatrix()

			if not self.parent:
				# UE Rotation fix
				return self.getPoseMatrix(frame) * mtx4_z90 * mtx4_y90
			else:
				#return (mtx4_z90 * ((self.getPoseMatrix(frame) * arm_mat)))  *  (mtx4_z90 * (self.parent.getPoseMatrix(frame) * arm_mat)).inverted()
				return (self.parent.getPoseMatrix(frame) * mtx4_z90).inverted() * ((self.getPoseMatrix(frame)) * mtx4_z90)

		# we need thes because cameras and lights modified rotations
		def getAnimParRelMatrixRot(self, frame):
			return self.getAnimParRelMatrix(frame)

		def flushAnimData(self):
			self.__anim_poselist.clear()

	class my_object_generic(object):
		__slots__ = ("fbxName",
					 "blenObject",
					 "blenData",
					 "origData",
					 "blenTextures",
					 "blenMaterials",
					 "blenMaterialList",
					 "blenAction",
					 "blenActionList",
					 "fbxGroupNames",
					 "fbxParent",
					 "fbxBoneParent",
					 "fbxBones",
					 "fbxArm",
					 "matrixWorld",
					 "__anim_poselist",
					 )

		# Other settings can be applied for each type - mesh, armature etc.
		def __init__(self, ob, matrixWorld=None):
			self.fbxName = sane_obname(ob)
			self.blenObject = ob
			self.fbxGroupNames = []
			self.fbxParent = None  # set later on IF the parent is in the selection.
			self.fbxArm = None
			if matrixWorld:
				self.matrixWorld = global_matrix * matrixWorld
			else:
				self.matrixWorld = global_matrix * ob.matrix_world

			self.__anim_poselist = {}  # we should only access this

		def parRelMatrix(self):
			if self.fbxParent:
				return self.fbxParent.matrixWorld.inverted() * self.matrixWorld
			else:
				return self.matrixWorld

		def setPoseFrame(self, f, fake=False):
			if fake:
				self.__anim_poselist[f] = self.matrixWorld * global_matrix.inverted()
			else:
				self.__anim_poselist[f] = self.blenObject.matrix_world.copy()

		def getAnimParRelMatrix(self, frame):
			if self.fbxParent:
				#return (self.__anim_poselist[frame] * self.fbxParent.__anim_poselist[frame].inverted() ) * global_matrix
				return (global_matrix * self.fbxParent.__anim_poselist[frame]).inverted() * (global_matrix * self.__anim_poselist[frame])
			else:
				return global_matrix * self.__anim_poselist[frame]

		def getAnimParRelMatrixRot(self, frame):
			obj_type = self.blenObject.type
			if self.fbxParent:
				matrix_rot = ((global_matrix * self.fbxParent.__anim_poselist[frame]).inverted() * (global_matrix * self.__anim_poselist[frame])).to_3x3()
			else:
				matrix_rot = (global_matrix * self.__anim_poselist[frame]).to_3x3()
			
			# Lamps need to be rotated
			if obj_type == 'LAMP':
				matrix_rot = matrix_rot * mtx_x90
			elif obj_type == 'CAMERA':
				y = matrix_rot * Vector((0.0, 1.0, 0.0))
				matrix_rot = Matrix.Rotation(math.pi / 2.0, 3, y) * matrix_rot

			return matrix_rot

	# ----------------------------------------------

	print('\nFBX export starting... %r' % filepath)
	start_time = time.clock()
	try:
		file = open(filepath, "w", encoding="utf8", newline="\n")
	except:
		import traceback
		traceback.print_exc()
		operator.report({'ERROR'}, "Couldn't open file %r" % filepath)
		return {'CANCELLED'}

	# convenience
	fw = file.write

	# scene = context.scene  # now passed as an arg instead of context
	world = scene.world

	# ---------------------------- Write the header first
	fw(header_comment)
	curtime = time.localtime()[0:6]
	
	# moved creation time + creator into header
	fw('''FBXHeaderExtension:  {
	FBXHeaderVersion: 1003
	FBXVersion: 7300
	CreationTimeStamp:  {
		Version: 1000
		Year: %.4i
		Month: %.2i
		Day: %.2i
		Hour: %.2i
		Minute: %.2i
		Second: %.2i
		Millisecond: 0
	}''' % (curtime))

	fw('\n\tCreator: "FBX Custom 7.3 - Blender %s"' % (bpy.app.version_string))
	
	# SceneInfo (moved to header in 7.3):
	fw('''
	SceneInfo: "SceneInfo::GlobalInfo", "UserData" {
		Type: "UserData"
		Version: 100
		MetaData:  {
			Version: 100
			Title: ""
			Subject: ""
			Author: ""
			Keywords: ""
			Revision: ""
			Comment: ""
		}
		Properties70:  {
			''')
	
	fw('P: "DocumentUrl", "KString", "Url", "", "%s"\n' % filepath)
	fw('\t\t\tP: "SrcDocumentUrl", "KString", "Url", "", "%s"' % filepath)
	
	fw('''
			P: "Original", "Compound", "", ""
			P: "Original|ApplicationVendor", "KString", "", "", ""
			P: "Original|ApplicationName", "KString", "", "", "Blender"
			P: "Original|ApplicationVersion", "KString", "", "", "%s"
			P: "Original|DateTime_GMT", "DateTime", "", "", ""
			P: "Original|FileName", "KString", "", "", ""
			P: "LastSaved", "Compound", "", ""
			P: "LastSaved|ApplicationVendor", "KString", "", "", ""
			P: "LastSaved|ApplicationName", "KString", "", "", "Blender"
			P: "LastSaved|ApplicationVersion", "KString", "", "", "%s"
			P: "LastSaved|DateTime_GMT", "DateTime", "", "", "%s"
		}
	}''' % (bpy.app.version_string, bpy.app.version_string, curtime))
	fw('\n}\n')
	
	# Write global settings
	fw('''GlobalSettings:  {
	Version: 1000
	Properties70:  {
		P: "UpAxis", "int", "Integer", "",1
		P: "UpAxisSign", "int", "Integer", "",1
		P: "FrontAxis", "int", "Integer", "",2
		P: "FrontAxisSign", "int", "Integer", "",1
		P: "CoordAxis", "int", "Integer", "",0
		P: "CoordAxisSign", "int", "Integer", "",1
		P: "OriginalUpAxis", "int", "Integer", "",-1
		P: "OriginalUpAxisSign", "int", "Integer", "",1
		P: "UnitScaleFactor", "double", "Number", "",1
		P: "OriginalUnitScaleFactor", "double", "Number", "",1
		P: "AmbientColor", "ColorRGB", "Color", "",0,0,0
		P: "DefaultCamera", "KString", "", "", "Producer Perspective"
		P: "TimeMode", "enum", "", "",11
		P: "TimeSpanStart", "KTime", "Time", "",0
		P: "TimeSpanStop", "KTime", "Time", "",44261734750
		P: "CustomFrameRate", "double", "Number", "",-1
	}''')
	fw('\n}\n\n')
	
	# Document description - not really part of header, but close to the start
	fw('; Documents Description\n')
	fw(';------------------------------------------------------------------\n\n')
	fw('Documents:  {\n\tCount: 1\n')
	fw('\tDocument: 10, "", "Scene" {\n')
	fw('\t\tProperties70:  {\n')
	fw('\t\t\tP: "SourceObject", "object", "", ""\n')
	fw('\t\t\tP: "ActiveAnimStackName", "KString", "", "", ""\n')
	fw('\t\t}\n\t\tRootNode: 0\n\t}\n}\n\n')
	
	fw('; Document References\n;------------------------------------------------------------------\n\nReferences:\t{\n}')
	
	pose_items = []  # list of (fbxName, matrix) to write pose data for, easier to collect along the way

	# --------------- funcs for exporting
	def object_tx(ob, loc, matrix, matrix_mod=None):
		"""
		Matrix mod is so armature objects can modify their bone matrices
		"""
		if isinstance(ob, bpy.types.Bone):
			# UE rotation fix (root bone)
			if not ob.parent:
				matrix = ob.matrix_local * mtx4_z90 * mtx4_y90
			else:
				matrix = ob.matrix_local * mtx4_z90
			
			# no rotation changes needed here since root bone's rotation is applied to rest of skeleton
			parent = ob.parent
			if parent:
				#par_matrix = mtx4_z90 * (parent.matrix['ARMATURESPACE'] * matrix_mod)
				par_matrix = parent.matrix_local * mtx4_z90  # dont apply armature matrix anymore
				matrix = par_matrix.inverted() * matrix

			loc, rot, scale = matrix.decompose()
			matrix_rot = rot.to_matrix()

			loc = tuple(loc)
			rot = tuple(rot.to_euler())  # quat -> euler
			scale = tuple(scale)

		else:
			# This is bad because we need the parent relative matrix from the fbx parent (if we have one), dont use anymore
			#if ob and not matrix: matrix = ob.matrix_world * global_matrix
			if ob and not matrix:
				raise Exception("error: this should never happen!")

			matrix_rot = matrix
			#if matrix:
			#    matrix = matrix_scale * matrix

			if matrix:
				loc, rot, scale = matrix.decompose()
				matrix_rot = rot.to_matrix()

				# Lamps need to be rotated
				if ob and ob.type == 'LAMP':
					matrix_rot = matrix_rot * mtx_x90
				elif ob and ob.type == 'CAMERA':
					y = matrix_rot * Vector((0.0, 1.0, 0.0))
					matrix_rot = Matrix.Rotation(math.pi / 2.0, 3, y) * matrix_rot
				# else do nothing.

				loc = tuple(loc)
				rot = tuple(matrix_rot.to_euler())
				scale = tuple(scale)
			else:
				if not loc:
					loc = 0.0, 0.0, 0.0
				scale = 1.0, 1.0, 1.0
				rot = 0.0, 0.0, 0.0

		return loc, rot, scale, matrix, matrix_rot
	
	
	
	def write_object_tx(ob, loc, matrix, matrix_mod=None):
		"""
		We have loc to set the location if non blender objects that have a location

		matrix_mod is only used for bones at the moment
		"""
		loc, rot, scale, matrix, matrix_rot = object_tx(ob, loc, matrix, matrix_mod)
		
		fw('\n\t\t\tProperty: "Lcl Translation", "Lcl Translation", "A+",%.15f,%.15f,%.15f' % loc)
		fw('\n\t\t\tProperty: "Lcl Rotation", "Lcl Rotation", "A+",%.15f,%.15f,%.15f' % tuple_rad_to_deg(rot))
		fw('\n\t\t\tProperty: "Lcl Scaling", "Lcl Scaling", "A+",%.15f,%.15f,%.15f' % scale)
		return loc, rot, scale, matrix, matrix_rot

	def get_constraints(ob=None):
		# Set variables to their defaults.
		constraint_values = {"loc_min": (0.0, 0.0, 0.0),
							 "loc_max": (0.0, 0.0, 0.0),
							 "loc_limit": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
							 "rot_min": (0.0, 0.0, 0.0),
							 "rot_max": (0.0, 0.0, 0.0),
							 "rot_limit": (0.0, 0.0, 0.0),
							 "sca_min": (1.0, 1.0, 1.0),
							 "sca_max": (1.0, 1.0, 1.0),
							 "sca_limit": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
							}

		# Iterate through the list of constraints for this object to get the information in a format which is compatible with the FBX format.
		if ob is not None:
			for constraint in ob.constraints:
				if constraint.type == 'LIMIT_LOCATION':
					constraint_values["loc_min"] = constraint.min_x, constraint.min_y, constraint.min_z
					constraint_values["loc_max"] = constraint.max_x, constraint.max_y, constraint.max_z
					constraint_values["loc_limit"] = constraint.use_min_x, constraint.use_min_y, constraint.use_min_z, constraint.use_max_x, constraint.use_max_y, constraint.use_max_z
				elif constraint.type == 'LIMIT_ROTATION':
					constraint_values["rot_min"] = math.degrees(constraint.min_x), math.degrees(constraint.min_y), math.degrees(constraint.min_z)
					constraint_values["rot_max"] = math.degrees(constraint.max_x), math.degrees(constraint.max_y), math.degrees(constraint.max_z)
					constraint_values["rot_limit"] = constraint.use_limit_x, constraint.use_limit_y, constraint.use_limit_z
				elif constraint.type == 'LIMIT_SCALE':
					constraint_values["sca_min"] = constraint.min_x, constraint.min_y, constraint.min_z
					constraint_values["sca_max"] = constraint.max_x, constraint.max_y, constraint.max_z
					constraint_values["sca_limit"] = constraint.use_min_x, constraint.use_min_y, constraint.use_min_z, constraint.use_max_x, constraint.use_max_y, constraint.use_max_z

		# in case bad values are assigned.
		assert(len(constraint_values) == 9)

		return constraint_values

	def write_object_props(ob=None, loc=None, matrix=None, matrix_mod=None, pose_bone=None):
		# Check if a pose exists for this object and set the constraint soruce accordingly. (Poses only exsit if the object is a bone.)
		if pose_bone:
			constraints = get_constraints(pose_bone)
		else:
			constraints = get_constraints(ob)
		
		# if the type is 0 its an empty otherwise its a mesh
		# only difference at the moment is one has a color
		fw('''
		Properties60:  {
			Property: "QuaternionInterpolate", "bool", "",0
			Property: "Visibility", "Visibility", "A+",1''')

		loc, rot, scale, matrix, matrix_rot = write_object_tx(ob, loc, matrix, matrix_mod)

		# Rotation order, note, for FBX files Iv loaded normal order is 1
		# setting to zero.
		# eEULER_XYZ = 0
		# eEULER_XZY
		# eEULER_YZX
		# eEULER_YXZ
		# eEULER_ZXY
		# eEULER_ZYX

		fw('\n\t\t\tProperty: "RotationOffset", "Vector3D", "",0,0,0'
		   '\n\t\t\tProperty: "RotationPivot", "Vector3D", "",0,0,0'
		   '\n\t\t\tProperty: "ScalingOffset", "Vector3D", "",0,0,0'
		   '\n\t\t\tProperty: "ScalingPivot", "Vector3D", "",0,0,0'
		   '\n\t\t\tProperty: "TranslationActive", "bool", "",0'
		   )

		fw('\n\t\t\tProperty: "TranslationMin", "Vector3D", "",%.15g,%.15g,%.15g' % constraints["loc_min"])
		fw('\n\t\t\tProperty: "TranslationMax", "Vector3D", "",%.15g,%.15g,%.15g' % constraints["loc_max"])
		fw('\n\t\t\tProperty: "TranslationMinX", "bool", "",%d' % constraints["loc_limit"][0])
		fw('\n\t\t\tProperty: "TranslationMinY", "bool", "",%d' % constraints["loc_limit"][1])
		fw('\n\t\t\tProperty: "TranslationMinZ", "bool", "",%d' % constraints["loc_limit"][2])
		fw('\n\t\t\tProperty: "TranslationMaxX", "bool", "",%d' % constraints["loc_limit"][3])
		fw('\n\t\t\tProperty: "TranslationMaxY", "bool", "",%d' % constraints["loc_limit"][4])
		fw('\n\t\t\tProperty: "TranslationMaxZ", "bool", "",%d' % constraints["loc_limit"][5])

		fw('\n\t\t\tProperty: "RotationOrder", "enum", "",0'
		   '\n\t\t\tProperty: "RotationSpaceForLimitOnly", "bool", "",0'
		   '\n\t\t\tProperty: "AxisLen", "double", "",10'
		   '\n\t\t\tProperty: "PreRotation", "Vector3D", "",0,0,0'
		   '\n\t\t\tProperty: "PostRotation", "Vector3D", "",0,0,0'
		   '\n\t\t\tProperty: "RotationActive", "bool", "",0'
		   )

		fw('\n\t\t\tProperty: "RotationMin", "Vector3D", "",%.15g,%.15g,%.15g' % constraints["rot_min"])
		fw('\n\t\t\tProperty: "RotationMax", "Vector3D", "",%.15g,%.15g,%.15g' % constraints["rot_max"])
		fw('\n\t\t\tProperty: "RotationMinX", "bool", "",%d' % constraints["rot_limit"][0])
		fw('\n\t\t\tProperty: "RotationMinY", "bool", "",%d' % constraints["rot_limit"][1])
		fw('\n\t\t\tProperty: "RotationMinZ", "bool", "",%d' % constraints["rot_limit"][2])
		fw('\n\t\t\tProperty: "RotationMaxX", "bool", "",%d' % constraints["rot_limit"][0])
		fw('\n\t\t\tProperty: "RotationMaxY", "bool", "",%d' % constraints["rot_limit"][1])
		fw('\n\t\t\tProperty: "RotationMaxZ", "bool", "",%d' % constraints["rot_limit"][2])

		fw('\n\t\t\tProperty: "RotationStiffnessX", "double", "",0'
		   '\n\t\t\tProperty: "RotationStiffnessY", "double", "",0'
		   '\n\t\t\tProperty: "RotationStiffnessZ", "double", "",0'
		   '\n\t\t\tProperty: "MinDampRangeX", "double", "",0'
		   '\n\t\t\tProperty: "MinDampRangeY", "double", "",0'
		   '\n\t\t\tProperty: "MinDampRangeZ", "double", "",0'
		   '\n\t\t\tProperty: "MaxDampRangeX", "double", "",0'
		   '\n\t\t\tProperty: "MaxDampRangeY", "double", "",0'
		   '\n\t\t\tProperty: "MaxDampRangeZ", "double", "",0'
		   '\n\t\t\tProperty: "MinDampStrengthX", "double", "",0'
		   '\n\t\t\tProperty: "MinDampStrengthY", "double", "",0'
		   '\n\t\t\tProperty: "MinDampStrengthZ", "double", "",0'
		   '\n\t\t\tProperty: "MaxDampStrengthX", "double", "",0'
		   '\n\t\t\tProperty: "MaxDampStrengthY", "double", "",0'
		   '\n\t\t\tProperty: "MaxDampStrengthZ", "double", "",0'
		   '\n\t\t\tProperty: "PreferedAngleX", "double", "",0'
		   '\n\t\t\tProperty: "PreferedAngleY", "double", "",0'
		   '\n\t\t\tProperty: "PreferedAngleZ", "double", "",0'
		   '\n\t\t\tProperty: "InheritType", "enum", "",0'
		   '\n\t\t\tProperty: "ScalingActive", "bool", "",0'
		   )

		fw('\n\t\t\tProperty: "ScalingMin", "Vector3D", "",%.15g,%.15g,%.15g' % constraints["sca_min"])
		fw('\n\t\t\tProperty: "ScalingMax", "Vector3D", "",%.15g,%.15g,%.15g' % constraints["sca_max"])
		fw('\n\t\t\tProperty: "ScalingMinX", "bool", "",%d' % constraints["sca_limit"][0])
		fw('\n\t\t\tProperty: "ScalingMinY", "bool", "",%d' % constraints["sca_limit"][1])
		fw('\n\t\t\tProperty: "ScalingMinZ", "bool", "",%d' % constraints["sca_limit"][2])
		fw('\n\t\t\tProperty: "ScalingMaxX", "bool", "",%d' % constraints["sca_limit"][3])
		fw('\n\t\t\tProperty: "ScalingMaxY", "bool", "",%d' % constraints["sca_limit"][4])
		fw('\n\t\t\tProperty: "ScalingMaxZ", "bool", "",%d' % constraints["sca_limit"][5])

		fw('\n\t\t\tProperty: "GeometricTranslation", "Vector3D", "",0,0,0'
		   '\n\t\t\tProperty: "GeometricRotation", "Vector3D", "",0,0,0'
		   '\n\t\t\tProperty: "GeometricScaling", "Vector3D", "",1,1,1'
		   '\n\t\t\tProperty: "LookAtProperty", "object", ""'
		   '\n\t\t\tProperty: "UpVectorProperty", "object", ""'
		   '\n\t\t\tProperty: "Show", "bool", "",1'
		   '\n\t\t\tProperty: "NegativePercentShapeSupport", "bool", "",1'
		   '\n\t\t\tProperty: "DefaultAttributeIndex", "int", "",0'
		   )

		if ob and not isinstance(ob, bpy.types.Bone):
			# Only mesh objects have color
			fw('\n\t\t\tProperty: "Color", "Color", "A",0.8,0.8,0.8'
			   '\n\t\t\tProperty: "Size", "double", "",100'
			   '\n\t\t\tProperty: "Look", "enum", "",1'
			   )

		return loc, rot, scale, matrix, matrix_rot
	
	
	#################################
	# Cameras
	def write_camera_switch():
		fw('''
	Model: "Model::Camera Switcher", "CameraSwitcher" {
		Version: 232''')

		write_object_props()
		fw('''
			Property: "Color", "Color", "A",0.8,0.8,0.8
			Property: "Camera Index", "Integer", "A+",100
		}
		MultiLayer: 0
		MultiTake: 1
		Hidden: "True"
		Shading: W
		Culling: "CullingOff"
		Version: 101
		Name: "Model::Camera Switcher"
		CameraId: 0
		CameraName: 100
		CameraIndexName:
	}''')
	
	
	def write_camera_dummy(name, loc, near, far, proj_type, up):
		fw('\n\tModel: "Model::%s", "Camera" {' % name)
		fw('\n\t\tVersion: 232')
		write_object_props(None, loc)

		fw('\n\t\t\tProperty: "Color", "Color", "A",0.8,0.8,0.8'
		   '\n\t\t\tProperty: "Roll", "Roll", "A+",0'
		   '\n\t\t\tProperty: "FieldOfView", "FieldOfView", "A+",40'
		   '\n\t\t\tProperty: "FieldOfViewX", "FieldOfView", "A+",1'
		   '\n\t\t\tProperty: "FieldOfViewY", "FieldOfView", "A+",1'
		   '\n\t\t\tProperty: "OpticalCenterX", "Real", "A+",0'
		   '\n\t\t\tProperty: "OpticalCenterY", "Real", "A+",0'
		   '\n\t\t\tProperty: "BackgroundColor", "Color", "A+",0.63,0.63,0.63'
		   '\n\t\t\tProperty: "TurnTable", "Real", "A+",0'
		   '\n\t\t\tProperty: "DisplayTurnTableIcon", "bool", "",1'
		   '\n\t\t\tProperty: "Motion Blur Intensity", "Real", "A+",1'
		   '\n\t\t\tProperty: "UseMotionBlur", "bool", "",0'
		   '\n\t\t\tProperty: "UseRealTimeMotionBlur", "bool", "",1'
		   '\n\t\t\tProperty: "ResolutionMode", "enum", "",0'
		   '\n\t\t\tProperty: "ApertureMode", "enum", "",2'
		   '\n\t\t\tProperty: "GateFit", "enum", "",0'
		   '\n\t\t\tProperty: "FocalLength", "Real", "A+",21.3544940948486'
		   '\n\t\t\tProperty: "CameraFormat", "enum", "",0'
		   '\n\t\t\tProperty: "AspectW", "double", "",320'
		   '\n\t\t\tProperty: "AspectH", "double", "",200'
		   '\n\t\t\tProperty: "PixelAspectRatio", "double", "",1'
		   '\n\t\t\tProperty: "UseFrameColor", "bool", "",0'
		   '\n\t\t\tProperty: "FrameColor", "ColorRGB", "",0.3,0.3,0.3'
		   '\n\t\t\tProperty: "ShowName", "bool", "",1'
		   '\n\t\t\tProperty: "ShowGrid", "bool", "",1'
		   '\n\t\t\tProperty: "ShowOpticalCenter", "bool", "",0'
		   '\n\t\t\tProperty: "ShowAzimut", "bool", "",1'
		   '\n\t\t\tProperty: "ShowTimeCode", "bool", "",0'
		   )

		fw('\n\t\t\tProperty: "NearPlane", "double", "",%.6f' % near)
		fw('\n\t\t\tProperty: "FarPlane", "double", "",%.6f' % far)

		fw('\n\t\t\tProperty: "FilmWidth", "double", "",0.816'
		   '\n\t\t\tProperty: "FilmHeight", "double", "",0.612'
		   '\n\t\t\tProperty: "FilmAspectRatio", "double", "",1.33333333333333'
		   '\n\t\t\tProperty: "FilmSqueezeRatio", "double", "",1'
		   '\n\t\t\tProperty: "FilmFormatIndex", "enum", "",4'
		   '\n\t\t\tProperty: "ViewFrustum", "bool", "",1'
		   '\n\t\t\tProperty: "ViewFrustumNearFarPlane", "bool", "",0'
		   '\n\t\t\tProperty: "ViewFrustumBackPlaneMode", "enum", "",2'
		   '\n\t\t\tProperty: "BackPlaneDistance", "double", "",100'
		   '\n\t\t\tProperty: "BackPlaneDistanceMode", "enum", "",0'
		   '\n\t\t\tProperty: "ViewCameraToLookAt", "bool", "",1'
		   '\n\t\t\tProperty: "LockMode", "bool", "",0'
		   '\n\t\t\tProperty: "LockInterestNavigation", "bool", "",0'
		   '\n\t\t\tProperty: "FitImage", "bool", "",0'
		   '\n\t\t\tProperty: "Crop", "bool", "",0'
		   '\n\t\t\tProperty: "Center", "bool", "",1'
		   '\n\t\t\tProperty: "KeepRatio", "bool", "",1'
		   '\n\t\t\tProperty: "BackgroundMode", "enum", "",0'
		   '\n\t\t\tProperty: "BackgroundAlphaTreshold", "double", "",0.5'
		   '\n\t\t\tProperty: "ForegroundTransparent", "bool", "",1'
		   '\n\t\t\tProperty: "DisplaySafeArea", "bool", "",0'
		   '\n\t\t\tProperty: "SafeAreaDisplayStyle", "enum", "",1'
		   '\n\t\t\tProperty: "SafeAreaAspectRatio", "double", "",1.33333333333333'
		   '\n\t\t\tProperty: "Use2DMagnifierZoom", "bool", "",0'
		   '\n\t\t\tProperty: "2D Magnifier Zoom", "Real", "A+",100'
		   '\n\t\t\tProperty: "2D Magnifier X", "Real", "A+",50'
		   '\n\t\t\tProperty: "2D Magnifier Y", "Real", "A+",50'
		   )

		fw('\n\t\t\tProperty: "CameraProjectionType", "enum", "",%i' % proj_type)

		fw('\n\t\t\tProperty: "UseRealTimeDOFAndAA", "bool", "",0'
		   '\n\t\t\tProperty: "UseDepthOfField", "bool", "",0'
		   '\n\t\t\tProperty: "FocusSource", "enum", "",0'
		   '\n\t\t\tProperty: "FocusAngle", "double", "",3.5'
		   '\n\t\t\tProperty: "FocusDistance", "double", "",200'
		   '\n\t\t\tProperty: "UseAntialiasing", "bool", "",0'
		   '\n\t\t\tProperty: "AntialiasingIntensity", "double", "",0.77777'
		   '\n\t\t\tProperty: "UseAccumulationBuffer", "bool", "",0'
		   '\n\t\t\tProperty: "FrameSamplingCount", "int", "",7'
		   '\n\t\t}'
		   '\n\t\tMultiLayer: 0'
		   '\n\t\tMultiTake: 0'
		   '\n\t\tHidden: "True"'
		   '\n\t\tShading: Y'
		   '\n\t\tCulling: "CullingOff"'
		   '\n\t\tTypeFlags: "Camera"'
		   '\n\t\tGeometryVersion: 124'
		   )

		fw('\n\t\tPosition: %.6f,%.6f,%.6f' % loc)
		fw('\n\t\tUp: %i,%i,%i' % up)

		fw('\n\t\tLookAt: 0,0,0'
		   '\n\t\tShowInfoOnMoving: 1'
		   '\n\t\tShowAudio: 0'
		   '\n\t\tAudioColor: 0,1,0'
		   '\n\t\tCameraOrthoZoom: 1'
		   '\n\t}'
		   )
	
	def write_camera_default():
		# This sucks but to match FBX converter its easier to
		# write the cameras though they are not needed.
		write_camera_dummy('Producer Perspective', (0, 71.3, 287.5), 10, 4000, 0, (0, 1, 0))
		write_camera_dummy('Producer Top', (0, 4000, 0), 1, 30000, 1, (0, 0, -1))
		write_camera_dummy('Producer Bottom', (0, -4000, 0), 1, 30000, 1, (0, 0, -1))
		write_camera_dummy('Producer Front', (0, 0, 4000), 1, 30000, 1, (0, 1, 0))
		write_camera_dummy('Producer Back', (0, 0, -4000), 1, 30000, 1, (0, 1, 0))
		write_camera_dummy('Producer Right', (4000, 0, 0), 1, 30000, 1, (0, 1, 0))
		write_camera_dummy('Producer Left', (-4000, 0, 0), 1, 30000, 1, (0, 1, 0))
	
	def write_camera(my_cam):
		"""
		Write a blender camera
		"""
		render = scene.render
		width = render.resolution_x
		height = render.resolution_y
		aspect = width / height

		data = my_cam.blenObject.data
		# film width & height from mm to inches
		filmwidth = data.sensor_width * 0.0393700787
		filmheight = data.sensor_height * 0.0393700787
		filmaspect = filmwidth / filmheight
		# film offset
		offsetx = filmwidth * data.shift_x
		offsety = filmaspect * filmheight * data.shift_y

		fw('\n\tModel: "Model::%s", "Camera" {' % my_cam.fbxName)
		fw('\n\t\tVersion: 232')
		loc, rot, scale, matrix, matrix_rot = write_object_props(my_cam.blenObject, None, my_cam.parRelMatrix())

		fw('\n\t\t\tProperty: "Roll", "Roll", "A+",0')
		fw('\n\t\t\tProperty: "FieldOfView", "FieldOfView", "A+",%.6f' % math.degrees(data.angle_y))

		fw('\n\t\t\tProperty: "FieldOfViewX", "FieldOfView", "A+",1'
		   '\n\t\t\tProperty: "FieldOfViewY", "FieldOfView", "A+",1'
		   )

		fw('\n\t\t\tProperty: "FocalLength", "Number", "A+",%.6f' % data.lens)
		fw('\n\t\t\tProperty: "FilmOffsetX", "Number", "A+",%.6f' % offsetx)
		fw('\n\t\t\tProperty: "FilmOffsetY", "Number", "A+",%.6f' % offsety)

		fw('\n\t\t\tProperty: "BackgroundColor", "Color", "A+",0,0,0'
		   '\n\t\t\tProperty: "TurnTable", "Real", "A+",0'
		   '\n\t\t\tProperty: "DisplayTurnTableIcon", "bool", "",1'
		   '\n\t\t\tProperty: "Motion Blur Intensity", "Real", "A+",1'
		   '\n\t\t\tProperty: "UseMotionBlur", "bool", "",0'
		   '\n\t\t\tProperty: "UseRealTimeMotionBlur", "bool", "",1'
		   '\n\t\t\tProperty: "ResolutionMode", "enum", "",0'
		   '\n\t\t\tProperty: "ApertureMode", "enum", "",3'  # horizontal - Houdini compatible
		   '\n\t\t\tProperty: "GateFit", "enum", "",2'
		   '\n\t\t\tProperty: "CameraFormat", "enum", "",0'
		   )

		fw('\n\t\t\tProperty: "AspectW", "double", "",%i' % width)
		fw('\n\t\t\tProperty: "AspectH", "double", "",%i' % height)

		"""Camera aspect ratio modes.
			0 If the ratio mode is eWINDOW_SIZE, both width and height values aren't relevant.
			1 If the ratio mode is eFIXED_RATIO, the height value is set to 1.0 and the width value is relative to the height value.
			2 If the ratio mode is eFIXED_RESOLUTION, both width and height values are in pixels.
			3 If the ratio mode is eFIXED_WIDTH, the width value is in pixels and the height value is relative to the width value.
			4 If the ratio mode is eFIXED_HEIGHT, the height value is in pixels and the width value is relative to the height value.

		Definition at line 234 of file kfbxcamera.h. """

		fw('\n\t\t\tProperty: "PixelAspectRatio", "double", "",1'
		   '\n\t\t\tProperty: "UseFrameColor", "bool", "",0'
		   '\n\t\t\tProperty: "FrameColor", "ColorRGB", "",0.3,0.3,0.3'
		   '\n\t\t\tProperty: "ShowName", "bool", "",1'
		   '\n\t\t\tProperty: "ShowGrid", "bool", "",1'
		   '\n\t\t\tProperty: "ShowOpticalCenter", "bool", "",0'
		   '\n\t\t\tProperty: "ShowAzimut", "bool", "",1'
		   '\n\t\t\tProperty: "ShowTimeCode", "bool", "",0'
		   )

		fw('\n\t\t\tProperty: "NearPlane", "double", "",%.6f' % (data.clip_start * global_scale))
		fw('\n\t\t\tProperty: "FarPlane", "double", "",%.6f' % (data.clip_end * global_scale))

		fw('\n\t\t\tProperty: "FilmWidth", "double", "",%.6f' % filmwidth)
		fw('\n\t\t\tProperty: "FilmHeight", "double", "",%.6f' % filmheight)
		fw('\n\t\t\tProperty: "FilmAspectRatio", "double", "",%.6f' % filmaspect)

		fw('\n\t\t\tProperty: "FilmSqueezeRatio", "double", "",1'
		   '\n\t\t\tProperty: "FilmFormatIndex", "enum", "",0'
		   '\n\t\t\tProperty: "ViewFrustum", "bool", "",1'
		   '\n\t\t\tProperty: "ViewFrustumNearFarPlane", "bool", "",0'
		   '\n\t\t\tProperty: "ViewFrustumBackPlaneMode", "enum", "",2'
		   '\n\t\t\tProperty: "BackPlaneDistance", "double", "",100'
		   '\n\t\t\tProperty: "BackPlaneDistanceMode", "enum", "",0'
		   '\n\t\t\tProperty: "ViewCameraToLookAt", "bool", "",1'
		   '\n\t\t\tProperty: "LockMode", "bool", "",0'
		   '\n\t\t\tProperty: "LockInterestNavigation", "bool", "",0'
		   '\n\t\t\tProperty: "FitImage", "bool", "",0'
		   '\n\t\t\tProperty: "Crop", "bool", "",0'
		   '\n\t\t\tProperty: "Center", "bool", "",1'
		   '\n\t\t\tProperty: "KeepRatio", "bool", "",1'
		   '\n\t\t\tProperty: "BackgroundMode", "enum", "",0'
		   '\n\t\t\tProperty: "BackgroundAlphaTreshold", "double", "",0.5'
		   '\n\t\t\tProperty: "ForegroundTransparent", "bool", "",1'
		   '\n\t\t\tProperty: "DisplaySafeArea", "bool", "",0'
		   '\n\t\t\tProperty: "SafeAreaDisplayStyle", "enum", "",1'
		   )

		fw('\n\t\t\tProperty: "SafeAreaAspectRatio", "double", "",%.6f' % aspect)
		
		fw('\n\t\t\tProperty: "Use2DMagnifierZoom", "bool", "",0'
		   '\n\t\t\tProperty: "2D Magnifier Zoom", "Real", "A+",100'
		   '\n\t\t\tProperty: "2D Magnifier X", "Real", "A+",50'
		   '\n\t\t\tProperty: "2D Magnifier Y", "Real", "A+",50'
		   '\n\t\t\tProperty: "CameraProjectionType", "enum", "",0'
		   '\n\t\t\tProperty: "UseRealTimeDOFAndAA", "bool", "",0'
		   '\n\t\t\tProperty: "UseDepthOfField", "bool", "",0'
		   '\n\t\t\tProperty: "FocusSource", "enum", "",0'
		   '\n\t\t\tProperty: "FocusAngle", "double", "",3.5'
		   '\n\t\t\tProperty: "FocusDistance", "double", "",200'
		   '\n\t\t\tProperty: "UseAntialiasing", "bool", "",0'
		   '\n\t\t\tProperty: "AntialiasingIntensity", "double", "",0.77777'
		   '\n\t\t\tProperty: "UseAccumulationBuffer", "bool", "",0'
		   '\n\t\t\tProperty: "FrameSamplingCount", "int", "",7'
		   )

		fw('\n\t\t}')
		
		fw('\n\t\tMultiLayer: 0'
		   '\n\t\tMultiTake: 0'
		   '\n\t\tShading: Y'
		   '\n\t\tCulling: "CullingOff"'
		   '\n\t\tTypeFlags: "Camera"'
		   '\n\t\tGeometryVersion: 124'
		   )
		
		fw('\n\t\tPosition: %.6f,%.6f,%.6f' % loc)
		fw('\n\t\tUp: %.6f,%.6f,%.6f' % (matrix_rot * Vector((0.0, 1.0, 0.0)))[:])
		fw('\n\t\tLookAt: %.6f,%.6f,%.6f' % (matrix_rot * Vector((0.0, 0.0, -1.0)))[:])
		
		#fw('\n\t\tUp: 0,0,0' )
		#fw('\n\t\tLookAt: 0,0,0' )
		
		fw('\n\t\tShowInfoOnMoving: 1')
		fw('\n\t\tShowAudio: 0')
		fw('\n\t\tAudioColor: 0,1,0')
		fw('\n\t\tCameraOrthoZoom: 1')
		fw('\n\t}')
	
	# lights
	def write_light(my_light):
		light = my_light.blenObject.data
		fw('\n\tModel: "Model::%s", "Light" {' % my_light.fbxName)
		fw('\n\t\tVersion: 232')
		
		write_object_props(my_light.blenObject, None, my_light.parRelMatrix())
		
		# Why are these values here twice?????? - oh well, follow the holy sdk's output
		
		# Blender light types match FBX's, funny coincidence, we just need to
		# be sure that all unsupported types are made into a point light
		#ePOINT,
		#eDIRECTIONAL
		#eSPOT
		light_type_items = {'POINT': 0, 'SUN': 1, 'SPOT': 2, 'HEMI': 3, 'AREA': 4}
		light_type = light_type_items[light.type]
		
		if light_type > 2:
			light_type = 1  # hemi and area lights become directional
		
		if light.type == 'HEMI':
			do_light = not (light.use_diffuse or light.use_specular)
			do_shadow = False
		else:
			do_light = not (light.use_only_shadow or (not light.use_diffuse and not light.use_specular))
			do_shadow = (light.shadow_method in {'RAY_SHADOW', 'BUFFER_SHADOW'})
		
		# scale = abs(global_matrix.to_scale()[0])  # scale is always uniform in this case  #  UNUSED
		
		fw('\n\t\t\tProperty: "LightType", "enum", "",%i' % light_type)
		fw('\n\t\t\tProperty: "CastLightOnObject", "bool", "",1')
		fw('\n\t\t\tProperty: "DrawVolumetricLight", "bool", "",1')
		fw('\n\t\t\tProperty: "DrawGroundProjection", "bool", "",1')
		fw('\n\t\t\tProperty: "DrawFrontFacingVolumetricLight", "bool", "",0')
		fw('\n\t\t\tProperty: "GoboProperty", "object", ""')
		fw('\n\t\t\tProperty: "Color", "Color", "A+",1,1,1')
		fw('\n\t\t\tProperty: "Intensity", "Intensity", "A+",%.2f' % (min(light.energy * 100.0, 200.0)))  # clamp below 200
		if light.type == 'SPOT':
			fw('\n\t\t\tProperty: "Cone angle", "Cone angle", "A+",%.2f' % math.degrees(light.spot_size))
		fw('\n\t\t\tProperty: "Fog", "Fog", "A+",50')
		fw('\n\t\t\tProperty: "Color", "Color", "A",%.2f,%.2f,%.2f' % tuple(light.color))
		
		fw('\n\t\t\tProperty: "Intensity", "Intensity", "A+",%.2f' % (min(light.energy * 100.0, 200.0)))  # clamp below 200
		
		fw('\n\t\t\tProperty: "Fog", "Fog", "A+",50')
		fw('\n\t\t\tProperty: "LightType", "enum", "",%i' % light_type)
		fw('\n\t\t\tProperty: "CastLightOnObject", "bool", "",%i' % do_light)
		fw('\n\t\t\tProperty: "DrawGroundProjection", "bool", "",1')
		fw('\n\t\t\tProperty: "DrawFrontFacingVolumetricLight", "bool", "",0')
		fw('\n\t\t\tProperty: "DrawVolumetricLight", "bool", "",1')
		fw('\n\t\t\tProperty: "GoboProperty", "object", ""')
		fw('\n\t\t\tProperty: "DecayType", "enum", "",0')
		fw('\n\t\t\tProperty: "DecayStart", "double", "",%.2f' % light.distance)
		
		fw('\n\t\t\tProperty: "EnableNearAttenuation", "bool", "",0'
		   '\n\t\t\tProperty: "NearAttenuationStart", "double", "",0'
		   '\n\t\t\tProperty: "NearAttenuationEnd", "double", "",0'
		   '\n\t\t\tProperty: "EnableFarAttenuation", "bool", "",0'
		   '\n\t\t\tProperty: "FarAttenuationStart", "double", "",0'
		   '\n\t\t\tProperty: "FarAttenuationEnd", "double", "",0'
		   )
		
		fw('\n\t\t\tProperty: "CastShadows", "bool", "",%i' % do_shadow)
		fw('\n\t\t\tProperty: "ShadowColor", "ColorRGBA", "",0,0,0,1')
		fw('\n\t\t}')
		
		fw('\n\t\tMultiLayer: 0'
		   '\n\t\tMultiTake: 0'
		   '\n\t\tShading: Y'
		   '\n\t\tCulling: "CullingOff"'
		   '\n\t\tTypeFlags: "Light"'
		   '\n\t\tGeometryVersion: 124'
		   '\n\t}'
		   )
	
	# null objects
	def write_null(my_null=None, fbxName=None, fbxType="Null", fbxTypeFlags="Null"):
		# ob can be null
		if not fbxName:
			fbxName = my_null.fbxName

		fw('\n\tModel: "Model::%s", "%s" {' % (fbxName, fbxType))
		fw('\n\t\tVersion: 232')

		if my_null:
			poseMatrix = write_object_props(my_null.blenObject, None, my_null.parRelMatrix())[3]
		else:
			poseMatrix = write_object_props()[3]

		pose_items.append((fbxName, poseMatrix, my_null.name))

		fw('\n\t\t}'
		   '\n\t\tMultiLayer: 0'
		   '\n\t\tMultiTake: 1'
		   '\n\t\tShading: Y'
		   '\n\t\tCulling: "CullingOff"'
		   )

		fw('\n\t\tTypeFlags: "%s"' % fbxTypeFlags)
		fw('\n\t}')
	
	
	# Bones:
	
	# NodeAttributes: size, limblength for now
	def write_bone_node(my_bone, bindex):
		bindex = exporter_data.get_fbx_BoneAttributeID(my_bone.fbxName)
		templlength = (my_bone.blenBone.head_local - my_bone.blenBone.tail_local).length
		fw('\n\tNodeAttribute: %i, ' % bindex)
		if my_bone.blenBone.parent:
			fw('"NodeAttribute::%s", "LimbNode" {' % my_bone.fbxName)
		else:
			fw('"NodeAttribute::%s", "Root" {' % my_bone.fbxName)
		fw('''
		Properties70:  {
			P: "Size", "double", "Number", "",1
			P: "LimbLength", "double", "Number", "H",%f
		}
		TypeFlags: "Skeleton"
	}''' % templlength)
	
	
	# Limb: offset, scale, rotation
	def write_bone_props(my_bone, bindex):
		bindex = exporter_data.get_fbx_BoneID(my_bone.fbxName)
		
		if my_bone.parent:
			global_matrix_bone = my_bone.restMatrix
		else:
			global_matrix_bone = (my_bone.restMatrix * my_bone.fbxArm.matrixWorld) * mtx4_z90
		#pose_items.append((my_bone.fbxName, global_matrix_bone, my_bone.fbxName))
		
		#pose_items.append((my_bone.fbxName, my_bone.fbxArm.matrixWorld, my_bone.fbxName))
		loc, rot, scale, matrix, matrix_rot = object_tx(my_bone.blenBone, None,global_matrix_bone)
		#loc, rot, scale, matrix, matrix_rot = object_tx(my_bone.blenBone, None,my_bone.fbxArm.matrixWorld)
		pose_items.append((my_bone.fbxName, matrix, my_bone.fbxName))
		
		lclrot = tuple_rad_to_deg(rot)
		
		fw('\n\tModel: %i, "Model::' % bindex)
		if my_bone.blenBone.parent:
			fw('%s", "LimbNode" {' % my_bone.fbxName)
		else:
			fw('%s", "Root" {' % my_bone.fbxName)
		fw('''
		Version: 232
		Properties70:  {
			P: "ScalingMin", "Vector3D", "Vector", "",1,1,1
			P: "DefaultAttributeIndex", "int", "Integer", "",0''')
		fw('\n\t\t\tP: "Lcl Translation", "Lcl Translation", "", "A",%.15f,%.15f,%.15f' % loc)
		fw('\n\t\t\tP: "Lcl Scaling", "Lcl Scaling", "", "A+",1,1,1')
		fw('\n\t\t\tP: "Lcl Rotation", "Lcl Rotation", "", "A+",%.15f,%.15f,%.15f' % lclrot)
		fw('\n\t\t}\n\t\tShading: Y')
		fw('\n\t\tCulling: "CullingOff"')
		fw('\n\t}')
		
	
	# added for 7.3 support
	def write_modelattributes(my_mesh):
		loc, rot, scale, matrix, matrix_rot = object_tx(my_mesh.blenObject, None, my_mesh.blenObject.matrix_world * global_matrix)
		#newmatrix = my_mesh.blenObject.matrix_world * global_matrix
		#loc, rot, scale = my_mesh.blenObject.matrix_world * global_matrix
		lclrot = tuple_rad_to_deg(rot)
		
		fw('\n\tModel: %i, "Model::' % exporter_data.get_fbx_MeshID(my_mesh.blenObject.name))
		fw('%s", "Mesh" {' % my_mesh.fbxName)
		fw('''
		Version: 232
		Properties70:  {
			P: "ScalingMin", "Vector3D", "Vector", "",1,1,1
			P: "DefaultAttributeIndex", "int", "Integer", "",0''')
		fw('\n\t\t\tP: "Lcl Translation", "Lcl Translation", "", "A",%.15f,%.15f,%.15f' % loc)
		fw('\n\t\t\tP: "Lcl Scaling", "Lcl Scaling", "", "A+",%.15f,%.15f,%.15f' % scale)
		fw('\n\t\t\tP: "Lcl Rotation", "Lcl Rotation", "", "A+",%.15f,%.15f,%.15f' % lclrot)
		fw('''
			P: "Size", "double", "Number", "",100
			P: "Look", "enum", "", "",1
		}''')
		fw('\n\t\tShading: Y')
		fw('\n\t\tCulling: "CullingOff"')
		fw('\n\t}')
	
	
	# Materials
	def write_material(mat):
		# gather
		mat_cols = mat_cold = 0.8, 0.8, 0.8
		mat_colamb = 0.0, 0.0, 0.0
		mat_dif = 1.0
		mat_amb = 0.5
		mat_hard = 20.0
		mat_spec = 0.2
		mat_alpha = 1.0
		mat_emit = 0.0
		mat_shadeless = False
		mat_shader = 'Phong'
		
		if mat:
			world_amb = 0.0, 0.0, 0.0
			if world:
				world_amb = world.ambient_color[:]
			
			mat_cold = tuple(mat.diffuse_color)
			mat_cols = tuple(mat.specular_color)
			mat_colamb = world_amb

			mat_dif = mat.diffuse_intensity
			mat_amb = mat.ambient
			mat_hard = (float(mat.specular_hardness) - 1.0) / 5.10
			mat_spec = mat.specular_intensity / 2.0
			mat_alpha = mat.alpha
			mat_emit = mat.emit
			mat_shadeless = mat.use_shadeless
			mat_shader = 'Lambert'
			
			if not mat_shadeless:
				if mat.diffuse_shader == 'LAMBERT':
					mat_shader = 'Lambert'
				else:
					mat_shader = 'Phong'
		
		# write
		fw('\n\tMaterial: %i, ' % exporter_data.get_fbx_MaterialID(mat.name))
		fw('"Material::%s", "" {' % mat.name)
		fw('\n\t\tVersion: 102')
		fw('\n\t\tShadingModel: "%s"' % mat_shader.lower())
		fw('\n\t\tMultiLayer: 0')
		fw('\n\t\tProperties70:  {')
		fw('\n\t\t\tP: "EmissiveColor", "Color", "", "A",%.4f,%.4f,%.4f' % mat_cold)
		fw('\n\t\t\tP: "EmissiveFactor", "Number", "", "A",%.4f' % mat_emit)
		fw('\n\t\t\tP: "AmbientColor", "Color", "", "A",%.4f,%.4f,%.4f' % mat_colamb)
		fw('\n\t\t\tP: "DiffuseFactor", "Number", "", "A",%.4f' % mat_dif)
		fw('\n\t\t\tP: "TransparentColor", "Color", "", "A",1,1,1')
		if not mat_shadeless:
			fw('\n\t\t\tP: "SpecularColor", "ColorRGB", "Color", "",%.4f,%.4f,%.4f' % mat_cols)
			fw('\n\t\t\tP: "SpecularFactor", "double", "Number", "",%.4f' % mat_spec)
			fw('\n\t\t\tP: "ShininessExponent", "double", "Number", "",80')
			fw('\n\t\t\tP: "ReflectionColor", "ColorRGB", "Color", "",0,0,0')
			fw('\n\t\t\tP: "ReflectionFactor", "double", "Number", "",1')
		fw('\n\t\t\tP: "Emissive", "ColorRGB", "Color", "",0,0,0')
		fw('\n\t\t\tP: "Ambient", "ColorRGB", "Color", "",%.1f,%.1f,%.1f' % mat_colamb)
		fw('\n\t\t\tP: "Diffuse", "ColorRGB", "Color", "",%.1f,%.1f,%.1f' % mat_cold)
		if not mat_shadeless:
			fw('\n\t\t\tP: "Specular", "ColorRGB", "Color", "",%.1f,%.1f,%.1f' % mat_cols)
			fw('\n\t\t\tP: "Shininess", "double", "Number", "",%.1f' % mat_hard)
		fw('\n\t\t\tP: "Opacity", "double", "Number", "",%.1f' % mat_alpha)
		if not mat_shadeless:
			fw('\n\t\t\tP: "Reflectivity", "double", "Number", "",0')
		fw('\n\t\t}')
		fw('\n\t}')
	
	
	# Videos
	def write_video(texname, tex):
		fw('\n\tVideo: %i, ' % exporter_data.get_fbx_VideoID(tex.name))
		fw('"Video::%s", "Clip" {' % (texname))
		
		if tex:
			fname_rel = bpy_extras.io_utils.path_reference(tex.filepath, base_src, base_dst, 'AUTO', "", copy_set, tex.library)
			fname_strip = bpy.path.basename(fname_rel)
		else:
			fname_strip = fname_rel = ""
		
		fw('''
		Type: "Clip"
		Properties70:  {
			P: "Path", "KString", "XRefUrl", "", "%s"
			P: "PlaySpeed", "double", "Number", "",1
		}
		UseMipMap: 0''' % tex.filepath)
		fw('\n\t\tFilename: "%s"' % tex.filepath)
		fw('\n\t\tRelativeFilename: "%s"' % fname_rel)
		fw('\n\t}')
	
	# Textures
	def write_texture(texname, tex):
		fw('\n\tTexture: %i, ' % exporter_data.get_fbx_TextureID(tex.name))
		fw('"Texture::%s", "" {' % texname)
		fw('\n\t\tType: "TextureVideoClip"')
		fw('\n\t\tVersion: 202')
		
		fw('\n\t\tTextureName: "Texture::%s"' % texname)
		fw('\n\t\tProperties70:  {')
		fw('\n\t\t\tP: "Texture alpha", "Number", "", "A+",%i' % 1)
		fw('\n\t\t\tP: "UVSet", "KString", "", "", "default"')
		fw('\n\t\t\tP: "VideoProperty", "object", "", ""')
		fw('\n\t\t\tP: "CurrentMappingType", "enum", "", "",0')
		fw('\n\t\t\tP: "WrapModeU", "enum", "", "",%i' % tex.use_clamp_x)
		fw('\n\t\t\tP: "WrapModeV", "enum", "", "",%i' % tex.use_clamp_y)
		fw('\n\t\t}')
		fw('\n\t\tMedia: "Video::%s"' % texname)
		
		if tex:
			fname_rel = bpy_extras.io_utils.path_reference(tex.filepath, base_src, base_dst, 'AUTO', "", copy_set, tex.library)
			fname_strip = bpy.path.basename(fname_rel)
		else:
			fname_strip = fname_rel = ""
		
		fw('\n\t\tFileName: "%s"' % tex.filepath)
		fw('\n\t\tRelativeFilename: "%s"' % fname_rel)  # need some make relative command

		fw('''
		ModelUVTranslation: 0,0
		ModelUVScaling: 1,1
		Texture_Alpha_Source: "None"
		Cropping: 0,0,0,0
	}''')
	
	
	# deformers (skin)
	def write_deformer_skin(obname):
		# Each mesh has its own deformer
		fw('\n\tDeformer: %i,' % exporter_data.get_fbx_DeformerSkinID(obname))
		fw(''' "Deformer::Skin %s", "Skin" {
		Version: 101
		Link_DeformAcuracy: 50
	}''' % obname)
	
	# deformers (cluster)
	def write_sub_deformer_skin(my_mesh, my_bone, weights):
		"""
		Each subdeformer is specific to a mesh, but the bone it links to can be used by many sub-deformers
		So the SubDeformer needs the mesh-object name as a prefix to make it unique

		Its possible that there is no matching vgroup in this mesh, in that case no verts are in the subdeformer,
		a but silly but dosnt really matter
		"""
		
		fw('\n\tDeformer: %i, ' % exporter_data.get_fbx_DeformerClusterID(my_mesh.fbxName + '_' + my_bone.fbxName))
		fw('"SubDeformer::Cluster %s ' % my_mesh.fbxName)
		fw('%s", "Cluster" {' % my_bone.fbxName)
		fw('''
		Version: 100
		Properties70:  {
			P: "SrcModel", "object", "", ""
		}
		UserData: "", ""''')
		
		# Support for bone parents
		if my_mesh.fbxBoneParent:
			if my_mesh.fbxBoneParent == my_bone:
				# TODO - this is a bit lazy, we could have a simple write loop
				# for this case because all weights are 1.0 but for now this is ok
				# Parent Bones arent used all that much anyway.
				vgroup_data = [(j, 1.0) for j in range(len(my_mesh.blenData.vertices))]
			else:
				# This bone is not a parent of this mesh object, no weights
				vgroup_data = []

		else:
			# Normal weight painted mesh
			if my_bone.blenName in weights[0]:
				# Before we used normalized weight list
				group_index = weights[0].index(my_bone.blenName)
				vgroup_data = [(j, weight[group_index]) for j, weight in enumerate(weights[1]) if weight[group_index]]
			else:
				vgroup_data = []
		
		if len(vgroup_data) > 0:
			fw('\n\t\tIndexes: *%i {\n\t\t\ta: ' % len(vgroup_data))
			i = -1
			for vg in vgroup_data:
				if i == -1:
					fw('%i' % vg[0])
					i = 0
				else:
					if i == 104:
						fw('\n\t\t')
						i = 0
					fw(',%i' % vg[0])
				i += 1
			fw('\n\t\t}')
			fw('\n\t\tWeights: *%i {\n\t\t\ta: ' % len(vgroup_data))
			
			i = -1
			for vg in vgroup_data:
				if i == -1:
					fw('%.8f' % vg[1])
					i = 0
				else:
					if i == 38:
						fw('\n\t\t')
						i = 0
					fw(',%.8f' % vg[1])
				i += 1
			fw('\n\t\t}')
		# Set TransformLink to the global transform of the bone and Transform
		# equal to the mesh's transform in bone space.
		# http://area.autodesk.com/forum/autodesk-fbx/fbx-sdk/why-the-values-return-by-fbxcluster-gettransformmatrix-x-not-same-with-the-value-in-ascii-fbx-file/

		global_bone_matrix = (my_bone.fbxArm.matrixWorld * my_bone.restMatrix) * mtx4_z90
		global_mesh_matrix = my_mesh.matrixWorld
		transform_matrix = (global_bone_matrix.inverted() * global_mesh_matrix)

		global_bone_matrix_string = mat4x4str(global_bone_matrix )
		transform_matrix_string = mat4x4str(transform_matrix )

		fw('\n\t\tTransform: *16 {\n\t\t\ta: %s' % transform_matrix_string)
		fw('\n\t\t}\n\t\tTransformLink: *16 {\n\t\t\ta: %s' % global_bone_matrix_string)
		fw('\n\t\t}\n\t}')
	
	
	# Blend shapes/morph targets:
	
	# shape geometry
	def write_blend_shape_geometry(my_mesh):
		key_blocks = my_mesh.blenObject.data.shape_keys.key_blocks[:]
		shapeid = exporter_data.get_fbx_GeomID(my_mesh.blenObject.name) + 10000
		
		for kb in key_blocks[1:]:
			shapeid += 1
			
			fw('\n\tGeometry: %i, ' % shapeid)
			fw('"Geometry::%s", "Shape" {' % kb.name)
			fw('\n\t\tVersion: 100')
			
			basis_verts = key_blocks[0].data
			delta_verts = []
			
			vertscount = 0
			for j, kv in enumerate(kb.data):
				delta = kv.co - basis_verts[j].co
				if delta.length > 0.000001:
					vertscount += 1
			
			fw('\n\t\tIndexes: *%i {\n\t\t\ta: ' % vertscount)
			i = -1
			for j, kv in enumerate(kb.data):
				delta = kv.co - basis_verts[j].co
				if delta.length > 0.000001:
					if i == -1:
						fw('%d' % j)
					else:
						if i == 14:
							fw('\n\t\t\t')
							i = 0
						fw(',%d' % j)
					delta_verts.append(delta[:])
					i += 1
			
			fw('\n\t\t}\n\t\tVertices: *%i {\n\t\t\ta: ' % (len(delta_verts) * 3))
			i = -1
			for dv in delta_verts:
				if i == -1:
					fw("%.6f,%.6f,%.6f" % dv)
				else:
					if i == 16:
						fw('\n\t\t\t')
						i = 0
					fw(",%.6f,%.6f,%.6f" % dv)
				i += 1
			
			fw('\n\t\t}\n\t\tNormals: *%i {\n\t\t\ta: ' % (len(delta_verts) * 3))
			i = -1
			for j in range(len(delta_verts)):
				if i == -1:
					fw("0,0,0")
				else:
					if i == 16:
						fw('\n\t\t\t')
						i = 0
					fw(",0,0,0")
				i += 1
			
			fw('\n\t\t}\n\t}')
	
	# shape deformer
	def write_blend_shape_deformer(my_mesh):
		key_blocks = my_mesh.blenObject.data.shape_keys.key_blocks[:]
		shapeid = exporter_data.get_fbx_GeomID(my_mesh.blenObject.name) + 600000
		
		fw('\n\tDeformer: %i, "Deformer::", "BlendShape" {' % shapeid)
		fw('\n\t\tVersion: 100\n\t}')
		
		shapekeycount = 10001
		for kb in key_blocks[1:]:
			fw('\n\tDeformer: %i, ' % (shapekeycount + shapeid))
			fw('''"SubDeformer::%s", "BlendShapeChannel" {
		Version: 100
		DeformPercent: 0
		FullWeights: *1 {
			a: 100
		} 
	}''' % kb.name)
			shapekeycount += 1
	
	
	#		Calculate uv direction for tangent space:
	# - tris required (kind of... half of each face is not considered in
	# calculation if using quads but tangents still turn out ok if engine triangulation is close enough)
	# - uvs must be properly mapped to vertices
	def calc_uvtanbase(uvpoly, polyverts):
		# get uv distances
		uv_dBA = uvpoly[1] - uvpoly[0]
		uv_dCA = uvpoly[2] - uvpoly[0]
		# get point distances
		p_dBA = polyverts[1] - polyverts[0]
		p_dCA = polyverts[2] - polyverts[0]
		# calculate face area - may not be needed since results are pretty much identical on import with or without this
		area = (uv_dBA[0] * uv_dCA[1]) - (uv_dBA[1] * uv_dCA[0])
		if area > 0.0:
			area = 1.0 / area
		tangentdir = Vector(
			((uv_dCA[1] * p_dBA[0]) - (uv_dBA[1] * p_dCA[0]),
			(uv_dCA[1] * p_dBA[1]) - (uv_dBA[1] * p_dCA[1]),
			(uv_dCA[1] * p_dBA[2]) - (uv_dBA[1] * p_dCA[2]))
			) * area
		return tangentdir
	
	
	# Geometry Data
	def write_mesh(my_mesh):
		#Gather mesh data
		me = my_mesh.blenData
		meshobject = my_mesh.blenObject
		
		
		
		# if there are non NULL materials on this mesh
		do_materials = bool(my_mesh.blenMaterials)
		do_textures = bool(my_mesh.blenTextures)
		do_uvs = bool(me.tessface_uv_textures)
		do_shapekeys = (my_mesh.blenObject.type == 'MESH' and
						my_mesh.blenObject.data.shape_keys and
						len(my_mesh.blenObject.data.vertices) == len(me.vertices))
		
		fw(('\n\tGeometry: %i, ' % exporter_data.get_fbx_GeomID(my_mesh.blenObject.name)) +  ('"Geometry::%s", "Mesh" {' % my_mesh.fbxName))
		
		me_vertices = [v for v in me.vertices]
		me_edges = [e for e in me.edges] if use_mesh_edges else ()
		me_faces = [f for f in me.tessfaces]
		
		# base lists for new features:
		me_normals = []
		me_tangents = []
		me_binormals = []
		
		uvverts_list = []
		uv_vertcoords = []
		vindices = []
		vindexlist2 = []
		
		is_collision = ("UCX_" in meshobject.name)
		
		normalsmode = normals_export_mode
		usedefaultnormals = False
		export_tangents = False
		
		if not is_collision:
			# check if tangents need to be exported and uv layer exists
			if export_tangentspace_base != 'NONE':
				if len(me.tessface_uv_textures) > tangentspace_uvlnum:
					export_tangents = True
			
			# check if required normals data exists / autodetect if needed
			if normalsmode == 'AUTO':
				if 'polyn_meshdata' in meshobject or 'vertexn_meshdata' in meshobject:
					normalsmode = 'NORMEDIT'
				elif 'vertex_normal_list' in meshobject:
					normalsmode = 'RECALCVN'
				else:
					normalsmode = 'BLEND'
					usedefaultnormals = True
			elif normalsmode == 'NORMEDIT':
				if bpy.context.window_manager.edit_splitnormals:
					if 'polyn_meshdata' not in meshobject:
						operator.report({'WARNING'}, "List not found")
						usedefaultnormals = True
				else:
					if 'vertexn_meshdata' not in meshobject:
						operator.report({'WARNING'}, "List not found")
						usedefaultnormals = True
			elif normalsmode == 'RECALCVN':
				if 'vertex_normal_list' not in meshobject:
					operator.report({'WARNING'}, "List not found")
					usedefaultnormals = True
			elif normalsmode == 'BLEND':
				usedefaultnormals = True
		else:
			usedefaultnormals = True
		
		
		#################
		# Normals:
		if not usedefaultnormals:
			# Custom - Included normals editor
			if normalsmode == 'NORMEDIT':
				# convert per vertex to per poly if needed
				if bpy.context.window_manager.edit_splitnormals:
					if len(meshobject.polyn_meshdata) == len(me_faces):
						for i in range(len(meshobject.polyn_meshdata)):
							tempvcount = 0
							for vd in meshobject.polyn_meshdata[i].vdata:
								if tempvcount < len(me_faces[i].vertices):
									me_normals.append(Vector(vd.vnormal))
								tempvcount += 1
					else:
						operator.report({'WARNING'}, "List size mismatch")
						usedefaultnormals = True
				else:
					if len(meshobject.vertexn_meshdata) == len(me_vertices):
						for f in me_faces:
							tempverts = [v for v in f.vertices]
							for j in tempverts:
								me_normals.append(Vector(meshobject.vertexn_meshdata[j].vnormal))
					else:
						operator.report({'WARNING'}, "List size mismatch")
						usedefaultnormals = True
				
			# Custom - adsn's Recalc Vertex Normals addon
			elif normalsmode == 'RECALCVN':
				if 'vertex_normal_list' in meshobject:
					if len(meshobject.vertex_normal_list) == len(me_vertices):
						for i in range(len(me_faces)):
							for j in me_faces[i].vertices:
								me_normals.append(Vector(meshobject.vertex_normal_list[j].normal))
					else:
						operator.report({'WARNING'}, "List size mismatch")
						usedefaultnormals = True
			
		# Blender split vertex normals - Default / fallback
		if usedefaultnormals:
			me.calc_normals_split()
			me_normals = [t.normal.copy() for t in me.loops]
			
		
		##############################################################
		# Tangents + Binormals:
		if export_tangents:
			# Custom - modified Lengyel's method
			if export_tangentspace_base == 'LENGYEL':
				me.free_normals_split()
				t_uvlayer = [uvl for uvl in me.tessface_uv_textures[tangentspace_uvlnum].data]
				weightslist = []
				
				for i in range(len(me_faces)):
					faceverts = []
					uvface = []
					uvface.append(t_uvlayer[i].uv1.copy())
					uv_vertcoords.append(t_uvlayer[i].uv1.copy())
					uvface.append(t_uvlayer[i].uv2.copy())
					uv_vertcoords.append(t_uvlayer[i].uv2.copy())
					uvface.append(t_uvlayer[i].uv3.copy())
					uv_vertcoords.append(t_uvlayer[i].uv3.copy())
					if len(me_faces[i].vertices) > 3:
						uvface.append(t_uvlayer[i].uv4.copy())
						uv_vertcoords.append(t_uvlayer[i].uv4.copy())
					
					for j in me_faces[i].vertices:
						faceverts.append(me_vertices[j].co.copy())
						vindexlist2.append(len(vindices))
						vindices.append(j)
					
					for k in range(len(me_faces[i].vertices)):
						uvverts_list.append(calc_uvtanbase(uvface, faceverts))
				
				if len(uvverts_list) != len(me_normals):
					operator.report({'WARNING'}, "UV list length mismatch: Tangents will not be calculated.")
				else :
					# Calculate tangents/binormals from normals list and uvverts_list
					for i in range(len(me_normals)):
						tan = (uvverts_list[i] - (me_normals[i] * me_normals[i].dot(uvverts_list[i]))).normalized()
						me_tangents.append(tan)
						me_binormals.append(me_normals[i].cross(tan))
					
					tempvect = Vector((0.0,0.0,0.0))
					smoothlist = [[],[],[],[]]
					vertstoremove = []
					new_tangents = [v for v in me_tangents]
					
					# 			Tangent Smoothing
					# - averages the tangents for each vert connected to a smoothed face to remove 'jittering'
					# - smoothing is based on uv islands each vert's faces are in
					for i in range(len(me_vertices)):
						# Gather Loop
						# - slow - checks the index list for uv islands each vert is part of
						for j in vindexlist2:
							if vindices[j] == i:
								vertstoremove.append(j)
								if len(smoothlist[0]) > 0:
									if math.sqrt(((uv_vertcoords[j][0] - uv_vertcoords[smoothlist[0][0]][0]) ** 2) + ((uv_vertcoords[j][1] - uv_vertcoords[smoothlist[0][0]][1]) ** 2)) < 0.01:
										smoothlist[0].append(j)
									else:
										if len(smoothlist[1]) > 0:
											if math.sqrt(((uv_vertcoords[j][0] - uv_vertcoords[smoothlist[1][0]][0]) ** 2) + ((uv_vertcoords[j][1] - uv_vertcoords[smoothlist[1][0]][1]) ** 2)) < 0.01:
												smoothlist[1].append(j)
											else:
												if len(smoothlist[2]) > 0:
													if math.sqrt(((uv_vertcoords[j][0] - uv_vertcoords[smoothlist[2][0]][0]) ** 2) + ((uv_vertcoords[j][1] - uv_vertcoords[smoothlist[2][0]][1]) ** 2)) < 0.01:
														smoothlist[2].append(j)
													else:
														smoothlist[3].append(j)
												else:
													smoothlist[2].append(j)
										else:
											smoothlist[1].append(j)
								else:
									smoothlist[0].append(j)
						
						# calculation time tweak: remove indices that won't come up again for less iterations in successive passes
						for k in vertstoremove:
							vindexlist2.remove(k)
						
						# Smoothing pass for this vert
						# - averages the tangents of vertices that are on the same uv island
						# - 4 uv islands / vertex max, anything else gets averaged into fourth island for now
						if len(smoothlist[0]) > 0:
							tempvect.zero()
							for l in smoothlist[0]:
								tempvect += me_tangents[l]
							tempvect = tempvect / float(len(smoothlist[0]))
							for t in smoothlist[0]:
								new_tangents[t] = tempvect.copy()
								me_binormals[t] = me_normals[t].cross(tempvect)
							if len(smoothlist[1]) > 0:
								tempvect.zero()
								for l in smoothlist[1]:
									tempvect += me_tangents[l]
								tempvect = tempvect / float(len(smoothlist[1]))
								for t in smoothlist[1]:
									new_tangents[t] = tempvect.copy()
									me_binormals[t] = me_normals[t].cross(tempvect)
								if len(smoothlist[2]) > 0:
									tempvect.zero()
									for l in smoothlist[2]:
										tempvect += me_tangents[l]
									tempvect = tempvect / float(len(smoothlist[2]))
									for t in smoothlist[2]:
										new_tangents[t] = tempvect.copy()
										me_binormals[t] = me_normals[t].cross(tempvect)
									if len(smoothlist[3]) > 0:
										tempvect.zero()
										for l in smoothlist[3]:
											tempvect += me_tangents[l]
										tempvect = tempvect / float(len(smoothlist[3]))
										for t in smoothlist[3]:
											new_tangents[t] = tempvect.copy()
											me_binormals[t] = me_normals[t].cross(tempvect)
						
						# reset vars for next iteration
						smoothlist = [[],[],[],[]]
						vertstoremove = []
					me_tangents = [v for v in new_tangents]
			else:
				# Blender Default - Mikk TSpace
				# - copy() because me_tangents is cleared by calc_normals_split
				if normalsmode == 'BLEND':
					me.calc_tangents(me.uv_layers[tangentspace_uvlnum].name)
					me_tangents = [t.tangent.copy() for t in me.loops]
					me_binormals = [t.bitangent.copy() for t in me.loops]
					me.free_tangents()
					me.free_normals_split()
				else:
					operator.report({'WARNING'}, "Default Tangents require default normals")
					export_tangents = False
		else:
			me.free_normals_split()
		
		######################################
		# Mesh Geometry Pose:
		# - use global matrix here to apply scale + axis settings to the mesh
		poseMatrix = (meshobject.matrix_world * global_matrix)
		pose_items.append((my_mesh.fbxName, poseMatrix, my_mesh.fbxName))
		
		
		if do_shapekeys:
			fw('\n\t\tProperties70:  {')
			for kb in my_mesh.blenObject.data.shape_keys.key_blocks[1:]:
				fw('\n\t\t\tP: "%s", "Number", "", "A",0' % kb.name)
			fw('\n\t\t}')
		
		############################################
		# Write the Real Mesh data here
		
		# Vertices
		fw('''
		Vertices: *%i {
			a: ''' % (len(me_vertices) * 3))
		
		i = -1
		totalvcnt = 1
		for v in me_vertices:
			if i == -1:
				fw('%.6f,%.6f,%.6f,' % v.co[:])
				i = 0
			else:
				if i == 16:
					fw('\n')
					i = 0
				if totalvcnt >= len(me_vertices):
					fw('%.6f,%.6f,%.6f' % v.co[:])
				else:
					fw('%.6f,%.6f,%.6f,' % v.co[:])
			
			i += 1
			totalvcnt += 1
		fw('\n\t\t}')
		
		totalvertcount = 0
		for f in me_faces:
			totalvertcount += len(f.vertices)
		
		# PolygonVertIndices
		fw('''
		PolygonVertexIndex: *%i {
			a: ''' % totalvertcount)
		i = -1
		totalfcnt = 1
		for f in me_faces:
			fi = [fv for fv in f.vertices]
			# last index XORd w. -1 indicates end of face
			if i == -1:
				if len(fi) == 3:
					fw('%i,%i,%i,' % (fi[0], fi[1], fi[2] ^ -1))
				else:
					fw('%i,%i,%i,%i,' % (fi[0], fi[1], fi[2], fi[3] ^ -1))
				i = 0
			else:
				if i == 26:
					fw('\n')
					i = 0
				
				if totalfcnt >= len(me_faces):
					if len(fi) == 3:
						fw('%i,%i,%i' % (fi[0], fi[1], fi[2] ^ -1))
					else:
						fw('%i,%i,%i,%i' % (fi[0], fi[1], fi[2], fi[3] ^ -1))

				else:
					if len(fi) == 3:
						fw('%i,%i,%i,' % (fi[0], fi[1], fi[2] ^ -1))
					else:
						fw('%i,%i,%i,%i,' % (fi[0], fi[1], fi[2], fi[3] ^ -1))
			i += 1
			totalfcnt += 1
		fw('\n\t\t}')
		
		# Edges - not needed for UE meshes
		if len(me_edges) > 0:
			fw('''
		Edges: *%i {
			a: ''' % len(me_edges))
			
			i = -1
			for ed in me_edges:
				if i == -1:
					fw('%i,%i' % (ed.vertices[0], ed.vertices[1]))
					i = 0
				else:
					if i == 16:
						fw('\n\t\t')
						i = 0
					fw(',%i,%i' % (ed.vertices[0], ed.vertices[1]))
				i += 1
		fw('\n\t\tGeometryVersion: 124')
		
		
		########################################
		#		Normals, Tangents, Binormals:
		
		fw('''
		LayerElementNormal: 0 {
			Version: 101
			Name: ""
			MappingInformationType: "ByPolygonVertex"
			ReferenceInformationType: "Direct"
			Normals: *%i {
				a: ''' % (len(me_normals) * 3))

		i = -1
		normscount = 1
		for v in me_normals:
			if i == -1:
				fw('%.6f,%.6f,%.6f,' % v[:])
				i = 0
			else:
				if i == 12:
					fw('\n')
					i = 0
				if normscount >= len(me_normals):
					fw('%.6f,%.6f,%.6f'% v[:])
				else:
					fw('%.6f,%.6f,%.6f,'% v[:])
			i += 1
			normscount += 1
		fw('\n\t\t\t}\n\t\t}')
		
		if export_tangents:
			fw('''
		LayerElementBinormal: 0 {
			Version: 101
			Name: ""
			MappingInformationType: "ByPolygonVertex"
			ReferenceInformationType: "Direct"
			Binormals: *%i {
				a: ''' % (len(me_binormals) * 3))
			i = -1
			normscount = 1
			for v in me_binormals:
				if i == -1:
					fw('%.6f,%.6f,%.6f,' % v[:])
					i = 0
				else:
					if i == 12:
						fw('\n')
						i = 0
					if normscount >= len(me_binormals):
						fw('%.6f,%.6f,%.6f'% v[:])
					else:
						fw('%.6f,%.6f,%.6f,'% v[:])
				i += 1
				normscount += 1
			fw('\n\t\t\t}\n\t\t}')
			
			fw('''
		LayerElementTangent: 0 {
			Version: 101
			Name: ""
			MappingInformationType: "ByPolygonVertex"
			ReferenceInformationType: "Direct"
			Tangents: *%i {
				a: ''' % (len(me_tangents) * 3))
			i = -1
			normscount = 1
			for v in me_tangents:
				if i == -1:
					fw('%.6f,%.6f,%.6f,' % v[:])
					i = 0
				else:
					if i == 12:
						fw('\n')
						i = 0
					if normscount >= len(me_tangents):
						fw('%.6f,%.6f,%.6f'% v[:])
					else:
						fw('%.6f,%.6f,%.6f,'% v[:])
				i += 1
				normscount += 1
			fw('\n\t\t\t}\n\t\t}')
		
		###########################################
		# Write Smoothing Groups
		
		if mesh_smooth_type == 'FACE' or is_collision:
			fw('''
		LayerElementSmoothing: 0 {
			Version: 102
			Name: ""
			MappingInformationType: "ByPolygon"
			ReferenceInformationType: "Direct"
			Smoothing: *%i {
				a: ''' % len(me_faces))
			i = -1
			totalfcount = 1
			for f in me_faces:
				if i == -1:
					fw('%i,' % f.use_smooth)
					i = 0
				else:
					if i == 108:
						fw('\n')
						i = 0
					if totalfcount >= len(me_faces):
						fw('%i' % f.use_smooth)
					else:
						fw('%i,' % f.use_smooth)
				i += 1
				totalfcount += 1

			fw('\n\t\t\t}\n\t\t}')
		# Write Edge Smoothing
		elif mesh_smooth_type == 'EDGE' and not is_collision:
			fw('''
		LayerElementSmoothing: 0 {
			Version: 101
			Name: ""
			MappingInformationType: "ByEdge"
			ReferenceInformationType: "Direct"
			Smoothing: *%i {
				a: ''' % len(me_edges))

			i = -1
			totalfcount = 1
			for ed in me_edges:
				if i == -1:
					fw('%i,' % (ed.use_edge_sharp))
					i = 0
				else:
					if i == 108:
						fw('\n')
						i = 0
					if totalfcount >= len(me_faces):
						fw('%i' % ed.use_edge_sharp)
					else:
						fw('%i,' % ed.use_edge_sharp)
				i += 1
				totalfcount += 1
			fw('\n\t\t\t}\n\t\t}')
		
		# Write No Smoothing
		elif mesh_smooth_type == 'OFF' and not is_collision:
			pass
		else:
			raise Exception("invalid mesh_smooth_type: %r" % mesh_smooth_type)
		
		
		#####################################################
		# VertexColor Layers
		
		
		
		collayers = []
		if len(me.tessface_vertex_colors):
			collayers = me.tessface_vertex_colors
			
			# combine color layers if needed:
			if merge_vertexcollayers:
				newvcols = []
				finalvcols = []
				totalcolcount = 0
				for collayer in collayers:
					newvcols = []
					totalcolcount = 0
					findex = 0
					for cf in collayer.data:
						totalcolcount += len(me_faces[findex].vertices)
						
						newvcols.append(cf.color1)
						newvcols.append(cf.color2)
						newvcols.append(cf.color3)
						if len(me_faces[findex].vertices) == 4:
							newvcols.append(cf.color4)
						
						findex += 1
					
					tempcount = 0
					for cc in newvcols:
						if len(finalvcols) < len(newvcols):
							finalvcols.append(cc)
						else:
							finalvcols[tempcount] = cc + finalvcols[tempcount]
						
						tempcount += 1
							
				fw('\n\t\tLayerElementColor: 0 {')
				fw('\n\t\t\tVersion: 101')
				fw('\n\t\t\tName: "colscombined"')
				fw('''
				MappingInformationType: "ByPolygonVertex"
				ReferenceInformationType: "IndexToDirect"
				Colors: *%i {
					a: ''' % (totalcolcount * 4))
				
				i = -1
				ii = 0  # Count how many Colors we write
				
				for col in finalvcols:
					if i == -1:
						fw('%.4f,%.4f,%.4f,1' % (col[0], col[1], col[2]))
						i = 0
					else:
						if i == 7:
							fw('\n\t\t\t\t')
							i = 0
						fw(',%.4f,%.4f,%.4f,1' % (col[0], col[1], col[2]))
					i += 1
					ii += 1  # One more Color
				
				fw('\n\t\t\t}\n\t\t\tColorIndex: *%i {' % totalcolcount)
				fw('\n\t\t\t\ta: ')
				i = -1
				for j in range(ii):
					if i == -1:
						fw('%i' % j)
						i = 0
					else:
						if i == 55:
							fw('\n\t\t\t\t')
							i = 0
						fw(',%i' % j)
					i += 1
				fw('\n\t\t\t}\n\t\t}')
				collayers = [collayers[0]]
				
			else:
				for colindex, collayer in enumerate(collayers):
					totalcolcount = 0
					
					for fi, cf in enumerate(collayer.data):
						totalcolcount += len(me_faces[fi].vertices)
					
					fw('\n\t\tLayerElementColor: %i {' % colindex)
					fw('\n\t\t\tVersion: 101')
					fw('\n\t\t\tName: "%s"' % collayer.name)
					fw('''
				MappingInformationType: "ByPolygonVertex"
				ReferenceInformationType: "IndexToDirect"
				Colors: *%i {
					a: ''' % (totalcolcount * 4))
					
					i = -1
					ii = 0  # Count how many Colors we write
					print(len(me_faces), len(collayer.data))
					for fi, cf in enumerate(collayer.data):
						if len(me_faces[fi].vertices) == 4:
							colors = cf.color1[:], cf.color2[:], cf.color3[:], cf.color4[:]
						else:
							colors = cf.color1[:], cf.color2[:], cf.color3[:]
						
						for col in colors:
							if i == -1:
								fw('%.4f,%.4f,%.4f,1' % col)
								i = 0
							else:
								if i == 7:
									fw('\n\t\t\t\t')
									i = 0
								fw(',%.4f,%.4f,%.4f,1' % col)
							i += 1
							ii += 1  # One more Color
					
					fw('\n\t\t\t}\n\t\t\tColorIndex: *%i {' % totalcolcount)
					fw('\n\t\t\t\ta: ')
					i = -1
					for j in range(ii):
						if i == -1:
							fw('%i' % j)
							i = 0
						else:
							if i == 55:
								fw('\n\t\t\t\t')
								i = 0
							fw(',%i' % j)
						i += 1
					fw('\n\t\t\t}\n\t\t}')
		
		# Write UV layers.
		uvlayers = []
		if do_uvs:
			curuv = 0
			uvlayers = me.tessface_uv_textures
			for uvindex, uvlayer in enumerate(me.tessface_uv_textures):
				uvscount = 0
				for uf in uvlayer.data:
					uvscount += len(uf.uv)
				
				fw('''
		LayerElementUV: %i {''' % curuv)
				fw('''
			Version: 101
			Name: "%s"''' % uvlayer.name)
				fw('''
			MappingInformationType: "ByPolygonVertex"
			ReferenceInformationType: "IndexToDirect"
			UV: *%i {
				a: ''' % (uvscount * 2))
				curuv += 1
				i = -1
				ii = 0  # Count how many UVs we write
				
				for uf in uvlayer.data:
					# workaround, since uf.uv iteration is wrong atm
					for uv in uf.uv:
						if i == -1:
							fw('%.6f,%.6f,' % uv[:])
							i = 0
						else:
							if i == 24:
								fw('\n')
								i = 0
							if ii >= (uvscount - 1):
								fw('%.6f,%.6f' % uv[:])
							else:
								fw('%.6f,%.6f,' % uv[:])
						i += 1
						ii += 1  # One more UV
				fw('\n\t\t\t}')
				fw('''
			UVIndex: *%i {
				a: ''' % uvscount)
				
				i = -1
				tempuvcount = 1
				for j in range(ii):
					if i == -1:
						fw('%i,' % j)
						i = 0
					else:
						if i == 55:
							fw('\n')
							i = 0
						if tempuvcount >= uvscount:
							fw('%i' % j)
						else:
							fw('%i,' % j)
					i += 1
					tempuvcount += 1
				
				fw('\n\t\t\t}\n\t\t}')
				

		# Done with UV/textures.
		if do_materials:
			fw('\n\t\tLayerElementMaterial: 0 {')
			fw('\n\t\t\tVersion: 101')
			fw('\n\t\t\tName: ""')

			if len(my_mesh.blenMaterials) == 1:
				fw('\n\t\t\tMappingInformationType: "AllSame"')
			else:
				fw('\n\t\t\tMappingInformationType: "ByPolygon"')

			fw('\n\t\t\tReferenceInformationType: "IndexToDirect"')
			
			if len(my_mesh.blenMaterials) == 1:
				fw('\n\t\t\tMaterials: *1 {\n\t\t\t\ta: 0')
			else:
				fw('\n\t\t\tMaterials: *%i {' % len(me_faces))
				fw('\n\t\t\t\ta: ')
				# Build a material mapping for this
				material_mapping_local = {}  # local-mat & tex : global index.

				for j, mat_tex_pair in enumerate(my_mesh.blenMaterials):
					material_mapping_local[mat_tex_pair] = j

				mats = my_mesh.blenMaterialList

				if me.tessface_uv_textures.active:
					uv_faces = me.tessface_uv_textures.active.data
				else:
					uv_faces = [None] * len(me_faces)

				i = -1
				for f, uf in zip(me_faces, uv_faces):
					try:
						mat = mats[f.material_index]
					except:
						mat = None

					if do_uvs:
						tex = uf.image  # WARNING - MULTI UV LAYER IMAGES NOT SUPPORTED :/
					else:
						tex = None

					if i == -1:
						i = 0
						fw('%s' % material_mapping_local[mat, tex])  # None for mat or tex is ok
					else:
						if i == 55:
							fw('\n\t\t\t\t')
							i = 0

						fw(',%s' % material_mapping_local[mat, tex])
					i += 1

			fw('\n\t\t\t}\n\t\t}')

		fw('''
		Layer: 0 {
			Version: 100
			LayerElement:  {
				Type: "LayerElementNormal"
				TypedIndex: 0
			}''')

		fw('''
			LayerElement:  {
				Type: "LayerElementBinormal"
				TypedIndex: 0
			}''')

		fw('''
			LayerElement:  {
				Type: "LayerElementTangent"
				TypedIndex: 0
			}''')

		if do_materials:
			fw('''
			LayerElement:  {
				Type: "LayerElementMaterial"
				TypedIndex: 0
			}''')

		# Smoothing info
		if mesh_smooth_type != 'OFF':
			fw('''
			LayerElement:  {
				Type: "LayerElementSmoothing"
				TypedIndex: 0
			}''')

		if me.tessface_vertex_colors:
			fw('''
			LayerElement:  {
				Type: "LayerElementColor"
				TypedIndex: 0
			}''')

		if do_uvs:  # same as me.faceUV
			fw('''
			LayerElement:  {
				Type: "LayerElementUV"
				TypedIndex: 0
			}''')

		fw('\n\t\t}')
		
		
		
		# add more layers for additional uvs + colors
		templayercount = len(uvlayers)
		if len(collayers) > templayercount:
			templayercount = len(collayers)
		
		if (templayercount > 1):
			for l in range(1, templayercount):
				fw('\n\t\tLayer: %i {' % l)
				fw('\n\t\t\tVersion: 100')
				
				if len(uvlayers) > l:
					fw('''
			LayerElement:  {
				Type: "LayerElementUV"''')
					fw('\n\t\t\t\tTypedIndex: %i' % l)
					fw('\n\t\t\t}')
				
				if len(collayers) > l:
					fw('''
			LayerElement:  {
				Type: "LayerElementColor"''')
					fw('\n\t\t\t\tTypedIndex: %i' % l)
					fw('\n\t\t\t}')
				
				fw('\n\t\t}')
		
		
		
		fw('\n\t}')

	def write_group(name):
		fw('\n\tGroupSelection: "GroupSelection::%s", "Default" {' % name)

		fw('''
		Properties60:  {
			Property: "MultiLayer", "bool", "",0
			Property: "Pickable", "bool", "",1
			Property: "Transformable", "bool", "",1
			Property: "Show", "bool", "",1
		}
		MultiLayer: 0
	}''')

	# add meshes here to clear because they are not used anywhere.
	meshes_to_clear = []

	ob_meshes = []
	ob_lights = []
	ob_cameras = []
	# in fbx we export bones as children of the mesh
	# armatures not a part of a mesh, will be added to ob_arms
	ob_bones = []
	ob_arms = []
	ob_null = []  # emptys

	# List of types that have blender objects (not bones)
	ob_all_typegroups = [ob_meshes, ob_lights, ob_cameras, ob_arms, ob_null]

	groups = []  # blender groups, only add ones that have objects in the selections
	materials = {}  # (mat, image) keys, should be a set()
	textures = {}  # should be a set()

	tmp_ob_type = None  # in case no objects are exported, so as not to raise an error

## XXX

	if 'ARMATURE' in object_types:
		# This is needed so applying modifiers dosnt apply the armature deformation, its also needed
		# ...so mesh objects return their rest worldspace matrix when bone-parents are exported as weighted meshes.
		# set every armature to its rest, backup the original values so we done mess up the scene
		ob_arms_orig_rest = [arm.pose_position for arm in bpy.data.armatures]

		for arm in bpy.data.armatures:
			arm.pose_position = 'REST'

		if ob_arms_orig_rest:
			for ob_base in bpy.data.objects:
				if ob_base.type == 'ARMATURE':
					ob_base.update_tag()

			# This causes the makeDisplayList command to effect the mesh
			scene.frame_set(scene.frame_current)

	for ob_base in context_objects:

		# ignore dupli children
		if ob_base.parent and ob_base.parent.dupli_type in {'VERTS', 'FACES'}:
			continue

		obs = [(ob_base, ob_base.matrix_world.copy())]
		if ob_base.dupli_type != 'NONE':
			ob_base.dupli_list_create(scene)
			obs = [(dob.object, dob.matrix.copy()) for dob in ob_base.dupli_list]

		for ob, mtx in obs:
			tmp_ob_type = ob.type
			if tmp_ob_type == 'ARMATURE':
				if 'ARMATURE' in object_types:
					# TODO - armatures dont work in dupligroups!
					if ob not in ob_arms:
						ob_arms.append(ob)
					# ob_arms.append(ob) # replace later. was "ob_arms.append(sane_obname(ob), ob)"
			elif tmp_ob_type == 'EMPTY':
				if 'EMPTY' in object_types:
					ob_null.append(my_object_generic(ob, mtx))
			elif 'MESH' in object_types:
				origData = True
				if tmp_ob_type != 'MESH':
					try:
						me = ob.to_mesh(scene, True, 'PREVIEW')
					except:
						me = None

					if me:
						meshes_to_clear.append(me)
						mats = me.materials
						origData = False
				else:
					# Mesh Type!
					if use_mesh_modifiers:
						me = ob.to_mesh(scene, True, 'PREVIEW')

						# print ob, me, me.getVertGroupNames()
						meshes_to_clear.append(me)
						origData = False
						mats = me.materials
					else:
						me = ob.data
						me.update(calc_tessface=True)
						mats = me.materials


				if me:
# 					# This WILL modify meshes in blender if use_mesh_modifiers is disabled.
# 					# so strictly this is bad. but only in rare cases would it have negative results
# 					# say with dupliverts the objects would rotate a bit differently
# 					if EXP_MESH_HQ_NORMALS:
# 						BPyMesh.meshCalcNormals(me) # high quality normals nice for realtime engines.

					texture_mapping_local = {}
					material_mapping_local = {}
					if me.tessface_uv_textures:
						matscheck = []
						for uvlayer in me.tessface_uv_textures:
							for f, uf in zip(me.tessfaces, uvlayer.data):
								tex = uf.image
								textures[tex] = texture_mapping_local[tex] = None

								try:
									mat = mats[f.material_index]
								except:
									mat = None
								
								if mat not in matscheck:
									matscheck.append(mat)
									materials[mat, tex] = material_mapping_local[mat, tex] = None  # should use sets, wait for blender 2.5
									exporter_data.index_fbxMaterials.append(mat.name)

					else:
						
						for mat in mats:
							# 2.44 use mat.lib too for uniqueness
							materials[mat, None] = material_mapping_local[mat, None] = None
						else:
							materials[None, None] = None

					if 'ARMATURE' in object_types:
						armob = ob.find_armature()
						blenParentBoneName = None

						# parent bone - special case
						if (not armob) and ob.parent and ob.parent.type == 'ARMATURE' and \
								ob.parent_type == 'BONE':
							armob = ob.parent
							blenParentBoneName = ob.parent_bone

						if armob and armob not in ob_arms:
							ob_arms.append(armob)

						# Warning for scaled, mesh objects with armatures
						if abs(ob.scale[0] - 1.0) > 0.05 or abs(ob.scale[1] - 1.0) > 0.05 or abs(ob.scale[1] - 1.0) > 0.05:
							operator.report({'WARNING'}, "Object '%s' has a scale of (%.3f, %.3f, %.3f), " \
														 "Armature deformation will not work as expected " \
														 "(apply Scale to fix)" % ((ob.name,) + tuple(ob.scale)))

					else:
						blenParentBoneName = armob = None

					my_mesh = my_object_generic(ob, mtx)
					my_mesh.blenData = me
					my_mesh.origData = origData
					my_mesh.blenMaterials = list(material_mapping_local.keys())
					my_mesh.blenMaterialList = mats
					my_mesh.blenTextures = list(texture_mapping_local.keys())

					# sort the name so we get predictable output, some items may be NULL
					my_mesh.blenMaterials.sort(key=lambda m: (getattr(m[0], "name", ""), getattr(m[1], "name", "")))
					my_mesh.blenTextures.sort(key=lambda m: getattr(m, "name", ""))

					# if only 1 null texture then empty the list
					if len(my_mesh.blenTextures) == 1 and my_mesh.blenTextures[0] is None:
						my_mesh.blenTextures = []

					my_mesh.fbxArm = armob  # replace with my_object_generic armature instance later
					my_mesh.fbxBoneParent = blenParentBoneName  # replace with my_bone instance later

					ob_meshes.append(my_mesh)
					exporter_data.index_fbxModels.append(ob.name)

		# not forgetting to free dupli_list
		if ob_base.dupli_list:
			ob_base.dupli_list_clear()

	if 'ARMATURE' in object_types:
		# now we have the meshes, restore the rest arm position
		for i, arm in enumerate(bpy.data.armatures):
			arm.pose_position = ob_arms_orig_rest[i]

		if ob_arms_orig_rest:
			for ob_base in bpy.data.objects:
				if ob_base.type == 'ARMATURE':
					ob_base.update_tag()
			# This causes the makeDisplayList command to effect the mesh
			scene.frame_set(scene.frame_current)

	del tmp_ob_type, context_objects

	# now we have collected all armatures, add bones
	for i, ob in enumerate(ob_arms):

		ob_arms[i] = my_arm = my_object_generic(ob)

		my_arm.fbxBones = []
		my_arm.blenData = ob.data
		if ob.animation_data:
			my_arm.blenAction = ob.animation_data.action
		else:
			my_arm.blenAction = None
		my_arm.blenActionList = []

		# fbxName, blenderObject, my_bones, blenderActions
		#ob_arms[i] = fbxArmObName, ob, arm_my_bones, (ob.action, [])

		if use_armature_deform_only:
			# tag non deforming bones that have no deforming children
			deform_map = dict.fromkeys(my_arm.blenData.bones, False)
			for bone in my_arm.blenData.bones:
				if bone.use_deform:
					deform_map[bone] = True
					# tag all parents, even ones that are not deform since their child _is_
					for parent in bone.parent_recursive:
						deform_map[parent] = True

		for bone in my_arm.blenData.bones:

			if use_armature_deform_only:
				# if this bone doesnt deform, and none of its children deform, skip it!
				if not deform_map[bone]:
					continue

			my_bone = my_bone_class(bone, my_arm)
			my_arm.fbxBones.append(my_bone)
			ob_bones.append(my_bone)
			exporter_data.index_fbxBones.append(my_bone.fbxName)

		if use_armature_deform_only:
			del deform_map

	# add the meshes to the bones and replace the meshes armature with own armature class
	#for obname, ob, mtx, me, mats, arm, armname in ob_meshes:
	for my_mesh in ob_meshes:
		# Replace
		# ...this could be sped up with dictionary mapping but its unlikely for
		# it ever to be a bottleneck - (would need 100+ meshes using armatures)
		if my_mesh.fbxArm:
			for my_arm in ob_arms:
				if my_arm.blenObject == my_mesh.fbxArm:
					my_mesh.fbxArm = my_arm
					break

		for my_bone in ob_bones:

			# The mesh uses this bones armature!
			if my_bone.fbxArm == my_mesh.fbxArm:
				if my_bone.blenBone.use_deform:
					my_bone.blenMeshes[my_mesh.fbxName] = me

				# parent bone: replace bone names with our class instances
				# my_mesh.fbxBoneParent is None or a blender bone name initialy, replacing if the names match.
				if my_mesh.fbxBoneParent == my_bone.blenName:
					my_mesh.fbxBoneParent = my_bone

	bone_deformer_count = 0  # count how many bones deform a mesh
	my_bone_blenParent = None
	for my_bone in ob_bones:
		my_bone_blenParent = my_bone.blenBone.parent
		if my_bone_blenParent:
			for my_bone_parent in ob_bones:
				# Note 2.45rc2 you can compare bones normally
				if my_bone_blenParent.name == my_bone_parent.blenName and my_bone.fbxArm == my_bone_parent.fbxArm:
					my_bone.parent = my_bone_parent
					break

		# Not used at the moment
		# my_bone.calcRestMatrixLocal()
		bone_deformer_count += len(my_bone.blenMeshes)

	del my_bone_blenParent

	# Build blenObject -> fbxObject mapping
	# this is needed for groups as well as fbxParenting
	bpy.data.objects.tag(False)

	# using a list of object names for tagging (Arystan)

	tmp_obmapping = {}
	for ob_generic in ob_all_typegroups:
		for ob_base in ob_generic:
			ob_base.blenObject.tag = True
			tmp_obmapping[ob_base.blenObject] = ob_base

	# Build Groups from objects we export
	for blenGroup in bpy.data.groups:
		fbxGroupName = None
		for ob in blenGroup.objects:
			if ob.tag:
				if fbxGroupName is None:
					fbxGroupName = sane_groupname(blenGroup)
					groups.append((fbxGroupName, blenGroup))

				tmp_obmapping[ob].fbxGroupNames.append(fbxGroupName)  # also adds to the objects fbxGroupNames

	groups.sort()  # not really needed

	# Assign parents using this mapping
	for ob_generic in ob_all_typegroups:
		for my_ob in ob_generic:
			parent = my_ob.blenObject.parent
			if parent and parent.tag:  # does it exist and is it in the mapping
				my_ob.fbxParent = tmp_obmapping[parent]

	del tmp_obmapping
	# Finished finding groups we use

	# == WRITE OBJECTS TO THE FILE ==
	# == From now on we are building the FBX file from the information collected above (JCB)
	
	foundmats = []
	
	materials = [(sane_matname(mat_tex_pair), mat_tex_pair) for mat_tex_pair in materials.keys()]
	textures = [(sane_texname(tex), tex) for tex in textures.keys()  if tex]
	materials.sort(key=lambda m: m[0])  # sort by name
	textures.sort(key=lambda m: m[0])

	camera_count = 8 if 'CAMERA' in object_types else 0

	# sanity checks
	try:
		assert(not (ob_meshes and ('MESH' not in object_types)))
		assert(not (materials and ('MESH' not in object_types)))
		assert(not (textures and ('MESH' not in object_types)))
		assert(not (textures and ('MESH' not in object_types)))

		assert(not (ob_lights and ('LAMP' not in object_types)))

		assert(not (ob_cameras and ('CAMERA' not in object_types)))
	except AssertionError:
		import traceback
		traceback.print_exc()
	
	tmp = 0
	# Add deformer nodes
	for my_mesh in ob_meshes:
		if my_mesh.fbxArm:
			tmp += 1
	
	# Add subdeformers
	for my_bone in ob_bones:
		tmp += len(my_bone.blenMeshes)
	
	blendshapecount = 0
	for my_mesh in ob_meshes:
		me = my_mesh.blenData
		do_shapekeys = (my_mesh.blenObject.type == 'MESH' and
						my_mesh.blenObject.data.shape_keys and
						len(my_mesh.blenObject.data.vertices) == len(me.vertices))
		if do_shapekeys:
			key_blocks = my_mesh.blenObject.data.shape_keys.key_blocks[:]
			for kb in key_blocks[1:]:
				blendshapecount += 1
	
	# textureindex
	for texname, tex in textures:
		exporter_data.index_fbxTextures.append(tex.name)
	
	fw('''

; Object definitions
;------------------------------------------------------------------

Definitions:  {
	Version: 100
	Count: %i''' % (
		len(ob_meshes) * 2 +
		blendshapecount +
		len(ob_bones) * 2 +
		len(materials) +
		len(textures) * 3 +
		tmp +
		2)) # add 1 each for global config, pose
	
	del bone_deformer_count
	
	# global config
	fw('''
	ObjectType: "GlobalSettings" {
		Count: 1
	}''')
	
	# model config
	# mesh object and bone translation data
	fw('''
	ObjectType: "Model" {
		Count: %i''' % (
		len(ob_meshes) +
		len(ob_bones))) 
	fw('''
		PropertyTemplate: "FbxNode" {
			Properties70:  {
				P: "QuaternionInterpolate", "enum", "", "",0
				P: "RotationOffset", "Vector3D", "Vector", "",0,0,0
				P: "RotationPivot", "Vector3D", "Vector", "",0,0,0
				P: "ScalingOffset", "Vector3D", "Vector", "",0,0,0
				P: "ScalingPivot", "Vector3D", "Vector", "",0,0,0
				P: "TranslationActive", "bool", "", "",0
				P: "TranslationMin", "Vector3D", "Vector", "",0,0,0
				P: "TranslationMax", "Vector3D", "Vector", "",0,0,0
				P: "TranslationMinX", "bool", "", "",0
				P: "TranslationMinY", "bool", "", "",0
				P: "TranslationMinZ", "bool", "", "",0
				P: "TranslationMaxX", "bool", "", "",0
				P: "TranslationMaxY", "bool", "", "",0
				P: "TranslationMaxZ", "bool", "", "",0
				P: "RotationOrder", "enum", "", "",0
				P: "RotationSpaceForLimitOnly", "bool", "", "",0
				P: "RotationStiffnessX", "double", "Number", "",0
				P: "RotationStiffnessY", "double", "Number", "",0
				P: "RotationStiffnessZ", "double", "Number", "",0
				P: "AxisLen", "double", "Number", "",10
				P: "PreRotation", "Vector3D", "Vector", "",0,0,0
				P: "PostRotation", "Vector3D", "Vector", "",0,0,0
				P: "RotationActive", "bool", "", "",0
				P: "RotationMin", "Vector3D", "Vector", "",0,0,0
				P: "RotationMax", "Vector3D", "Vector", "",0,0,0
				P: "RotationMinX", "bool", "", "",0
				P: "RotationMinY", "bool", "", "",0
				P: "RotationMinZ", "bool", "", "",0
				P: "RotationMaxX", "bool", "", "",0
				P: "RotationMaxY", "bool", "", "",0
				P: "RotationMaxZ", "bool", "", "",0
				P: "InheritType", "enum", "", "",0
				P: "ScalingActive", "bool", "", "",0
				P: "ScalingMin", "Vector3D", "Vector", "",0,0,0
				P: "ScalingMax", "Vector3D", "Vector", "",1,1,1
				P: "ScalingMinX", "bool", "", "",0
				P: "ScalingMinY", "bool", "", "",0
				P: "ScalingMinZ", "bool", "", "",0
				P: "ScalingMaxX", "bool", "", "",0
				P: "ScalingMaxY", "bool", "", "",0
				P: "ScalingMaxZ", "bool", "", "",0
				P: "GeometricTranslation", "Vector3D", "Vector", "",0,0,0
				P: "GeometricRotation", "Vector3D", "Vector", "",0,0,0
				P: "GeometricScaling", "Vector3D", "Vector", "",1,1,1
				P: "MinDampRangeX", "double", "Number", "",0
				P: "MinDampRangeY", "double", "Number", "",0
				P: "MinDampRangeZ", "double", "Number", "",0
				P: "MaxDampRangeX", "double", "Number", "",0
				P: "MaxDampRangeY", "double", "Number", "",0
				P: "MaxDampRangeZ", "double", "Number", "",0
				P: "MinDampStrengthX", "double", "Number", "",0
				P: "MinDampStrengthY", "double", "Number", "",0
				P: "MinDampStrengthZ", "double", "Number", "",0
				P: "MaxDampStrengthX", "double", "Number", "",0
				P: "MaxDampStrengthY", "double", "Number", "",0
				P: "MaxDampStrengthZ", "double", "Number", "",0
				P: "PreferedAngleX", "double", "Number", "",0
				P: "PreferedAngleY", "double", "Number", "",0
				P: "PreferedAngleZ", "double", "Number", "",0
				P: "LookAtProperty", "object", "", ""
				P: "UpVectorProperty", "object", "", ""
				P: "Show", "bool", "", "",1
				P: "NegativePercentShapeSupport", "bool", "", "",1
				P: "DefaultAttributeIndex", "int", "Integer", "",-1
				P: "Freeze", "bool", "", "",0
				P: "LODBox", "bool", "", "",0
				P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0
				P: "Lcl Rotation", "Lcl Rotation", "", "A",0,0,0
				P: "Lcl Scaling", "Lcl Scaling", "", "A",1,1,1
				P: "Visibility", "Visibility", "", "A",1
				P: "Visibility Inheritance", "Visibility Inheritance", "", "",1
			}
		}
	}''')
	
	# Geometry config:
	# - mesh data
	fw('''
	ObjectType: "Geometry" {
		Count: %i''' % len(ob_meshes))
	fw('''
		PropertyTemplate: "FbxMesh" {
			Properties70:  {
				P: "Color", "ColorRGB", "Color", "",0.8,0.8,0.8
				P: "BBoxMin", "Vector3D", "Vector", "",0,0,0
				P: "BBoxMax", "Vector3D", "Vector", "",0,0,0
				P: "Primary Visibility", "bool", "", "",1
				P: "Casts Shadows", "bool", "", "",1
				P: "Receive Shadows", "bool", "", "",1
			}
		}
	}''')
	
	# NodeAttribute config:
	# - bone attributes
	fw('''
	ObjectType: "NodeAttribute" {
		Count: %i''' % len(ob_bones))
	
	fw('''
		PropertyTemplate: "FbxSkeleton" {
			Properties70:  {
				P: "Color", "ColorRGB", "Color", "",0.8,0.8,0.8
				P: "Size", "double", "Number", "",100
				P: "LimbLength", "double", "Number", "H",1
			}
		}
	}''')
	
	# material config
	# - switched default to Phong for consistency with UE
	# -probably won't make a difference since attributes are changed on export
	if materials:
		fw('''
	ObjectType: "Material" {
		Count: %i''' % len(materials))
		
		fw('''
		PropertyTemplate: "FbxSurfacePhong" {
			Properties70:  {
				P: "ShadingModel", "KString", "", "", "Phong"
				P: "MultiLayer", "bool", "", "",0
				P: "EmissiveColor", "Color", "", "A",0,0,0
				P: "EmissiveFactor", "Number", "", "A",1
				P: "AmbientColor", "Color", "", "A",0.2,0.2,0.2
				P: "AmbientFactor", "Number", "", "A",1
				P: "DiffuseColor", "Color", "", "A",0.8,0.8,0.8
				P: "DiffuseFactor", "Number", "", "A",1
				P: "Bump", "Vector3D", "Vector", "",0,0,0
				P: "NormalMap", "Vector3D", "Vector", "",0,0,0
				P: "BumpFactor", "double", "Number", "",1
				P: "TransparentColor", "Color", "", "A",0,0,0
				P: "TransparencyFactor", "Number", "", "A",0
				P: "DisplacementColor", "ColorRGB", "Color", "",0,0,0
				P: "DisplacementFactor", "double", "Number", "",1
				P: "VectorDisplacementColor", "ColorRGB", "Color", "",0,0,0
				P: "VectorDisplacementFactor", "double", "Number", "",1
			}
		}
	}''')
	
	if textures:
		# texture config
		fw('''
	ObjectType: "Texture" {
		Count: %i''' % len(textures))
		
		fw('''
		PropertyTemplate: "FbxFileTexture" {
			Properties70:  {
				P: "TextureTypeUse", "enum", "", "",0
				P: "Texture alpha", "Number", "", "A",1
				P: "CurrentMappingType", "enum", "", "",0
				P: "WrapModeU", "enum", "", "",0
				P: "WrapModeV", "enum", "", "",0
				P: "UVSwap", "bool", "", "",0
				P: "PremultiplyAlpha", "bool", "", "",1
				P: "Translation", "Vector", "", "A",0,0,0
				P: "Rotation", "Vector", "", "A",0,0,0
				P: "Scaling", "Vector", "", "A",1,1,1
				P: "TextureRotationPivot", "Vector3D", "Vector", "",0,0,0
				P: "TextureScalingPivot", "Vector3D", "Vector", "",0,0,0
				P: "CurrentTextureBlendMode", "enum", "", "",1
				P: "UVSet", "KString", "", "", "default"
				P: "UseMaterial", "bool", "", "",0
				P: "UseMipMap", "bool", "", "",0
			}
		}
	}''')
		
		# write video config
		fw('''
	ObjectType: "Video" {
		Count: %i''' % (len(textures) * 2))
		
		fw('''
		PropertyTemplate: "FbxVideo" {
			Properties70:  {
				P: "ImageSequence", "bool", "", "",0
				P: "ImageSequenceOffset", "int", "Integer", "",0
				P: "FrameRate", "double", "Number", "",0
				P: "LastFrame", "int", "Integer", "",0
				P: "Width", "int", "Integer", "",0
				P: "Height", "int", "Integer", "",0
				P: "Path", "KString", "XRefUrl", "", ""
				P: "StartFrame", "int", "Integer", "",0
				P: "StopFrame", "int", "Integer", "",0
				P: "PlaySpeed", "double", "Number", "",0
				P: "Offset", "KTime", "Time", "",0
				P: "InterlaceMode", "enum", "", "",0
				P: "FreeRunning", "bool", "", "",0
				P: "Loop", "bool", "", "",0
				P: "AccessMode", "enum", "", "",0
			}
		}
	}''')
	
	
	
	
	if tmp:
		fw('''
	ObjectType: "Deformer" {
		Count: %i
	}''' % tmp)
	del tmp
	
	# Bind pose is essential for XNA if the 'MESH' is included (JCB)
	fw('''
	ObjectType: "Pose" {
		Count: 1
	}''')
	
	fw('\n}\n')
	
	fw('''

; Object properties
;------------------------------------------------------------------

Objects:  {''')

	#if 'CAMERA' in object_types:
	#	# To comply with other FBX FILES
	#	write_camera_switch()

	for my_null in ob_null:
		write_null(my_null)

	# XNA requires the armature to be a Limb (JCB)
	# Note, 2.58 and previous wrote these as normal empties and it worked mostly (except for XNA)
	#for my_arm in ob_arms:
	#	write_null(my_arm, fbxType="Limb", fbxTypeFlags="Skeleton")
	
	# addon scope is mesh only, no need to export cameras + lights
	
	#for my_cam in ob_cameras:
	#	write_camera(my_cam)

	#for my_light in ob_lights:
	#	write_light(my_light)
	
	
	# write geometry
	for my_mesh in ob_meshes:
		write_mesh(my_mesh)
	
	# write blend shapes
	for my_mesh in ob_meshes:
		me = my_mesh.blenData
		do_shapekeys = (my_mesh.blenObject.type == 'MESH' and
						my_mesh.blenObject.data.shape_keys and
						len(my_mesh.blenObject.data.vertices) == len(me.vertices))
		if do_shapekeys:
			write_blend_shape_geometry(my_mesh)
	
	# bone NodeAttributes:
	bindex = 1
	for my_bone in ob_bones:
		write_bone_node(my_bone, bindex)
		bindex += 1
	
	# new model attributes
	for my_mesh in ob_meshes:
		write_modelattributes(my_mesh)
	
	# bone Model/Limbs:
	bindex = 1
	for my_bone in ob_bones:
		write_bone_props(my_bone, bindex)
		bindex += 1
	
	# Write pose is really weird, only needed when an armature and mesh are used together
	# each by themselves do not need pose data. For now only pose meshes and bones

	# Bind pose is essential for XNA if the 'MESH' is included (JCB)
	# added root node for 7.3 - still being read as invalid on UE import
	
	fw('''
	Pose: 100, "Pose::BIND_POSES", "BindPose" {
		Type: "BindPose"
		Version: 100
		NbPoseNodes: %i
		PoseNode:  {''' % (len(pose_items) + 1))
	# RootNode - not really sure if this is needed
	fw('''
			Node: 0
			Matrix: *16 {
				a: 1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1
			} 
		}''')
	
	for fbxName, matrix, tempname in pose_items:
		tempobj = None
		isBone = False
		if tempname in bpy.context.scene.objects:
			tempobj = bpy.context.scene.objects[tempname]
		else:
			for b in ob_bones:
				if b.fbxName == fbxName:
					tempobj = b
					isBone = True
		
		tempname = ''
		
		if isBone:
			tempname = exporter_data.get_fbx_BoneID(tempobj.fbxName)
		else:
			tempname = exporter_data.get_fbx_MeshID(tempobj.name)
		
		fw('\n\t\tPoseNode:  {')
		fw('\n\t\t\tNode: %i' % tempname)
		fw('\n\t\t\tMatrix: *16 {')
		fw('\n\t\t\t\ta: %s' % mat4x4str(matrix if matrix else Matrix()))
		fw('\n\t\t\t}\n\t\t}')
	fw('\n\t}')
	
	#if 'CAMERA' in object_types:
	#	write_camera_default()
	
	# Materials
	for matname, (mat, tex) in materials:
		write_material(mat)
	
	# Videos
	for texname, tex in textures:
		write_video(texname, tex)
	
	# Textures
	for texname, tex in textures:
		write_texture(texname, tex)
	
	
	# NOTE - c4d and motionbuilder dont need normalized weights, but deep-exploration 5 does and (max?) do.

	# Write armature modifiers
	
	# build skin deformer index:
	for my_mesh in ob_meshes:
		if my_mesh.fbxArm:
			#me = my_mesh.blenData
			exporter_data.index_fbxSkins.append(my_mesh.fbxName)
			for my_bone in ob_bones:
				if me in iter(my_bone.blenMeshes.values()):
					exporter_data.index_fbxClusters.append(my_mesh.fbxName + '_' + my_bone.fbxName)
			
	for my_mesh in ob_meshes:
		if my_mesh.fbxArm:
			#me = my_mesh.blenData
			write_deformer_skin(my_mesh.fbxName)
			# Get normalized weights for temorary use
			if my_mesh.fbxBoneParent:
				weights = None
			else:
				weights = meshNormalizedWeights(my_mesh.blenObject, my_mesh.blenData)

			#for bonename, bone, obname, bone_mesh, armob in ob_bones:
			for my_bone in ob_bones:
				if me in iter(my_bone.blenMeshes.values()):
					write_sub_deformer_skin(my_mesh, my_bone, weights)
	
	# Blend shape Deformers
	for my_mesh in ob_meshes:
		me = my_mesh.blenData
		do_shapekeys = (my_mesh.blenObject.type == 'MESH' and
						my_mesh.blenObject.data.shape_keys and
						len(my_mesh.blenObject.data.vertices) == len(me.vertices))
		if do_shapekeys:
			write_blend_shape_deformer(my_mesh)
	
	
	# groups?
	for groupname, group in groups:
		write_group(groupname)
	
	# Finish Writing Objects
	
	fw('\n}')

	# Removed object relations - don't appear to be needed for 7.3
	
	
	#######################################################
	# Object connections:
	
	fw('''

; Object connections
;------------------------------------------------------------------

Connections:  {''')

	# NOTE - The FBX SDK does not care about the order but some importers DO!
	# for instance, defining the material->mesh connection
	# before the mesh->parent crashes cinema4d
	
	# Model - Parent/Root
	for ob_generic in ob_all_typegroups:  # all blender 'Object's we support
		for my_ob in ob_generic:
			# for deformed meshes, don't have any parents or they can get twice transformed.
			# - removed Armature dependency from export and object from file write for root bone fix
			if my_ob.fbxParent and (not my_ob.fbxArm):
				fw('\n\t;Model::%s, ' % my_ob.fbxName)
				fw('Model::%s' % my_ob.fbxParent.fbxName)
				fw('\n\tC: "OO",%i,' % exporter_data.get_fbx_GeomID(my_ob.blenObject.name))
				fw('%i\n\t' % exporter_data.get_fbx_MeshID(my_ob.fbxParent.blenObject.name))
			else:
				if my_ob.fbxName != "Armature":
					fw('\n\t;Model::%s, Model::RootNode' % my_ob.fbxName)
					fw('\n\tC: "OO",%i,0\n\t' % exporter_data.get_fbx_MeshID(my_ob.blenObject.name))
	
	# Root bone - RootNode
	for my_bone in ob_bones:
		if not my_bone.parent:
			fw('\n\t;Model::%s, Model::RootNode' % my_bone.fbxName)
			fw('\n\tC: "OO",%i,0\n\t' % exporter_data.get_fbx_BoneID(my_bone.fbxName))
	
	# Geometry - Model
	for ob_generic in ob_all_typegroups:  # all blender 'Object's we support
		for my_ob in ob_generic:
			if not (my_ob.fbxParent and (not my_ob.fbxArm)):
				if my_ob.fbxName != "Armature":
					fw('\n\t;Geometry::%s, ' % my_ob.fbxName)
					fw('Model::%s' % my_ob.fbxName)
					fw('\n\tC: "OO",%i,' % exporter_data.get_fbx_GeomID(my_ob.blenObject.name))
					fw('%i\n\t' % exporter_data.get_fbx_MeshID(my_ob.blenObject.name))
	
	# Materials
	if materials:
		# Material - Model
		for my_mesh in ob_meshes:
			for mat, tex in my_mesh.blenMaterials:
				mat_name = mat.name if mat else None
				tex_name = tex.name if tex else None
				fw('\n\t;Material::%s, ' % mat_name)
				fw('Model::%s' % my_mesh.fbxName)
				fw('\n\tC: "OO",%i,' % exporter_data.get_fbx_MaterialID(mat.name))
				fw('%i\n\t' % exporter_data.get_fbx_MeshID(my_mesh.blenObject.name))
	
	
	if 'MESH' in object_types:
		
		'''
	;Deformer::, Geometry::SkelCube
	C: "OO",40351760,40311968
		'''
		
		# Shape -> Geometry
		for my_mesh in ob_meshes:
			me = my_mesh.blenData
			do_shapekeys = (my_mesh.blenObject.type == 'MESH' and
							my_mesh.blenObject.data.shape_keys and
							len(my_mesh.blenObject.data.vertices) == len(me.vertices))
			if do_shapekeys:
				key_blocks = my_mesh.blenObject.data.shape_keys.key_blocks[:]
				geomid = exporter_data.get_fbx_GeomID(my_mesh.blenObject.name)
				fw('\n\t;Deformer::, Geometry::%s' % my_mesh.fbxName)
				fw('\n\tC: "OO",%i,' % (geomid + 600000))
				fw('%i\n\t' % exporter_data.get_fbx_GeomID(my_mesh.blenObject.name))
			
		
		# Skin -> Geometry
		for my_mesh in ob_meshes:
			if my_mesh.fbxArm:
				fw('\n\t;Deformer::Skin %s, ' % my_mesh.fbxName)
				fw('Geometry::%s' % my_mesh.fbxName)
				fw('\n\tC: "OO",%i,' % exporter_data.get_fbx_DeformerSkinID(my_mesh.fbxName))
				fw('%i\n\t' % exporter_data.get_fbx_GeomID(my_mesh.blenObject.name))
		
		
		# ShapeChannel -> Shape
		'''
	;SubDeformer::shrink, Deformer::
	C: "OO",40371312,40351760
	
	;SubDeformer::grow, Deformer::
	C: "OO",40372112,40351760
		'''
		for my_mesh in ob_meshes:
			me = my_mesh.blenData
			do_shapekeys = (my_mesh.blenObject.type == 'MESH' and
							my_mesh.blenObject.data.shape_keys and
							len(my_mesh.blenObject.data.vertices) == len(me.vertices))
			if do_shapekeys:
				key_blocks = my_mesh.blenObject.data.shape_keys.key_blocks[:]
				shapeid = exporter_data.get_fbx_GeomID(my_mesh.blenObject.name)
				for kb in key_blocks[1:]:
					shapeid += 1
					fw('\n\t;SubDeformer::%s, Deformer::' % kb.name)
					fw('\n\tC: "OO",%i,' % (shapeid +  610000))
					fw('%i\n\t' % (exporter_data.get_fbx_GeomID(my_mesh.blenObject.name) + 600000))
				
		# ShapeGeometry -> ShapeChannel
		'''
	;Geometry::shrink, SubDeformer::shrink
	C: "OO",40341104,40371312
	
	;Geometry::grow, SubDeformer::grow
	C: "OO",40348480,40372112
		'''
		for my_mesh in ob_meshes:
			me = my_mesh.blenData
			do_shapekeys = (my_mesh.blenObject.type == 'MESH' and
							my_mesh.blenObject.data.shape_keys and
							len(my_mesh.blenObject.data.vertices) == len(me.vertices))
			if do_shapekeys:
				key_blocks = my_mesh.blenObject.data.shape_keys.key_blocks[:]
				shapeid = exporter_data.get_fbx_GeomID(my_mesh.blenObject.name)
				for kb in key_blocks[1:]:
					shapeid += 1
					fw('\n\t;Geometry::%s, ' % kb.name)
					fw('SubDeformer::%s' % kb.name)
					fw('\n\tC: "OO",%i,' % (shapeid + 10000))
					fw('%i\n\t' % (shapeid+ 610000))
		
		
		# Limb -> ParentLimb
		for my_bone in ob_bones:
			if my_bone.parent:
				fw('\n\t;Model::%s, ' % my_bone.fbxName)
				fw('Model::%s' % my_bone.parent.fbxName)
				fw('\n\tC: "OO",%i,' % exporter_data.get_fbx_BoneID(my_bone.fbxName))
				fw('%i\n\t' % exporter_data.get_fbx_BoneID(my_bone.parent.fbxName))
			
			# NodeAttribute -> Limb
			fw('\n\t;Attribute::%s, ' % my_bone.fbxName)
			fw('Model::%s' % my_bone.fbxName)
			fw('\n\tC: "OO",%i,' % exporter_data.get_fbx_BoneAttributeID(my_bone.fbxName))
			fw('%i\n\t' % exporter_data.get_fbx_BoneID(my_bone.fbxName))
			
	
	
		# Cluster - Skin
		for my_bone in ob_bones:
			for fbxMeshObName in my_bone.blenMeshes:  # .keys()
				tempMesh = fbxMeshObName
				for tempobj in ob_meshes:
					if tempobj.fbxArm:
						if tempobj.fbxName == fbxMeshObName:	
							tempMesh = tempobj
				
				fw('\n\t;SubDeformer::Cluster %s %s, ' % (fbxMeshObName, my_bone.fbxName))
				fw('Deformer::Skin %s' % fbxMeshObName)
				fw('\n\tC: "OO",%i,' % exporter_data.get_fbx_DeformerClusterID(fbxMeshObName + '_' + my_bone.fbxName))
				fw('%i\n\t' % exporter_data.get_fbx_DeformerSkinID(fbxMeshObName))
		
		# Limb - Cluster
		for my_bone in ob_bones:
			for fbxMeshObName in my_bone.blenMeshes:  # .keys()
				tempObj = None
				for obj in ob_meshes:
					if obj.fbxName == fbxMeshObName:
						tempObj = obj
						
				fw('\n\t;Model::%s, ' % my_bone.fbxName)
				fw('SubDeformer::Cluster %s %s' % (fbxMeshObName, my_bone.fbxName))
				fw('\n\tC: "OO",%i,' % exporter_data.get_fbx_BoneID(my_bone.fbxName))
				fw('%i\n\t' % exporter_data.get_fbx_DeformerClusterID(fbxMeshObName + '_' + my_bone.fbxName))
	
	if materials:
		if textures:
			# Texture - Material
			for my_mesh in ob_meshes:
				for mat, tex in my_mesh.blenMaterials:
					mat_name = mat.name if mat else None
					tex_name = tex.name if tex else None
					fw('\n\t;Texture::%s, ' % tex_name)
					fw('Material::%s' % mat_name)
					fw('\n\tC: "OO",%i,' % exporter_data.get_fbx_TextureID(tex.name))
					fw('%i\n\t' % exporter_data.get_fbx_MaterialID(mat.name))
	
	# Video - Texture
	if textures:
		for texname, tex in textures:
			fw('\n\t;Video::%s, ' % tex.name)
			fw('Texture::%s' % tex.name)
			fw('\n\tC: "OO",%i,' % exporter_data.get_fbx_VideoID(tex.name))
			fw('%i\n\t' % exporter_data.get_fbx_TextureID(tex.name))
	
	# groups
	if groups:
		for ob_generic in ob_all_typegroups:
			for ob_base in ob_generic:
				for fbxGroupName in ob_base.fbxGroupNames:
					fw('\n\tConnect: "OO", "Model::%s", "GroupSelection::%s"' % (ob_base.fbxName, fbxGroupName))

	fw('\n}')
	
	
	
	#######################################################
	# Takes/Animations
	
	
	# Needed for scene footer as well as animation
	render = scene.render

	# from the FBX sdk
	#define KTIME_ONE_SECOND        KTime (K_LONGLONG(46186158000))
	def fbx_time(t):
		# 0.5 + val is the same as rounding.
		return int(0.5 + ((t / fps) * 46186158000))

	fps = float(render.fps)
	start = scene.frame_start
	end = scene.frame_end
	if end < start:
		start, end = end, start

	# comment the following line, otherwise we dont get the pose
	# if start==end: use_anim = False

	# animations for these object types
	ob_anim_lists = ob_bones, ob_meshes, ob_null, ob_cameras, ob_lights, ob_arms

	if use_anim and [tmp for tmp in ob_anim_lists if tmp]:

		frame_orig = scene.frame_current

		if use_anim_optimize:
			ANIM_OPTIMIZE_PRECISSION_FLOAT = 0.1 ** anim_optimize_precision

		# default action, when no actions are avaioable
		tmp_actions = []
		blenActionDefault = None
		action_lastcompat = None

		# instead of tagging
		tagged_actions = []

		# get the current action first so we can use it if we only export one action (JCB)
		for my_arm in ob_arms:
			blenActionDefault = my_arm.blenAction
			if blenActionDefault:
				break

		if use_anim_action_all:
			tmp_actions = bpy.data.actions[:]
		elif not use_default_take:
			if blenActionDefault:
				# Export the current action (JCB)
				tmp_actions.append(blenActionDefault)

		if tmp_actions:
			# find which actions are compatible with the armatures
			tmp_act_count = 0
			for my_arm in ob_arms:

				arm_bone_names = set([my_bone.blenName for my_bone in my_arm.fbxBones])

				for action in tmp_actions:

					if arm_bone_names.intersection(action_bone_names(my_arm.blenObject, action)):  # at least one channel matches.
						my_arm.blenActionList.append(action)
						tagged_actions.append(action.name)
						tmp_act_count += 1

						# in case there are no actions applied to armatures
						# for example, when a user deletes the current action.
						action_lastcompat = action

			if tmp_act_count:
				# unlikely to ever happen but if no actions applied to armatures, just use the last compatible armature.
				if not blenActionDefault:
					blenActionDefault = action_lastcompat

		del action_lastcompat

		if use_default_take:
			tmp_actions.insert(0, None)  # None is the default action

		fw('''
;Takes and animation section
;----------------------------------------------------

Takes:  {''')

		if blenActionDefault and not use_default_take:
			fw('\n\tCurrent: "%s"' % sane_takename(blenActionDefault))
		else:
			fw('\n\tCurrent: "Default Take"')

		for blenAction in tmp_actions:
			# we have tagged all actious that are used be selected armatures
			if blenAction:
				if blenAction.name in tagged_actions:
					print('\taction: "%s" exporting...' % blenAction.name)
				else:
					print('\taction: "%s" has no armature using it, skipping' % blenAction.name)
					continue

			if blenAction is None:
				# Warning, this only accounts for tmp_actions being [None]
				take_name = "Default Take"
				act_start = start
				act_end = end
			else:
				# use existing name
				take_name = sane_name_mapping_take.get(blenAction.name)
				if take_name is None:
					take_name = sane_takename(blenAction)

				act_start, act_end = blenAction.frame_range
				act_start = int(act_start)
				act_end = int(act_end)

				# Set the action active
				for my_arm in ob_arms:
					if my_arm.blenObject.animation_data and blenAction in my_arm.blenActionList:
						my_arm.blenObject.animation_data.action = blenAction

			# Use the action name as the take name and the take filename (JCB)
			fw('\n\tTake: "%s" {' % take_name)
			fw('\n\t\tFileName: "%s.tak"' % take_name.replace(" ", "_"))
			fw('\n\t\tLocalTime: %i,%i' % (fbx_time(act_start - 1), fbx_time(act_end - 1)))  # ??? - not sure why this is needed
			fw('\n\t\tReferenceTime: %i,%i' % (fbx_time(act_start - 1), fbx_time(act_end - 1)))  # ??? - not sure why this is needed

			fw('''

		;Models animation
		;----------------------------------------------------''')

			# set pose data for all bones
			# do this here in case the action changes
			'''
			for my_bone in ob_bones:
				my_bone.flushAnimData()
			'''
			i = act_start
			while i <= act_end:
				scene.frame_set(i)
				for ob_generic in ob_anim_lists:
					for my_ob in ob_generic:
						#Blender.Window.RedrawAll()
						if ob_generic == ob_meshes and my_ob.fbxArm:
							# We cant animate armature meshes!
							my_ob.setPoseFrame(i, fake=True)
						else:
							my_ob.setPoseFrame(i)

				i += 1

			#for bonename, bone, obname, me, armob in ob_bones:
			for ob_generic in (ob_bones, ob_meshes, ob_null, ob_cameras, ob_lights, ob_arms):

				for my_ob in ob_generic:

					if ob_generic == ob_meshes and my_ob.fbxArm:
						# do nothing,
						pass
					else:

						fw('\n\t\tModel: "Model::%s" {' % my_ob.fbxName)  # ??? - not sure why this is needed
						fw('\n\t\t\tVersion: 1.1')
						fw('\n\t\t\tChannel: "Transform" {')

						context_bone_anim_mats = [(my_ob.getAnimParRelMatrix(frame), my_ob.getAnimParRelMatrixRot(frame)) for frame in range(act_start, act_end + 1)]

						# ----------------
						# ----------------
						for TX_LAYER, TX_CHAN in enumerate('TRS'):  # transform, rotate, scale

							if TX_CHAN == 'T':
								context_bone_anim_vecs = [mtx[0].to_translation() for mtx in context_bone_anim_mats]
							elif	TX_CHAN == 'S':
								context_bone_anim_vecs = [mtx[0].to_scale() for mtx in context_bone_anim_mats]
							elif	TX_CHAN == 'R':
								# Was....
								# elif 	TX_CHAN=='R':	context_bone_anim_vecs = [mtx[1].to_euler()			for mtx in context_bone_anim_mats]
								#
								# ...but we need to use the previous euler for compatible conversion.
								context_bone_anim_vecs = []
								prev_eul = None
								for mtx in context_bone_anim_mats:
									if prev_eul:
										prev_eul = mtx[1].to_euler('XYZ', prev_eul)
									else:
										prev_eul = mtx[1].to_euler()
									context_bone_anim_vecs.append(tuple_rad_to_deg(prev_eul))

							fw('\n\t\t\t\tChannel: "%s" {' % TX_CHAN)  # translation

							for i in range(3):
								# Loop on each axis of the bone
								fw('\n\t\t\t\t\tChannel: "%s" {' % ('XYZ'[i]))  # translation
								fw('\n\t\t\t\t\t\tDefault: %.15f' % context_bone_anim_vecs[0][i])
								fw('\n\t\t\t\t\t\tKeyVer: 4005')

								if not use_anim_optimize:
									# Just write all frames, simple but in-eficient
									fw('\n\t\t\t\t\t\tKeyCount: %i' % (1 + act_end - act_start))
									fw('\n\t\t\t\t\t\tKey: ')
									frame = act_start
									while frame <= act_end:
										if frame != act_start:
											fw(',')

										# Curve types are 'C,n' for constant, 'L' for linear
										# C,n is for bezier? - linear is best for now so we can do simple keyframe removal
										fw('\n\t\t\t\t\t\t\t%i,%.15f,L' % (fbx_time(frame - 1), context_bone_anim_vecs[frame - act_start][i]))
										frame += 1
								else:
									# remove unneeded keys, j is the frame, needed when some frames are removed.
									context_bone_anim_keys = [(vec[i], j) for j, vec in enumerate(context_bone_anim_vecs)]

									# last frame to fisrt frame, missing 1 frame on either side.
									# removeing in a backwards loop is faster
									#for j in xrange( (act_end-act_start)-1, 0, -1 ):
									# j = (act_end-act_start)-1
									j = len(context_bone_anim_keys) - 2
									while j > 0 and len(context_bone_anim_keys) > 2:
										# print j, len(context_bone_anim_keys)
										# Is this key the same as the ones next to it?

										# co-linear horizontal...
										if		abs(context_bone_anim_keys[j][0] - context_bone_anim_keys[j - 1][0]) < ANIM_OPTIMIZE_PRECISSION_FLOAT and \
												abs(context_bone_anim_keys[j][0] - context_bone_anim_keys[j + 1][0]) < ANIM_OPTIMIZE_PRECISSION_FLOAT:

											del context_bone_anim_keys[j]

										else:
											frame_range = float(context_bone_anim_keys[j + 1][1] - context_bone_anim_keys[j - 1][1])
											frame_range_fac1 = (context_bone_anim_keys[j + 1][1] - context_bone_anim_keys[j][1]) / frame_range
											frame_range_fac2 = 1.0 - frame_range_fac1

											if abs(((context_bone_anim_keys[j - 1][0] * frame_range_fac1 + context_bone_anim_keys[j + 1][0] * frame_range_fac2)) - context_bone_anim_keys[j][0]) < ANIM_OPTIMIZE_PRECISSION_FLOAT:
												del context_bone_anim_keys[j]
											else:
												j -= 1

										# keep the index below the list length
										if j > len(context_bone_anim_keys) - 2:
											j = len(context_bone_anim_keys) - 2

									if len(context_bone_anim_keys) == 2 and context_bone_anim_keys[0][0] == context_bone_anim_keys[1][0]:

										# This axis has no moton, its okay to skip KeyCount and Keys in this case
										# pass

										# better write one, otherwise we loose poses with no animation
										fw('\n\t\t\t\t\t\tKeyCount: 1')
										fw('\n\t\t\t\t\t\tKey: ')
										fw('\n\t\t\t\t\t\t\t%i,%.15f,L' % (fbx_time(start), context_bone_anim_keys[0][0]))
									else:
										# We only need to write these if there is at least one
										fw('\n\t\t\t\t\t\tKeyCount: %i' % len(context_bone_anim_keys))
										fw('\n\t\t\t\t\t\tKey: ')
										for val, frame in context_bone_anim_keys:
											if frame != context_bone_anim_keys[0][1]:  # not the first
												fw(',')
											# frame is already one less then blenders frame
											fw('\n\t\t\t\t\t\t\t%i,%.15f,L' % (fbx_time(frame), val))

								if i == 0:
									fw('\n\t\t\t\t\t\tColor: 1,0,0')
								elif i == 1:
									fw('\n\t\t\t\t\t\tColor: 0,1,0')
								elif i == 2:
									fw('\n\t\t\t\t\t\tColor: 0,0,1')

								fw('\n\t\t\t\t\t}')
							fw('\n\t\t\t\t\tLayerType: %i' % (TX_LAYER + 1))
							fw('\n\t\t\t\t}')

						# ---------------

						fw('\n\t\t\t}')
						fw('\n\t\t}')

			# end the take
			fw('\n\t}')

			# end action loop. set original actions
			# do this after every loop in case actions effect eachother.
			for my_arm in ob_arms:
				if my_arm.blenObject.animation_data:
					my_arm.blenObject.animation_data.action = my_arm.blenAction

		fw('\n}')

		scene.frame_set(frame_orig)

	else:
		# no animation
		fw('\n;Takes and animation section')
		fw('\n;----------------------------------------------------')
		fw('\n')
		fw('\nTakes:  {')
		fw('\n\tCurrent: ""')
		fw('\n}')

	
	# Clear mesh data Only when writing with modifiers applied
	for me in meshes_to_clear:
		bpy.data.meshes.remove(me)
	
	fw('\n')
	
	
	# XXX, shouldnt be global!
	for mapping in (sane_name_mapping_ob,
					sane_name_mapping_ob_unique,
					sane_name_mapping_mat,
					sane_name_mapping_tex,
					sane_name_mapping_take,
					sane_name_mapping_group,
					):
		mapping.clear()
	del mapping

	del ob_arms[:]
	del ob_bones[:]
	del ob_cameras[:]
	del ob_lights[:]
	del ob_meshes[:]
	del ob_null[:]

	file.close()

	# copy all collected files.
	bpy_extras.io_utils.path_reference_copy(copy_set)

	print('export finished in %.4f sec.' % (time.clock() - start_time))
	return {'FINISHED'}


def save(operator, context,
		 filepath="",
		 use_selection=False,
		 batch_mode='OFF',
		 use_batch_own_dir=False,
		 **kwargs
		 ):

	if bpy.ops.object.mode_set.poll():
		bpy.ops.object.mode_set(mode='OBJECT')

	if batch_mode == 'OFF':
		kwargs_mod = kwargs.copy()
		if use_selection:
			kwargs_mod["context_objects"] = context.selected_objects
		else:
			kwargs_mod["context_objects"] = context.scene.objects

		return save_single(operator, context.scene, filepath, **kwargs_mod)
	else:
		fbxpath = filepath

		prefix = os.path.basename(fbxpath)
		if prefix:
			fbxpath = os.path.dirname(fbxpath)

		if not fbxpath.endswith(os.sep):
			fbxpath += os.sep

		if batch_mode == 'GROUP':
			data_seq = bpy.data.groups
		else:
			data_seq = bpy.data.scenes

		# call this function within a loop with BATCH_ENABLE == False
		# no scene switching done at the moment.
		# orig_sce = context.scene

		new_fbxpath = fbxpath  # own dir option modifies, we need to keep an original
		for data in data_seq:  # scene or group
			newname = prefix + bpy.path.clean_name(data.name)

			if use_batch_own_dir:
				new_fbxpath = fbxpath + newname + os.sep
				# path may already exist
				# TODO - might exist but be a file. unlikely but should probably account for it.

				if not os.path.exists(new_fbxpath):
					os.makedirs(new_fbxpath)

			filepath = new_fbxpath + newname + '.fbx'

			print('\nBatch exporting %s as...\n\t%r' % (data, filepath))

			# XXX don't know what to do with this, probably do the same? (Arystan)
			if batch_mode == 'GROUP':  # group
				# group, so objects update properly, add a dummy scene.
				scene = bpy.data.scenes.new(name="FBX_Temp")
				scene.layers = [True] * 20
				# bpy.data.scenes.active = scene # XXX, cant switch
				for ob_base in data.objects:
					scene.objects.link(ob_base)

				scene.update()
			else:
				scene = data

				# TODO - BUMMER! Armatures not in the group wont animate the mesh

			# else:  # scene
			#     data_seq.active = data

			# Call self with modified args
			# Dont pass batch options since we already usedt them
			kwargs_batch = kwargs.copy()

			kwargs_batch["context_objects"] = data.objects

			save_single(operator, scene, filepath, **kwargs_batch)

			if batch_mode == 'GROUP':
				# remove temp group scene
				bpy.data.scenes.remove(scene)

		# no active scene changing!
		# bpy.data.scenes.active = orig_sce

		return {'FINISHED'}  # so the script wont run after we have batch exported.

# removed application requirements section
