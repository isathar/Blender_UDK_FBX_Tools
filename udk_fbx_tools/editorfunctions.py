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


# Helper functions for FBX Tools

import bpy
import bmesh
import bgl
import blf
import math
from mathutils import Vector

##################
# Math stuff:

# returns true if point is within distance^2
def in_distance(p1, p2, checkdist):
	tempdist = math.sqrt((p1[0] - p2[0]) ** 2) + (((p1[1] - p2[1]) ** 2) + (p1[2] - p2[2]) ** 2)
	return (tempdist < checkdist)

# angle check
# def. mag = 0.96
def in_angle(p1, p2, mag):
	return (p1.dot(p2) > mag)

# returns average vector of list
def get_average(vectlist):
	count = 0
	tempvect = Vector((0.0,0.0,0.0))
	for i in range(len(vectlist)):
		tempvect += Vector(vectlist[i])
		count += 1
	if count > 0:
		tempvect = tempvect / (count * 1.0)
	return tempvect

# prepare for .6f + normalize
def prepare_vector(vec):
	vec = vec.normalized()
	vec[0] = round(vec[0] * 1000000.0) * 0.000001
	vec[1] = round(vec[1] * 1000000.0) * 0.000001
	vec[2] = round(vec[2] * 1000000.0) * 0.000001
	return vec


########################
# Mesh stuff:

# returns true if a list of locations represents the same face as verts provided
def is_sameface(vertlist_locs, vertlist):
	count = 0
	for vl in vertlist_locs:
		for v in vertlist:
			if in_distance(v, vl, 0.0001):
				count += 1
	return (count == len(vertlist_locs))

def set_vertnormal_byloc(vertnorm, vloc, listobject):
	for v in listobject.vdata:
		if in_distance(vloc, v.vpos, 0.0001):
			v.vnormal = vertnorm
			break

def get_vert_fromloc(verts_list, vloc):
	for i in range(len(verts_list)):
		if in_distance(verts_list[i].co, vloc, 0.0001):
			return verts_list[i]
	return []
	

############################
# MeshData List Operations:

def get_facesforvert(listobject, vertloc):
	indices = []
	for i in range(len(listobject)):
		foundone = False
		for j in range(len(listobject[i].vdata)):
			if not foundone:
				if in_distance(vertloc, listobject[i].vdata[j].vpos, 0.0001):
					indices += [i]
					foundone = True
	return indices

# returns index of poly in list
def find_bycenter(listobject, fcenter):
	for i in range(len(listobject)):
		if in_distance(listobject[i].fcenter, fcenter, 0.0001):
			return i
	return -1


def update_face_inlist(oldface, newface):
	oldface.fcenter = newface.fcenter
	oldface.fnormal = newface.fnormal
	oldface.fsgroup = newface.fsgroup
	oldface.vcount = newface.vcount
	
	oldface.vdata.clear()
	for i in range(len(newface.vdata)):
		updface = oldface.vdata.add()
		updface.vnormal = newface.vdata[i].vnormal
		updface.vpos = newface.vdata[i].vpos

def replace_byindex(olddata, newdata, index):
	oldfdata = olddata[index]
	newfdata = newdata[index]
	
	oldfdata.fcenter = newfdata.fcenter
	oldfdata.fnormal = newfdata.fnormal
	oldfdata.fsgroup = newdata.fsgroup
	oldfdata.vcount = newfdata.vcount
	
	for i in range(len(oldfdata.vdata)):
		oldfdata.vdata[i].vnormal = newfdata.vdata[i].vnormal
		oldfdata.vdata[i].vpos = newfdata.vdata[i].vpos


##################
# Vertex Normals:

# writes normals data to list from specified vertex list
def write_frompoly(listobject, vlist):
	listobject.clear()
	for i in range(len(vlist)):
		n = listobject.add()
		n.vnormal = prepare_vector(vlist[i].normal)
		n.vpos = vlist[i].co

