# Helper functions for FBX Tools

import bpy
import bmesh
import bgl
import math
from mathutils import Vector

# Math:
def in_distance(p1, p2, checkdist):
	tempdist = math.sqrt((p1[0] - p2[0]) ** 2) + (((p1[1] - p2[1]) ** 2) + (p1[2] - p2[2]) ** 2)
	return (tempdist < checkdist)

##################
# Editor:

# generate new normals based on preset
def generate_newnormals(self, context):
	genmode = context.window_manager.vn_generatemode
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)
	me.update()
	
	faces_list = [f for f in bm.faces]
	verts_list = [v for v in bm.verts]
	
	# DEFAULT: Blender default
	if (genmode == 'DEFAULT'):
		bpy.ops.mesh.normals_make_consistent()
		me.update()
		
		if context.window_manager.edit_splitnormals:
			for i in range(len(faces_list)):
				faceverts = [v for v in faces_list[i].verts]
				tempfacedata = context.active_object.polyn_meshdata[i]
				
				for j in range(len(faceverts)):
					tempfacedata.vdata[j].vnormal = faceverts[j].normal
					tempfacedata.vdata[j].vpos = faceverts[j].co
		else:
			for i in range(len(verts_list)):
				tempV = context.active_object.vertexn_meshdata[i]
				tempV.vpos = verts_list[i].co
				tempV.vnormal = verts_list[i].normal
	
	# UPVECT: custom direction
	elif (genmode == 'UPVECT'):
		if context.window_manager.edit_splitnormals:
			if context.window_manager.vn_genselectiononly:
				for i in range(len(context.active_object.polyn_meshdata)):
					for j in range(len(context.active_object.polyn_meshdata[i].vdata)):
						if faces_list[i].verts[j].select:
							context.active_object.polyn_meshdata[i].vdata[j].vnormal = context.window_manager.vn_directionalvector
			else:
				for i in range(len(context.active_object.polyn_meshdata)):
					for j in range(len(context.active_object.polyn_meshdata[i].vdata)):
						context.active_object.polyn_meshdata[i].vdata[j].vnormal = context.window_manager.vn_directionalvector
		else:
			if context.window_manager.vn_genselectiononly:
				for i in range(len(verts_list)):
					if verts_list[i].select:
						context.active_object.vertexn_meshdata[i].vnormal = context.window_manager.vn_directionalvector
			else:
				for i in range(len(verts_list)):
					context.active_object.vertexn_meshdata[i].vnormal = context.window_manager.vn_directionalvector
	
	# BENT: Bent from point (3D cursor)
	elif (genmode == 'BENT'):
		cursorloc = context.scene.cursor_location
		if context.window_manager.edit_splitnormals:
			if context.window_manager.vn_genselectiononly:
				for i in range(len(context.active_object.polyn_meshdata)):
					for j in range(len(context.active_object.polyn_meshdata[i].vdata)):
						if not (faces_list[i].hide) and faces_list[i].select:
							tempv = Vector(context.active_object.polyn_meshdata[i].vdata[j].vpos) - cursorloc
							tempv = tempv.normalized()
							context.active_object.polyn_meshdata[i].vdata[j].vnormal = tempv
			else:
				for vn in context.active_object.polyn_meshdata:
					for vd in vn.vdata:
						tempv = Vector(vd.vpos) - cursorloc
						tempv = tempv.normalized()
						vd.vnormal = tempv
		else:
			if context.window_manager.vn_genselectiononly:
				for i in range(len(verts_list)):
					if verts_list[i].select:
						tempv = Vector(verts_list[i].co) - cursorloc
						tempv = tempv.normalized()
						tempv = (Vector(context.active_object.vertexn_meshdata[i].vnormal) * (1.0 - context.window_manager.vn_genbendingratio)) + (tempv * (context.window_manager.vn_genbendingratio))
						context.active_object.vertexn_meshdata[i].vnormal = tempv
			else:
				for i in range(len(verts_list)):
					tempv = Vector(verts_list[i].co) - cursorloc
					tempv = tempv.normalized()
					tempv = (Vector(context.active_object.vertexn_meshdata[i].vnormal) * (1.0 - context.window_manager.vn_genbendingratio)) + (tempv * (context.window_manager.vn_genbendingratio))
					context.active_object.vertexn_meshdata[i].vnormal = tempv
	
	# G_FOLIAGE: combination of bent and up-vector for ground foliage
	elif (genmode == 'G_FOLIAGE'):
		ignorehidden = context.window_manager.vn_genignorehidden
		cursorloc = Vector(context.window_manager.vn_centeroffset)
		if context.window_manager.edit_splitnormals:
			for i in range(len(context.active_object.polyn_meshdata)):
				ignoreface = False
				if ignorehidden:
					if faces_list[i].hide:
						ignoreface = True
				for j in range(len(context.active_object.polyn_meshdata[i].vdata)):
					if faces_list[i].verts[j].select:
						if not ignoreface:
							context.active_object.polyn_meshdata[i].vdata[j].vnormal = (0.0,0.0,1.0)
					else:	
						if not ignoreface:
							tempv = Vector(context.active_object.polyn_meshdata[i].vdata[j].vpos) - cursorloc
							context.active_object.polyn_meshdata[i].vdata[j].vnormal = tempv.normalized()
		else:
			for i in range(len(verts_list)):
				if ignorehidden:
					if not verts_list[i].hide:
						if verts_list[i].select:
							context.active_object.vertexn_meshdata[i].vnormal = (0.0,0.0,1.0)
						else:
							tempv = Vector(context.active_object.vertexn_meshdata[i].vpos) - cursorloc
							context.active_object.vertexn_meshdata[i].vnormal = tempv.normalized()
				else:
					if verts_list[i].select:
						context.active_object.vertexn_meshdata[i].vnormal = (0.0,0.0,1.0)
					else:
						tempv = Vector(context.active_object.vertexn_meshdata[i].vpos) - cursorloc
						context.active_object.vertexn_meshdata[i].vnormal = tempv.normalized()
	
	# CUSTOM: generate for selected faces independently from mesh (or for the whole mesh)
	elif (genmode == 'CUSTOM'):
		if context.window_manager.edit_splitnormals:
			for i in range(len(context.active_object.polyn_meshdata)):
				tempface = context.active_object.polyn_meshdata[i]
				f = faces_list[i]
				if context.window_manager.vn_genselectiononly:
					if f.select:
						for j in range(len(tempface.vdata)):
							fncount = 0
							tempfvect = Vector((0.0,0.0,0.0))
							if f.verts[j].select:
								for vf in f.verts[j].link_faces:
									if vf.select:
										fncount += 1
										tempfvect = tempfvect + vf.normal
								if fncount > 0:
									tempface.vdata[j].vnormal = (tempfvect / float(fncount)).normalized()
				else:
					for j in range(len(tempface.vdata)):
						fncount = len(f.verts[j].link_faces)
						tempfvect = Vector((0.0,0.0,0.0))
						for vf in f.verts[j].link_faces:
							if vf.select:
								tempfvect = tempfvect + vf.normal
						tempface.vdata[j].vnormal = (tempfvect / float(fncount)).normalized()
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
							context.active_object.vertexn_meshdata[i].vnormal = (tempfvect / float(fncount)).normalized()
				else:
					fncount = len(v.link_faces)
					tempfvect = Vector((0.0,0.0,0.0))
					for j in range(len(v.link_faces)):
						tempfvect = tempfvect + v.link_faces[j].normal
					context.active_object.vertexn_meshdata[i].vnormal = (tempfvect / float(fncount)).normalized()
	
	
	if (not context.window_manager.edit_splitnormals) and context.window_manager.vn_settomeshongen:
		set_meshnormals(context)


