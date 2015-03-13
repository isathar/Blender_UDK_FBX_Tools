# Helper functions for Normals Editor

import bpy
import bmesh
import bgl
import math
from mathutils import Vector
import sys

from . import normals_data



# Math:
def in_distance(p1, p2, checkdist):
	tempdist = math.sqrt((p1[0] - p2[0]) ** 2) + (((p1[1] - p2[1]) ** 2) + (p1[2] - p2[2]) ** 2)
	return (tempdist < checkdist)

##################
# Editor:

# generate new normals based on preset
def generate_newnormals(self, context):
	genmode = context.window_manager.vn_genmode
	me = context.active_object.data
	bm = bmesh.new()
	
	if context.mode == 'EDIT_MESH':
		bm = bmesh.from_edit_mesh(me)
	else:
		bm.from_mesh(me)
	
	me.update()
	
	faces_list = [f for f in bm.faces]
	verts_list = [v for v in bm.verts]
	
	# DEFAULT: Blender default
	if (genmode == 'DEFAULT'):
		wasobjmode = (context.mode == 'OBJECT')
		
		if wasobjmode:
			bpy.ops.object.mode_set(mode='EDIT')
			bm = bmesh.from_edit_mesh(me)
			me.update()
			faces_list = [f for f in bm.faces]
			verts_list = [v for v in bm.verts]
		
		bpy.ops.mesh.normals_make_consistent()
		
		if context.window_manager.edit_splitnormals:
			normals_data.cust_normals_ppoly.clear()
			for i in range(len(faces_list)):
				faceverts = [v for v in faces_list[i].verts]
				normals_data.cust_normals_ppoly.append([])
				for j in range(len(faceverts)):
					normals_data.cust_normals_ppoly[len(normals_data.cust_normals_ppoly) - 1].append(faceverts[j].normal.copy())
		else:
			normals_data.cust_normals_pvertex.clear()
			for i in range(len(verts_list)):
				normals_data.cust_normals_pvertex.append(verts_list[i].normal.copy())
		
		if wasobjmode:
			bpy.ops.object.mode_set(mode='OBJECT')
	
	# UPVECT: custom direction
	elif (genmode == 'UPVECT'):
		if context.window_manager.edit_splitnormals:
			if context.window_manager.vn_genselectiononly:
				for i in range(len(normals_data.cust_normals_ppoly)):
					for j in range(len(normals_data.cust_normals_ppoly[i])):
						if faces_list[i].verts[j].select:
							normals_data.cust_normals_ppoly[i][j] = Vector(context.window_manager.vn_dirvector)
			else:
				for i in range(len(normals_data.cust_normals_ppoly)):
					for j in range(len(normals_data.cust_normals_ppoly[i])):
						normals_data.cust_normals_ppoly[i][j] = Vector(context.window_manager.vn_dirvector)
		else:
			if context.window_manager.vn_genselectiononly:
				for i in range(len(verts_list)):
					if verts_list[i].select:
						normals_data.cust_normals_pvertex[i] = Vector(context.window_manager.vn_dirvector)
			else:
				for i in range(len(verts_list)):
					normals_data.cust_normals_pvertex[i] = Vector(context.window_manager.vn_dirvector)
	
	# BENT: Bent from point (3D cursor)
	elif (genmode == 'BENT'):
		cursorloc = context.scene.cursor_location
		if context.window_manager.edit_splitnormals:
			if context.window_manager.vn_genselectiononly:
				for i in range(len(normals_data.cust_normals_ppoly)):
					for j in range(len(normals_data.cust_normals_ppoly[i])):
						if not (faces_list[i].hide) and faces_list[i].select:
							tempv = Vector(faces_list[i].verts[j].co) - cursorloc
							tempv = tempv.normalized()
							normals_data.cust_normals_ppoly[i][j] = tempv.copy()
			else:
				for i in range(len(faces_list)):
					for j in range(len(faces_list[i].verts)):
						tempv = Vector(vd.vpos) - cursorloc
						tempv = tempv.normalized()
						normals_data.cust_normals_ppoly[i][j] = tempv.copy()
		else:
			if context.window_manager.vn_genselectiononly:
				for i in range(len(verts_list)):
					if verts_list[i].select:
						tempv = Vector(verts_list[i].co) - cursorloc
						tempv = tempv.normalized()
						tempv = (normals_data.cust_normals_pvertex[i] * (1.0 - context.window_manager.vn_genbendingratio)) + (tempv * (context.window_manager.vn_genbendingratio))
						normals_data.cust_normals_pvertex[i] = tempv
			else:
				for i in range(len(verts_list)):
					tempv = Vector(verts_list[i].co) - cursorloc
					tempv = tempv.normalized()
					tempv = (normals_data.cust_normals_pvertex[i] * (1.0 - context.window_manager.vn_genbendingratio)) + (tempv * (context.window_manager.vn_genbendingratio))
					normals_data.cust_normals_pvertex[i] = tempv
	
	# G_FOLIAGE: combination of bent and up-vector for ground foliage
	elif (genmode == 'G_FOLIAGE'):
		ignorehidden = context.window_manager.vn_genignorehidden
		cursorloc = Vector(context.window_manager.vn_centeroffset)
		if context.window_manager.edit_splitnormals:
			for i in range(len(faces_list)):
				ignoreface = False
				if ignorehidden:
					if faces_list[i].hide:
						ignoreface = True
				for j in range(len(faces_list[i].verts)):
					if faces_list[i].verts[j].select:
						if not ignoreface:
							normals_data.cust_normals_ppoly[i][j] = Vector((0.0,0.0,1.0))
					else:	
						if not ignoreface:
							tempv = faces_list[i].verts[j].co - cursorloc
							normals_data.cust_normals_ppoly[i][j] = tempv.normalized()
		else:
			for i in range(len(verts_list)):
				if ignorehidden:
					if not verts_list[i].hide:
						if verts_list[i].select:
							normals_data.cust_normals_pvertex[i] = Vector((0.0,0.0,1.0))
						else:
							tempv = verts_list[i].co - cursorloc
							normals_data.cust_normals_pvertex[i] = tempv.normalized()
				else:
					if verts_list[i].select:
						normals_data.cust_normals_pvertex[i] = Vector((0.0,0.0,1.0))
					else:
						tempv = verts_list[i].co - cursorloc
						normals_data.cust_normals_pvertex[i] = tempv.normalized()
	
	# CUSTOM: generate for selected faces independently from mesh (or for the whole mesh)
	# - based on existing face nomals, so the mesh requires faces
	# - seems to be weighted by mesh topology when used in poly mode
	#   - number of intersecting edges on connected face influences the direction
	elif (genmode == 'CUSTOM'):
		if context.window_manager.edit_splitnormals:
			for i in range(len(faces_list)):
				f = faces_list[i]
				if context.window_manager.vn_genselectiononly:
					if f.select:
						for j in range(len(f.verts)):
							fncount = 0
							tempfvect = Vector((0.0,0.0,0.0))
							if f.verts[j].select:
								for vf in f.verts[j].link_faces:
									if vf.select:
										fncount += 1
										tempfvect = tempfvect + vf.normal
								if fncount > 0:
									normals_data.cust_normals_ppoly[i][j] = (tempfvect / float(fncount)).normalized()
				else:
					for j in range(len(f.verts)):
						fncount = len(f.verts[j].link_faces)
						tempfvect = Vector((0.0,0.0,0.0))
						for vf in f.verts[j].link_faces:
							tempfvect = tempfvect + vf.normal
						normals_data.cust_normals_ppoly[i][j] = (tempfvect / float(fncount)).normalized()
		else:
			for i in range(len(verts_list)):
				v = verts_list[i]
				if context.window_manager.vn_genselectiononly:
					if v.select:
						fncount = 0
						tempfvect = Vector((0.0,0.0,0.0))
						for j in range(len(v.link_faces)):
							if v.link_faces[j].select:
								fncount += 1
								tempfvect = tempfvect + v.link_faces[j].normal
						if fncount > 0:
							normals_data.cust_normals_pvertex[i] = (tempfvect / float(fncount)).normalized()
				else:
					fncount = len(v.link_faces)
					tempfvect = Vector((0.0,0.0,0.0))
					for j in range(len(v.link_faces)):
						tempfvect = tempfvect + v.link_faces[j].normal
					normals_data.cust_normals_pvertex[i] = (tempfvect / float(fncount)).normalized()
				
	save_normalsdata(context)
	
	if (hasattr(context.active_object.data, "define_normals_split_custom") or not context.window_manager.edit_splitnormals) and context.window_manager.vn_settomeshongen:
		set_meshnormals(context)