# transfers data between vdata lists
def write_normals_fromlist(oldlist, newlist):
	for i in range(len(oldlist)):
		n = oldlist[i]
		n.vnormal = newlist.vnormal
		n.vpos = newlist.vpos

# get vnormals as list
def get_polynormal_forvert(vertloc, listobject):
	normlist = []
	
	for i in range(len(listobject)):
		lo = listobject[i]
		foundone = False
		for j in range(len(lo.vdata)):
			if not foundone:
				vd = lo.vdata[j]
				if in_distance(vertloc,vd.vpos,0.0001):
					normlist += [vd.vnormal]
					foundone = True
	return normlist


##
# generate new normals based on preset
def generate_newnormals(self, context):
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)
	me.update()
	
	faces_list = [f for f in bm.faces]
	
	genmode = bpy.context.window_manager.vn_generatemode

	if bpy.context.window_manager.vn_resetongenerate:
		bpy.context.object.custom_meshdata.clear()

		for i in range(len(faces_list)):
			f = faces_list[i]
			faceverts = [v for v in f.verts]
			tempfacedata = bpy.context.object.custom_meshdata.add()
			tempfacedata.fcenter = f.calc_center_median()
			tempfacedata.fnormal = f.normal
			tempfacedata.fsgroup = 1
			tempfacedata.vcount = len(faceverts)
			
			if 'vdata' not in tempfacedata:
				tempfacedata['vdata'] = []
				
			for j in range(len(faceverts)):
				tempvertdata = tempfacedata.vdata.add()


			write_frompoly(tempfacedata.vdata, faceverts)

	#############################
	# Blender default normals
	if (genmode == 'DEFAULT'):
		if bpy.context.window_manager.vn_genselectiononly:
			bpy.context.window_manager.temp_meshdata.clear()
		
			newfaceslist = []
			oldselection = []
			for i in range(len(faces_list)):
				f = faces_list[i]
				
				if f.select:
					oldselection += [f]
					for v in f.verts:
						if v.select:
							v.select = False
					
			for i in range(len(oldselection)):
				f = oldselection[i]
				f.select = False
				f2 = f.copy()
				f2.select = True
			
			bpy.ops.mesh.remove_doubles(threshold=0.0001, use_unselected=False)
			bpy.ops.mesh.faces_shade_smooth()
			#bpy.ops.mesh.subdivide(number_cuts=2, smoothness=1.0, quadtri=False, quadcorner='STRAIGHT_CUT', fractal=0.0, fractal_along_normal=0.0, seed=0)
			
			updated_faces_list = [f for f in bm.faces]
			for i in range(len(updated_faces_list)):
				f = updated_faces_list[i]
				
				if f.select:
					f.normal_update()
					newfaceslist += [f]
			
			for i in range(len(newfaceslist)):
				f = newfaceslist[i]
				tempfacedata = bpy.context.window_manager.temp_meshdata.add()
				tempfacedata.fcenter = f.calc_center_median()
				tempfacedata.fnormal = f.normal
				tempfacedata.fsgroup = 1
				tempverts = [v for v in f.verts]
				tempfacedata.vcount = len(tempverts)
				
				if 'vdata' not in tempfacedata:
					tempfacedata['vdata'] = []
					
				for j in range(len(tempverts)):
					tempvertdata = tempfacedata.vdata.add()

				write_frompoly(tempfacedata.vdata, tempverts)
			
			verts_list = [v for v in bm.verts]
			for i in range(len(bpy.context.window_manager.temp_meshdata)):
				vertslist = []
				tn = bpy.context.window_manager.temp_meshdata[i]
				tempindex = find_bycenter(bpy.context.object.custom_meshdata[:], tn.fcenter)
				
				if tempindex > -1:
					update_face_inlist(bpy.context.object.custom_meshdata[tempindex], tn)
			
			bpy.ops.mesh.delete(type='VERT')
			
			bpy.context.window_manager.temp_meshdata.clear()
		else:
			for i in range(len(faces_list)):
				f = faces_list[i]
				faceverts = f.verts[:]
				for j in range(len(faceverts)):
					v = faceverts[j]
					v.normal_update()
			
			bpy.context.object.custom_meshdata.clear()
			for i in range(len(faces_list)):
				f = faces_list[i]
				faceverts = [v for v in f.verts]
				tempfacedata = bpy.context.object.custom_meshdata.add()
				tempfacedata.fcenter = f.calc_center_median()
				tempfacedata.fnormal = f.normal
				tempfacedata.fsgroup = 1
				tempfacedata.vcount = len(faceverts)
				
				if 'vdata' not in tempfacedata:
					tempfacedata['vdata'] = []
					
				for j in range(len(faceverts)):
					tempvertdata = tempfacedata.vdata.add()


				write_frompoly(tempfacedata.vdata, faceverts)

	###############################
	# Up-Vector normals / custom directional normals
	elif (genmode == 'UPVECT'):
		
		if bpy.context.window_manager.vn_genselectiononly:
			for i in range(len(bpy.context.object.custom_meshdata)):
				for j in range(len(bpy.context.object.custom_meshdata[i].vdata)):
					if faces_list[i].verts[j].select:
						bpy.context.object.custom_meshdata[i].vdata[j].vnormal = bpy.context.window_manager.vn_directionalgendir
		else:
			for i in range(len(bpy.context.object.custom_meshdata)):
				for j in range(len(bpy.context.object.custom_meshdata[i].vdata)):
					bpy.context.object.custom_meshdata[i].vdata[j].vnormal = bpy.context.window_manager.vn_directionalgendir

	#########################
	# Bent normals
	elif (genmode == 'POINT'):
		
		cursorloc = context.scene.cursor_location
		if bpy.context.window_manager.vn_genselectiononly or bpy.context.window_manager.vn_genfoliagecalcinverse:
			for i in range(len(bpy.context.object.custom_meshdata)):
				for j in range(len(bpy.context.object.custom_meshdata[i].vdata)):
					if not (faces_list[i].hide) and faces_list[i].select:
						tempv = Vector(bpy.context.object.custom_meshdata[i].vdata[j].vpos) - cursorloc
						tempv = tempv.normalized()
						bpy.context.object.custom_meshdata[i].vdata[j].vnormal = tempv
		else:
			for vn in bpy.context.object.custom_meshdata:
				for vd in vn.vdata:
					tempv = Vector(vd.vpos) - cursorloc
					tempv = tempv.normalized()
					vd.vnormal = tempv
		
		if bpy.context.window_manager.vn_genfoliagecalcinverse:
			for i in range(len(bpy.context.object.custom_meshdata)):
				for j in range(len(bpy.context.object.custom_meshdata[i].vdata)):
					if not (faces_list[i].hide) and not (faces_list[i].select):
						tempv = cursorloc - Vector(bpy.context.object.custom_meshdata[i].vdata[j].vpos)
						tempv = tempv.normalized()
						bpy.context.object.custom_meshdata[i].vdata[j].vnormal = tempv
	
	###################################################
	# combination bent and up-vector for ground foliage
	elif (genmode == 'G_FOLIAGE'):
		ignorehidden = bpy.context.window_manager.vn_genignorehidden
		#cursorloc = context.scene.cursor_location
		cursorloc = Vector(bpy.context.window_manager.vn_gfoliage_centeroffset)
		for i in range(len(bpy.context.object.custom_meshdata)):
			ignoreface = False
			if ignorehidden:
				if faces_list[i].hide:
					ignoreface = True
			for j in range(len(bpy.context.object.custom_meshdata[i].vdata)):
				if faces_list[i].verts[j].select:
					if not ignoreface:
						bpy.context.object.custom_meshdata[i].vdata[j].vnormal = (0.0,0.0,1.0)
				else:	
					if not ignoreface:
						tempv = Vector(bpy.context.object.custom_meshdata[i].vdata[j].vpos) - cursorloc
						tempv = tempv.normalized()
						bpy.context.object.custom_meshdata[i].vdata[j].vnormal = tempv
	
	##########################
	# Angle-based custom algorithm
	elif (genmode == 'ANGLES'):
		wipnormalslist = [f.normal for f in faces_list]
		verts_list = [v for v in bm.verts]
		
		if bpy.context.window_manager.vn_genselectiononly:
			bpy.context.window_manager.temp_meshdata.clear()
			selectedlist = []
			
			# Pass 1 - Faces
			for j in range(len(bpy.context.object.custom_meshdata)):
				vn = bpy.context.object.custom_meshdata[j]
				tempface = bpy.context.window_manager.temp_meshdata.add()
				
				fnormal = vn.fnormal
				
				for k in range(len(vn.vdata)):
					if faces_list[j].select:
						selectedlist += [1]
						vd = vn.vdata[k]
						v = get_vert_fromloc(verts_list, vd.vpos)
						vd.vnormal = wipnormalslist[j]
					else:
						selectedlist += [0]
				
				update_face_inlist(tempface, vn)
			
			# Pass 2 - Vertices
			vertcount = 0
			for j in range(len(bpy.context.object.custom_meshdata)):
				vn = bpy.context.object.custom_meshdata[j]
				fnormal = vn.fnormal
				
				for k in range(len(vn.vdata)):
					if selectedlist[vertcount] > 0:
						vd = vn.vdata[k]
						tempnorms = []
						v = get_vert_fromloc(verts_list, vd.vpos)

						tempnorms = get_polynormal_forvert(vd.vpos, bpy.context.window_manager.temp_meshdata)
						avg = []

						for i in range(len(tempnorms)):
							if in_angle(Vector(tempnorms[i]), Vector(vd.vnormal), bpy.context.window_manager.vn_anglebased_dot_vert):
								avg += [tempnorms[i]]
						if len(avg) > 0:
							vd.vnormal = get_average(avg).normalized()
						else:
							vd.vnormal = fnormal
					
					vertcount += 1
			bpy.context.window_manager.temp_meshdata.clear()
			
		else:
			bpy.context.window_manager.temp_meshdata.clear()
			
			connectedfaces = []
			
			# Pass 1 - Faces
			for j in range(len(bpy.context.object.custom_meshdata)):
				vn = bpy.context.object.custom_meshdata[j]
				tempface = bpy.context.window_manager.temp_meshdata.add()
				
				fnormal = vn.fnormal
				for k in range(len(vn.vdata)):
					vd = vn.vdata[k]
					vd.vnormal = wipnormalslist[j]
				
				update_face_inlist(tempface, vn)
			
			# Pass 2 - Vertices
			for j in range(len(bpy.context.object.custom_meshdata)):
				vn = bpy.context.object.custom_meshdata[j]
				fnormal = vn.fnormal
				
				for k in range(len(vn.vdata)):
					vd = vn.vdata[k]
					tempnorms = []
					v = get_vert_fromloc(verts_list, vd.vpos)

					tempnorms = get_polynormal_forvert(vd.vpos, bpy.context.window_manager.temp_meshdata)
					avg = []

					for i in range(len(tempnorms)):
						if in_angle(Vector(tempnorms[i]), Vector(vd.vnormal), bpy.context.window_manager.vn_anglebased_dot_vert):
							avg += [tempnorms[i]]
					if len(avg) > 0:
						vd.vnormal = get_average(avg).normalized()
					else:
						vd.vnormal = fnormal

	
	me.update()