# create new normals list
def reset_normals(context):
	me = context.active_object.data
	
	context.window_manager.temp_copypastelist.clear()
	if context.window_manager.edit_splitnormals:
		context.active_object.polyn_meshdata.clear()
		
		faces_list = [f for f in me.polygons]
		verts_list = [[v.co, v.normal] for v in me.vertices]
		
		for f in faces_list:
			tempfacedata = context.active_object.polyn_meshdata.add()
			if 'vdata' not in tempfacedata:
				tempfacedata['vdata'] = []
			
			tempverts = [v for v in f.vertices]
			for j in tempverts:
				tempvertdata = tempfacedata.vdata.add()
				tempvertdata.vpos = verts_list[j][0]
				tempvertdata.vnormal = verts_list[j][1]
		
		if context.window_manager.convert_splitnormals and 'vertexn_meshdata' in context.active_object:
			convert_pvertextoppoly(context)
		
		context.active_object.vertexn_meshdata.clear()
	else:
		verts_list = [[v.co, v.normal] for v in me.vertices]
		
		context.active_object.vertexn_meshdata.clear()
		
		for v in verts_list:
			tempvdata = context.active_object.vertexn_meshdata.add()
			tempvdata.vpos = v[0]
			tempvdata.vnormal = v[1]
		
		if context.window_manager.convert_splitnormals and 'polyn_meshdata' in context.active_object:
			convert_ppolytopvertex(context)
		context.active_object.polyn_meshdata.clear()


# converts per poly normals list to per vertex
def convert_ppolytopvertex(context):
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)
	me.update()
	
	faces_list = [f for f in bm.faces]
	used_indices = []
	for i in range(len(faces_list)):
		for j in range(len(faces_list[i].verts)):
			if faces_list[i].verts[j].index not in used_indices:
				context.active_object.vertexn_meshdata[faces_list[i].verts[j].index].vnormal = context.active_object.polyn_meshdata[i].vdata[j].vnormal
				used_indices.append(faces_list[i].verts[j].index)
	
	return True