# create new normals list
def reset_normals(context):
	me = context.active_object.data
	me.update()
	
	if context.window_manager.edit_splitnormals:
		normals_data.cust_normals_ppoly.clear()
		faces_list = [f for f in me.polygons]
		verts_list = [v.normal for v in me.vertices]
		
		for f in faces_list:
			normals_data.cust_normals_ppoly.append([])
			for j in f.vertices:
				normals_data.cust_normals_ppoly[len(normals_data.cust_normals_ppoly) - 1].append(verts_list[j].copy())
		
		if context.window_manager.convert_splitnormals and len(normals_data.cust_normals_pvertex) > 0:
			convert_pvertextoppoly(context)
		
		normals_data.cust_normals_pvertex.clear()
	else:
		normals_data.cust_normals_pvertex.clear()
		verts_list = [v.normal for v in me.vertices]
		
		for j in range(len(verts_list)):
			normals_data.cust_normals_pvertex.append(verts_list[j].copy())
		
		if context.window_manager.convert_splitnormals and len(normals_data.cust_normals_ppoly) > 0:
			convert_ppolytopvertex(context)
		
		normals_data.cust_normals_ppoly.clear()
	
	save_normalsdata(context)


# load normals from saved data
def load_normalsdata(context):
	if context.window_manager.edit_splitnormals:
		me = context.active_object.data
		if len(context.active_object.polyn_meshdata) == len(me.polygons):
			normals_data.cust_normals_ppoly.clear()
			for f in context.active_object.polyn_meshdata:
				normals_data.cust_normals_ppoly.append([])
				for v in f.vdata:
					normals_data.cust_normals_ppoly[len(normals_data.cust_normals_ppoly) - 1].append(v.vnormal.copy())
	else:
		me = context.active_object.data
		if len(context.active_object.vertexn_meshdata) == len(me.vertices):
			normals_data.cust_normals_pvertex.clear()
			for v in context.active_object.vertexn_meshdata:
				normals_data.cust_normals_pvertex.append(v.vnormal.copy())
	