##
# create new normals list
def reset_normals(self, context):
	me = bpy.context.object.data
	bm = bmesh.from_edit_mesh(me)
	me.update()
	
	faces_list = [f for f in bm.faces]
		
	bpy.context.window_manager.temp_meshdata.clear()
	bpy.context.object.custom_meshdata.clear()
	
	for i in range(len(faces_list)):
		f = faces_list[i]
		tempverts = [v for v in f.verts]
		
		tempfacedata = bpy.context.object.custom_meshdata.add()
		
		tempfacedata.fcenter = f.calc_center_median()
		tempfacedata.fnormal = f.normal
		tempfacedata.vcount = len(tempverts)
		tempfacedata.fsgroup = 1
		
		if 'vdata' not in tempfacedata:
			tempfacedata['vdata'] = []
			
		for j in range(len(tempverts)):
			tempvertdata = tempfacedata.vdata.add()
			tempvertdata.vpos = tempverts[j].co
			tempvertdata.vnormal = tempverts[j].normal

		write_frompoly(tempfacedata.vdata, tempverts)



# Display vertex normals:

# gl line
def draw_line(vertexloc, vertexnorm, color, thickness, dispscale):
	x1 = vertexloc[0]
	y1 = vertexloc[1]
	z1 = vertexloc[2]

	x2 = (vertexnorm[0] * dispscale) + vertexloc[0]
	y2 = (vertexnorm[1] * dispscale) + vertexloc[1]
	z2 = (vertexnorm[2] * dispscale) + vertexloc[2]

	bgl.glLineWidth(thickness)
	bgl.glColor4f(*color)

	# draw line
	bgl.glBegin(bgl.GL_LINES)
	bgl.glVertex3f(x1,y1,z1)
	bgl.glVertex3f(x2,y2,z2)
	bgl.glEnd()