# converts per vertex normals list to per poly
def convert_pvertextoppoly(context):
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)
	me.update()
	
	faces_list = [f for f in bm.faces]
	for i in range(len(faces_list)):
		for j in range(len(faces_list[i].verts)):
			context.active_object.polyn_meshdata[i].vdata[j].vnormal = context.active_object.vertexn_meshdata[faces_list[i].verts[j].index].vnormal
	
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
						context.active_object.polyn_meshdata[i].vdata[j].vnormal = context.window_manager.vn_curnormal_disp
				else:
					if context.window_manager.vn_selected_face < len(faces_list[i].verts):
						if faces_list[i].verts[context.window_manager.vn_selected_face].select:
							context.active_object.polyn_meshdata[i].vdata[context.window_manager.vn_selected_face].vnormal = context.window_manager.vn_curnormal_disp
	else:
		verts_list = [v for v in bm.verts]
		for i in range(len(verts_list)):
			if verts_list[i].select:
				context.active_object.vertexn_meshdata[i].vnormal = context.window_manager.vn_curnormal_disp


# get current normal for manual edit (first selected vertex):
def vn_get(context):
	me = context.active_object.data
	bm = bmesh.from_edit_mesh(me)
	
	if context.window_manager.edit_splitnormals:
		faces_list = [f for f in bm.faces]
		for i in range(len(faces_list)):
			if faces_list[i].select:
				if context.window_manager.vn_selected_face < len(faces_list[i].verts):
					context.window_manager.vn_curnormal_disp = context.active_object.polyn_meshdata[i].vdata[context.window_manager.vn_selected_face].vnormal
					break
				else:
					context.window_manager.vn_selected_face = len(faces_list) - 1
					context.window_manager.vn_curnormal_disp = context.active_object.polyn_meshdata[i].vdata[context.window_manager.vn_selected_face].vnormal
					break
	else:
		verts_list = [v for v in bm.verts]
		for i in range(len(verts_list)):
			if verts_list[i].select:
				context.window_manager.vn_curnormal_disp = context.active_object.vertexn_meshdata[i].vnormal
				break


##############################
# Display vertex normals:

# draw gl line
def draw_line(vertexloc, vertexnorm, scale):
	x2 = (vertexnorm[0] * scale) + vertexloc[0]
	y2 = (vertexnorm[1] * scale) + vertexloc[1]
	z2 = (vertexnorm[2] * scale) + vertexloc[2]
	bgl.glBegin(bgl.GL_LINES)
	bgl.glVertex3f(vertexloc[0],vertexloc[1],vertexloc[2])
	bgl.glVertex3f(x2,y2,z2)
	bgl.glEnd()

# Draw vertex normals handler
def draw_vertex_normals(self, context):
	if context.mode != "EDIT_MESH":
		return
	
	dispcol = context.window_manager.vn_displaycolor
	scale = context.window_manager.vn_disp_scale
	
	bgl.glEnable(bgl.GL_BLEND)
	bgl.glLineWidth(1.5)
	bgl.glColor3f(dispcol[0],dispcol[1],dispcol[2])
	
	if context.window_manager.edit_splitnormals:
		if 'polyn_meshdata' in context.active_object:
			if context.window_manager.vndisp_selectiononly:
				me = context.active_object.data
				bm = bmesh.from_edit_mesh(me)
				
				fcount = 0
				for m in context.active_object.polyn_meshdata:
					if bm.faces[fcount].select:
						[draw_line(v.vpos, v.vnormal, scale) for v in m.vdata]
					fcount += 1
			else:
				for m in context.active_object.polyn_meshdata:
					[draw_line(v.vpos, v.vnormal, scale) for v in m.vdata]
	else:
		if context.window_manager.vndisp_selectiononly:
			me = context.active_object.data
			bm = bmesh.from_edit_mesh(me)
			
			vcount = 0
			for v in context.active_object.vertexn_meshdata:
				if bm.verts[vcount].select:
					draw_line(v.vpos, v.vnormal, scale)
				vcount += 1
		else:
			for v in context.active_object.vertexn_meshdata:
				draw_line(v.vpos, v.vnormal, scale)
	
	bgl.glDisable(bgl.GL_BLEND)


# apply normals to mesh (vertex mode only)
def set_meshnormals(context):
	if not context.window_manager.edit_splitnormals:
		if 'vertexn_meshdata' in context.active_object:
			me = context.active_object.data
			bm = bmesh.from_edit_mesh(me)
			me.update()
			
			#bm.verts.ensure_lookup_table()
			for i in range(len(bm.verts)):
				bm.verts[i].normal = context.active_object.vertexn_meshdata[i].vnormal