def save_normalsdata(context):
	if context.window_manager.edit_splitnormals:
		if 'vertexn_meshdata' in context.active_object:
			del context.active_object['vertexn_meshdata']
		if 'polyn_meshdata' not in context.active_object:
			context.active_object['polyn_meshdata'] = []
		context.active_object.polyn_meshdata.clear()
		
		for f in normals_data.cust_normals_ppoly:
			newface = context.active_object.polyn_meshdata.add()
			for v in f:
				newvert = newface.vdata.add()
				newvert.vnormal = v.copy()
	else:
		if 'polyn_meshdata' in context.active_object:
			del context.active_object['polyn_meshdata']
		if 'vertexn_meshdata' not in context.active_object:
			context.active_object['vertexn_meshdata'] = []
		context.active_object.vertexn_meshdata.clear()
		
		for v in normals_data.cust_normals_pvertex:
			newdata = context.active_object.vertexn_meshdata.add()
			newdata.vnormal = v.copy()
	


# converts per poly normals list to per vertex
def convert_ppolytopvertex(context):
	me = context.active_object.data
	#bm = bmesh.from_edit_mesh(me)
	#me.update()
	
	faces_list = [f for f in me.polygons]
	used_indices = []
	for i in range(len(faces_list)):
		for j in range(len(faces_list[i].vertices)):
			if faces_list[i].vertices[j] not in used_indices:
				normals_data.cust_normals_pvertex[faces_list[i].vertices[j]] = normals_data.cust_normals_ppoly[i][j].copy()
				used_indices.append(faces_list[i].vertices[j])
	
	return True