# Draw vertex normals handler
def draw_vertex_normals(self, context):

	if context.mode != "EDIT_MESH" or ('custom_meshdata' not in bpy.context.object):
		return

	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)
	
	dispscale = bpy.context.window_manager.vn_disp_scale
	col = bpy.context.window_manager.vn_displaycolor
	dispcol = (col[0],col[1],col[2],1.0)
	
	selected_list = []
	if bpy.context.window_manager.vndisp_selectiononly:
		#if bpy.context.window_manager.shownormalsbyface:
		selected_list = [f.index for f in bm.faces if f.select]
		#else:
		#	selected_list = [v.co for v in bm.verts if v.select]
	
	normals_list = []
	if bpy.context.window_manager.vndisp_selectiononly:
		#if bpy.context.window_manager.shownormalsbyface:
		for i in selected_list:
			normals_list += [bpy.context.object.custom_meshdata[i]]
		#else:
		#	for vp in selected_list:
		#		normals_list += [get_polynormal_forvert(vp, bpy.context.object.custom_meshdata)]
	else:
		normals_list = [vnf for vnf in bpy.context.object.custom_meshdata]
	
	bgl.glEnable(bgl.GL_BLEND)
	
	for i in range(len(normals_list)):
		#if bpy.context.window_manager.vndisp_selectiononly and not bpy.context.window_manager.shownormalsbyface:
		#	for k in range(len(normals_list[i])):
		#		draw_line(selected_list[i], Vector(normals_list[i][k]), dispcol, 1.5, dispscale)
		#else:
		vdlist = [vd for vd in normals_list[i].vdata]
		for j in range(len(vdlist)):
			draw_line(vdlist[j].vpos, vdlist[j].vnormal, dispcol, 1.5, dispscale)
			
			
	
	bgl.glDisable(bgl.GL_BLEND)


