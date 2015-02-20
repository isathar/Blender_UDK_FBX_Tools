###################################################################################################
# imports normals to the normal editor's mesh data variable from an existing FBX file
#
# - can import single or multiple meshes' normals (or all)
# - only FBX 6.1 supported for now
#
##########################################################

import bpy
import bmesh
import math
from mathutils import Vector
from bpy_extras.io_utils import (ImportHelper,path_reference_mode)
from bpy.props import (StringProperty,BoolProperty)
import os.path


# parse a LayerElementX line into a list of strings
def get_listfromline(line):
	newlist = []
	templist = []
	
	if ": " in line:
		tempstring = line.split(": ")[1]
		templist = tempstring.split(",")
		templist[len(templist) - 1] = (templist[len(templist) - 1].split("\n"))[0]
		for i in range(len(templist)):
			newlist.append(float(templist[i]))
	else:
		templist = line.split(",")
		templist[len(templist) - 1] = (templist[len(templist) - 1].split("\n"))[0]
		for i in range(1, len(templist)):
			newlist.append(float(templist[i]))
	
	return newlist


# convert a list of floats into a list of vectors
def convert_listtovectors(oldlist):
	newList = []
	tempcount = 0
	roundcount = 0
	tempVect = Vector([0.0,0.0,0.0])
	
	for i in range(len(oldlist)):
		if tempcount < 3:
			tempVect[tempcount] = oldlist[i]
			if tempcount == 2:
				newList.append(tempVect)
				tempcount = 0
				tempVect = Vector([0.0,0.0,0.0])
				roundcount += 1
			else:
				tempcount += 1
	
	return newList


# copy imported normals to the selected mesh
def copy_importednormals(objname, normals_list):
	# get ref to current object
	tempobject = "none"
	returnstr = "no mesh found"
	
	for obj in bpy.context.scene.objects:
		if obj.name == objname:
			tempobject = obj
			tempobject.select = True
			bpy.context.scene.objects.active = tempobject
	
	if tempobject != "none":
		# make sure mesh data exists
		if 'polyn_meshdata' in tempobject:
			# go to edit mode, get mesh data
			lastMode = bpy.context.mode
			if lastMode != "EDIT_MESH":
				bpy.ops.object.mode_set(mode='EDIT')
			
			me = tempobject.data
			bm = bmesh.from_edit_mesh(me)
			me.update()
			
			# build lists + counts
			faces_list = [f for f in bm.faces]
			faces_count = len(bm.faces)
			verts_perface = [len(f.verts) for f in bm.faces]
			verts_count = 0
			for c in verts_perface:
				verts_count += c
			
			# make sure selected mesh has the same # of faces/verts
			if faces_count == len(tempobject.polyn_meshdata):
				if verts_count == len(normals_list):
					# build the new mesh data
					vcount = 0
					for i in range(faces_count):
						faceverts = [v for v in faces_list[i].verts]
						for j in range(verts_perface[i]):
							if vcount < len(normals_list):
								tempobject.polyn_meshdata[i].vdata[j].vnormal = normals_list[vcount]
								vcount += 1
					
					returnstr =  ("imported " + str(vcount) + " normals")
				else:
					returnstr = ("Error: Mesh vertices different from file: " + str(len(normals_list)) + " in file / " + str(verts_count) + " in mesh")
			else:
				returnstr = ("Error: Mesh faces different from file: " + str(len(tempobject.polyn_meshdata)) + " in file / " + str(faces_count) + " in mesh")
			
			bpy.ops.object.mode_set(mode='OBJECT')
		else:
			returnstr = "no meshdata found"
		
		tempobject.select = False
		
	return returnstr


# imports normals for specified meshes
def import_readfbxfile(importfilepath, selectedonly):
	print ("Import Path = " + importfilepath)
	
	if os.path.exists(importfilepath):
		if os.path.isfile(importfilepath):
			# collect meshes to import
			objectstoread = []
			if selectedonly:
				for obj in bpy.context.scene.objects:
					if obj.type == 'MESH':
						if obj.select:
							objectstoread.append(obj.name)
							obj.select = False
			else:
				for obj in bpy.context.scene.objects:
					if obj.type == 'MESH':
						objectstoread.append(obj.name)
						obj.select = False
			
			# init stuff
			normals_list = []
			reading_object = False
			readlayer_normals = False
			reading_normals = False
			
			objcount_needed = len(objectstoread)
			objcount_imported = 0
			objcount_infile = 0
			
			# for each selected object
			for i in range(len(objectstoread)):
				normals_list = []
				
				objname = objectstoread[i]
				print("starting import for " + objname)
				
				# read file, collect normals
				file = open(importfilepath, 'r')
				
				for line in file:
					if reading_object:
						if readlayer_normals:
							if not reading_normals:
								if "Normals:" in line:
									# first line, start reading
									reading_normals = True
							
							if reading_normals:
								# > second line
								if "}" in line:
									reading_normals = False
									readlayer_normals = False
									reading_object = False
									break
								else:
									tempList = []
									tempList = get_listfromline(line)
									[normals_list.append(f) for f in tempList]
						else:
							if "LayerElementNormal" in line:
								# Normals layer found, prime read
								readlayer_normals = True
					else:
						if "Model::" in line:
							if objname in line:
								# current object found
								reading_object = True
								objcount_infile += 1
				
				file.close()
				
				# convert + set normals
				if len(normals_list) > 0:
					tempList2 = convert_listtovectors(normals_list)
					if len(tempList2) > 0:
						importstr = copy_importednormals(objname, tempList2)
						if importstr != "no mesh found" and importstr != "no meshdata found":
							objcount_imported += 1
						print (objname + ": " + importstr)
			
			# debug stuff:
			print ("- Import Stats -")
			print ("# Selected: " + str(objcount_needed))
			print ("# Imported: " + str(objcount_imported))
			print ("# in file : " + str(objcount_infile))
			
	return {"Finished"}


class import_customnormals(bpy.types.Operator, ImportHelper):
	bl_idname = "object.import_customnormals"
	bl_label = "Import Normals"
	bl_description = 'Import mesh normals to use in editor'
	
	filename_ext = ".fbx"
	filter_glob = StringProperty(default="*.fbx", options={'HIDDEN'})
	
	import_selected = BoolProperty(default=True,name="Selected Objects",description="Import normals to selected objects only")
	
	def execute(self, context):
		import_readfbxfile(self.filepath, self.import_selected)
		
		return {'FINISHED'}