# converts per vertex normals list to per poly
def convert_pvertextoppoly(context):
	me = context.active_object.data
	#bm = bmesh.from_edit_mesh(me)
	#me.update()
	
	faces_list = [f for f in me.polygons]
	for i in range(len(faces_list)):
		for j in range(len(faces_list[i].vertices)):
			normals_data.cust_normals_ppoly[i][j] = normals_data.cust_normals_pvertex[faces_list[i].vertices[j]].copy()
	
	return True


##################################
# Manual edit stuff:

def vn_set_auto(self, context):
	if context.window_manager.vn_realtimeedit:
		vn_set_manual(context)


# set selected vertices' normals to manual edit var
def vn_set_manual(context):
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)
	
	if context.window_manager.edit_splitnormals:
		faces_list = [f for f in bm.faces]
		for i in range(len(faces_list)):
			if faces_list[i].select:
				if context.window_manager.vn_changeasone:
					for j in range(len(faces_list[i].verts)):
						normals_data.cust_normals_ppoly[i][j] = Vector(context.window_manager.vn_curnormal_disp)
				else:
					if context.window_manager.vn_selected_face < len(faces_list[i].verts):
						if faces_list[i].verts[context.window_manager.vn_selected_face].select:
							normals_data.cust_normals_ppoly[i][context.window_manager.vn_selected_face] = Vector(context.window_manager.vn_curnormal_disp)
	else:
		verts_list = [v for v in bm.verts]
		for i in range(len(verts_list)):
			if verts_list[i].select:
				normals_data.cust_normals_pvertex[i] = context.window_manager.vn_curnormal_disp
	save_normalsdata(context)


# get current normal for manual edit (first selected vertex):
def vn_get(context):
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)
	
	if context.window_manager.edit_splitnormals:
		faces_list = [f for f in bm.faces]
		for i in range(len(faces_list)):
			if faces_list[i].select:
				if context.window_manager.vn_selected_face < len(faces_list[i].verts):
					context.window_manager.vn_curnormal_disp = normals_data.cust_normals_ppoly[i][context.window_manager.vn_selected_face]
					break
				else:
					context.window_manager.vn_selected_face = len(faces_list) - 1
					context.window_manager.vn_curnormal_disp = normals_data.cust_normals_ppoly[i][context.window_manager.vn_selected_face]
					break
	else:
		verts_list = [v for v in bm.verts]
		for i in range(len(verts_list)):
			if verts_list[i].select:
				context.window_manager.vn_curnormal_disp = normals_data.cust_normals_pvertex[i]
				break


# bridge to Transfer Vertex Normals addon
def transfer_normals(self, context):
	mod = sys.modules["object_transfervertexnorms"]
	if context.window_manager.normtrans_influence != 0.0:
		if context.window_manager.normtrans_bounds != 'ONLY':
			tempobjstr = context.window_manager.normtrans_sourceobj
			sourceobj = context.scene.objects[tempobjstr]
			if sourceobj != context.active_object:
				mod.transferVertexNormals(self, context, sourceobj,
						[context.active_object],
						context.window_manager.normtrans_influence,
						context.window_manager.normtrans_maxdist,
						context.window_manager.normtrans_bounds)
		else:
			mod.joinBoundaryVertexNormals(self, context, 
						[context.active_object],
						context.window_manager.normtrans_influence,
						context.window_manager.normtrans_maxdist)
	
	normals_data.cust_normals_pvertex.clear()
	me = context.active_object.data
	verts_list = [v.normal for v in me.vertices]
	
	for j in range(len(verts_list)):
		normals_data.cust_normals_pvertex.append(verts_list[j].copy())
	
	save_normalsdata(context)
	set_meshnormals(context)
	


# copy normals from adsn's addon to this one
def copy_fromadsn(context):
	if not context.window_manager.edit_splitnormals:
		if 'vertex_normal_list' in context.active_object:
			me = context.active_object.data
			if len(context.active_object.vertex_normal_list) == len(me.vertices):
				normals_data.cust_normals_pvertex.clear()
				for v in context.active_object.vertex_normal_list:
					normals_data.cust_normals_pvertex.append(Vector(v.normal))
				save_normalsdata(context)
				set_meshnormals(context)
	