def vn_set_auto(self, context):
	if bpy.context.window_manager.vn_realtimeedit:
		vn_set_manual(self, context)


def vn_set_manual(self, context):
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)

	selected_list = [v.co for v in bm.verts if v.select]

	if len(selected_list) > 0:
		for i in range(len(selected_list)):
			index_list = get_facesforvert(bpy.context.object.custom_meshdata, selected_list[i])
			
			if len(index_list) > 0:
				vertnorm = bpy.context.window_manager.vn_curnormal_disp
				
				if bpy.context.window_manager.vn_changeasone:
					for j in index_list:
						set_vertnormal_byloc(vertnorm, selected_list[i], bpy.context.object.custom_meshdata[j])
				else:
					if bpy.context.window_manager.vn_selected_face < len(index_list):
						set_vertnormal_byloc(vertnorm, selected_list[i], bpy.context.object.custom_meshdata[index_list[bpy.context.window_manager.vn_selected_face]])
				
				
		

# get current normal for manual edit:
def vn_get(self,context):
	me = bpy.context.active_object.data
	bm = bmesh.from_edit_mesh(me)

	vertloc = Vector((0.0,0.0,0.0))
	
	fv = 0
	vertlist = []
	
	faces_list = [f for f in bm.faces]
	
	for i in range(len(faces_list)):
		f = faces_list[i]
		tempverts = f.verts[:]
		for j in range(len(tempverts)):
			v = tempverts[j]
			if v.select:
				vertlist = tempverts
				vertloc = v.co

	showlist = get_polynormal_forvert(vertloc, bpy.context.object.custom_meshdata)
	normcount = len(showlist) - 1
	
	if bpy.context.window_manager.vn_selected_face < normcount:
		fv = bpy.context.window_manager.vn_selected_face
	else:
		fv = normcount
		bpy.context.window_manager.vn_selected_face = normcount
	
	bpy.context.window_manager.vn_curnormal_disp = showlist[fv]


def copy_tempnormalslist(self, context):
	me = bpy.context.active_object.data
	bm = bmesh.from_edit_mesh(me)
	
	me.update()
	
	faceslist = [f for f in bm.faces]
	bpy.context.window_manager.temp_meshdata.clear()
	
	for i in range(len(faceslist)):
		vertlist = [v for v in faceslist[i].verts]
		if len(vertlist) > 0:
			index = find_bycenter(bpy.context.object.custom_meshdata[:], faceslist[i].calc_center_median())
			currentdata = bpy.context.object.custom_meshdata[index]
			
			tempdata = bpy.context.window_manager.temp_meshdata.add()
			
			if 'vdata' not in tempdata:
				tempdata['vdata'] = []
			
			for j in range(len(vertlist)):
				tempv = tempdata.vdata.add()
				if vertlist[j].select:
					tempv.vpos = currentdata.vdata[j].vpos
					tempv.vnormal = currentdata.vdata[j].vnormal
	

def paste_tempnormalslist(self, context):
	me = bpy.context.active_object.data
	bm = bmesh.from_edit_mesh(me)
	
	me.update()
	
	verts_list = [v for v in bm.verts]
	for tempv in verts_list:
		face_indices = get_facesforvert(bpy.context.object.custom_meshdata, tempv.co)
		temp_normals = get_polynormal_forvert(tempv.co, bpy.context.window_manager.temp_meshdata)
		
		for i in range(len(temp_normals)):
			if temp_normals[i] != Vector((0.0,0.0,0.0)):
				set_vertnormal_byloc(temp_normals[i], tempv.co, bpy.context.object.custom_meshdata[face_indices[i]])
		
	bpy.context.window_manager.temp_meshdata.clear()

####################
# Smoothing Groups:


#    draw_smoothing_groups and show_smoothgroups are based on
#    the updated Index Visualiser by Bartius Crouch and CoDEmanX

# Draw smoothing group numbers on faces
groupcolors = [[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0],[1.0,1.0,0.0],[1.0,0.0,1.0],[0.0,1.0,1.0],[0.5,0.0,0.0],[0.0,0.5,0.0],[0.0,0.0,0.5],[0.5,0.5,0.0],[0.0,0.5,0.5],[0.5,0.0,0.5],[0.0,0.0,0.0],[1.0,1.0,1.0],[0.25,0.25,0.25],[0.75,0.75,0.75],[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0],[1.0,1.0,0.0],[1.0,0.0,1.0],[0.0,1.0,1.0],[0.5,0.0,0.0],[0.0,0.5,0.0],[0.0,0.0,0.5],[0.5,0.5,0.0],[0.0,0.5,0.5],[0.5,0.0,0.5],[0.0,0.0,0.0],[1.0,1.0,1.0],[0.25,0.25,0.25],[0.75,0.75,0.75],[0.45,0.25,0.15]]