##############################
# Display vertex normals:

# draw gl line
def draw_line(vertexloc, vertexnorm, scale):
	bgl.glBegin(bgl.GL_LINES)
	bgl.glVertex3f(vertexloc[0],vertexloc[1],vertexloc[2])
	bgl.glVertex3f(((vertexnorm[0] * scale) + vertexloc[0]),
		((vertexnorm[1] * scale) + vertexloc[1]),
		((vertexnorm[2] * scale) + vertexloc[2]))
	bgl.glEnd()

# Draw vertex normals handler
def draw_vertex_normals(self, context):
	dispcol = context.window_manager.vn_displaycolor
	scale = context.window_manager.vn_disp_scale
	
	bgl.glEnable(bgl.GL_BLEND)
	bgl.glLineWidth(1.5)
	bgl.glColor3f(dispcol[0],dispcol[1],dispcol[2])
	
	if context.window_manager.edit_splitnormals:
		if normals_data.lastdisplaymesh == context.active_object.data.name:
			me = context.active_object.data
			if context.mode == "EDIT_MESH" and context.window_manager.vndisp_selectiononly:
				bm = bmesh.from_edit_mesh(me)
				for i in range(len(bm.faces)):
					if bm.faces[i].select:
						for j in range(len(bm.faces[i].verts)):
							draw_line(bm.faces[i].verts[j].co, normals_data.cust_normals_ppoly[i][j], scale)
			else:
				for i in range(len(me.polygons)):
					for j in range(len(me.polygons[i].vertices)):
						draw_line(me.vertices[me.polygons[i].vertices[j]].co, normals_data.cust_normals_ppoly[i][j], scale)
		else:
			normals_data.lastdisplaymesh = ''
			context.window_manager.showing_vnormals = -1
	else:
		if normals_data.lastdisplaymesh == context.active_object.data.name:
			me = context.active_object.data
			if context.mode == "EDIT_MESH" and context.window_manager.vndisp_selectiononly:
				bm = bmesh.from_edit_mesh(me)
				for i in range(len(normals_data.cust_normals_pvertex)):
					if bm.verts[i].select:
						draw_line(bm.verts[i].co, normals_data.cust_normals_pvertex[i], scale)
			else:
				for i in range(len(normals_data.cust_normals_pvertex)):
					draw_line(me.vertices[i].co, normals_data.cust_normals_pvertex[i], scale)
		else:
			normals_data.lastdisplaymesh = ''
			context.window_manager.showing_vnormals = -1
	
	bgl.glDisable(bgl.GL_BLEND)


# apply normals to mesh (vertex mode only)
def set_meshnormals(context):
	if context.mode == "EDIT_MESH":
		if not context.window_manager.edit_splitnormals:
			if len(normals_data.cust_normals_pvertex) > 0:
				me = context.active_object.data
				bm = bmesh.from_edit_mesh(me)
				for i in range(len(bm.verts)):
					bm.verts[i].normal = normals_data.cust_normals_pvertex[i]
				context.area.tag_redraw()
	elif context.mode == "OBJECT":
		if hasattr(context.active_object.data, "define_normals_split_custom"):
			me = context.active_object.data
			me.create_normals_split()
			me.validate()
			if not context.window_manager.edit_splitnormals:
				normalslist = tuple(tuple(v) for v in normals_data.cust_normals_pvertex)
				me.use_auto_smooth = True
				me.free_normals_split()
				me.define_normals_split_custom_from_vertices(normalslist)
			else:
				normalslist = ()
				for f in normals_data.cust_normals_ppoly:
					normalslist = normalslist + tuple(tuple(l) for l in f)
				me.use_auto_smooth = True
				me.free_normals_split()
				me.define_normals_split_custom(normalslist)
		else:
			if not context.window_manager.edit_splitnormals:
				if len(normals_data.cust_normals_pvertex) > 0:
					me = context.active_object.data
					for i in range(len(me.vertices)):
						me.vertices[i].normal = normals_data.cust_normals_pvertex[i]
					context.area.tag_redraw()


def cleanup_datavars():
	normals_data.clear_normalsdata()