def draw_smoothing_groups(self, context):
	# polling
	if context.mode != "EDIT_MESH":
		return

	# get screen information
	region = context.region
	mid_x = region.width / 2
	mid_y = region.height / 2
	width = region.width
	height = region.height

	if 'group_colors' not in bpy.context.window_manager:
		bpy.context.window_manager['group_colors'] = []

	if len(bpy.context.window_manager.group_colors) < 33:
		
		for i in range(len(groupcolors)):
			newcol = bpy.context.window_manager.group_colors.add()
			newcol.colval = groupcolors[i]

	# get matrices
	view_mat = context.space_data.region_3d.perspective_matrix
	ob_mat = context.object.matrix_world
	total_mat = view_mat * ob_mat
		
	blf.size(0, 24, 72)
	
	def draw_group(r, g, b, index, center):
		vec = total_mat * center
		# dehomogenise
		vec = Vector((vec[0] / vec[3], vec[1] / vec[3], vec[2] / vec[3]))
		x = int(mid_x + vec[0] * width / 2)
		y = int(mid_y + vec[1] * height / 2)

		bgl.glColor3f(r, g, b)
		blf.position(0, x, y, 0)
		blf.draw(0, str(index))
	
	
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)

	faces_list = [f for f in bm.faces]

	for i in range(len(faces_list)):
		if not faces_list[i].hide:
			if bpy.context.window_manager.sg_showselected:
				if faces_list[i].select:
					#tempcenter = faces_list[i].calc_center_median()
					#index = find_bycenter(bpy.context.object.custom_meshdata, tempcenter)
					#if index > -1:
					curgroup = bpy.context.object.custom_meshdata[i].fsgroup
					curcol = bpy.context.window_manager.group_colors[curgroup].colval
					draw_group(curcol[0], curcol[1], curcol[2], curgroup, faces_list[i].calc_center_median().to_4d())
			else:
				#tempcenter = faces_list[i].calc_center_median()
				#index = find_bycenter(bpy.context.object.custom_meshdata, faces_list[i].calc_center_median())
				#if index > -1:
				curgroup = bpy.context.object.custom_meshdata[i].fsgroup
				curcol = bpy.context.window_manager.group_colors[curgroup].colval
				draw_group(curcol[0], curcol[1], curcol[2], curgroup, faces_list[i].calc_center_median().to_4d())


# set smoothing group for selected faces
def set_sgroup(context, groupnum):
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)

	me.update()
	faces_list = [f for f in bm.faces]

	for i in range(len(faces_list)):
		#index = find_bycenter(bpy.context.object.custom_meshdata[:], faces_list[i].calc_center_median())
		#if index > -1:
		if faces_list[i].select:
			bpy.context.object.custom_meshdata[i].fsgroup = groupnum

#select faces belonging to group
def select_facesingroup(context, groupnum):
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)

	me.update()
	faces_list = [f for f in bm.faces]

	for i in range(len(faces_list)):
		if not faces_list[i].select:
			#index = find_bycenter(bpy.context.object.custom_meshdata[:], faces_list[i].calc_center_median())
			#if index > -1:
			if bpy.context.object.custom_meshdata[i].fsgroup == groupnum:
				faces_list[i].select = True


######################
# Debug:

def debug_getmeshdata(self, me):
	uvtemp = me.tessface_uv_textures[0]
	print("Length of bm.faces: " + str(len(me.tessfaces)))
	print("Length of VN Data:" + str(len(bpy.context.object.custom_meshdata)))
	print(uvtemp.name + ": Length of uv_data: " + str(len(uvtemp.data)))