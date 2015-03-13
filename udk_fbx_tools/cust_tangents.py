# Old custom tangents
#
# - separate from the exporter since it's not needed for newer builds
# - kept for backwards compatibility + surprise that it worked
#
#
# Based on:
# Lengyel, Eric. “Computing Tangent Space Basis Vectors for an Arbitrary Mesh”. Terathon Software 3D Graphics Library, 2001. 
# http://www.terathon.com/code/tangent.html
#

import math
from mathutils import Vector


'''		Calculate uv direction for tangent space:
    - tris required (kind of... half of each face is not considered in
		calculation if using quads but tangents are ok if engine triangulation is close enough)
    - uvs must be properly mapped to vertices
'''
def calc_uvtanbase(uvpoly, polyverts):
	# get uv distances
	uv_dBA = uvpoly[1] - uvpoly[0]
	uv_dCA = uvpoly[2] - uvpoly[0]
	# get point distances
	p_dBA = polyverts[1] - polyverts[0]
	p_dCA = polyverts[2] - polyverts[0]
	# calculate face area
	area = (uv_dBA[0] * uv_dCA[1]) - (uv_dBA[1] * uv_dCA[0])
	if area > 0.0:
		area = 1.0 / area
	tangentdir = (
		((uv_dCA[1] * p_dBA[0]) - (uv_dBA[1] * p_dCA[0])) * area,
		((uv_dCA[1] * p_dBA[1]) - (uv_dBA[1] * p_dCA[1])) * area,
		((uv_dCA[1] * p_dBA[2]) - (uv_dBA[1] * p_dCA[2])) * area
	)
	return tangentdir


def build_initialtanlists(me_faces, me_vertices, t_uvlayer, me_normals):
	vindices = []
	vindexlist2 = []
	uvverts_list = []
	uv_vertcoords = []
	
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
			uvverts_list.append(
				Vector(calc_uvtanbase(uvface, faceverts))
			)
	
	# check if tangents are valid
	if len(uvverts_list) != len(me_normals):
		operator.report(
			{'WARNING'}, 
			"UV list length mismatch: Tangents will not be calculated."
		)
	else :
		# Calculate tangents/binormals from normals list and uvverts_list
		return calc_custtangents(
			len(me_vertices), uv_vertcoords, uvverts_list, 
			vindexlist2, vindices, me_normals
		)
	
	return [], []


def check_uvvertdist(coord1, coord2, length):
	return math.sqrt(((coord1[0] - coord2[0]) ** 2) + ((coord1[1] - coord2[1]) ** 2)) < 0.01


'''			Tangent Smoothing
	- averages the tangents for each vert connected to a smoothed face to remove 'jittering'
	- smoothing is based on uv islands each vert's faces are in
'''
def calc_custtangents(vertlength, uv_vertcoords, uvverts_list, vindexlist2, vindices, me_normals):
	me_tangents = []
	me_binormals = []
	
	for i in range(len(me_normals)):
		tan = (uvverts_list[i] - (
			me_normals[i] * me_normals[i].dot(uvverts_list[i])
		)).normalized()
		me_tangents.append(tan)
		me_binormals.append(me_normals[i].cross(tan))
	
	tempvect = Vector((0.0,0.0,0.0))
	smoothlist = [[],[],[],[]]
	vertstoremove = []
	new_tangents = [v for v in me_tangents]
	
	for i in range(vertlength):
		# Gather Loop
		# - slow - checks the index list for uv islands each vert is part of
		for j in vindexlist2:
			if vindices[j] == i:
				vertstoremove.append(j)
				if len(smoothlist[0]) > 0:
					if check_uvvertdist(uv_vertcoords[j], uv_vertcoords[smoothlist[0][0]], 0.01):
						smoothlist[0].append(j)
					else:
						if len(smoothlist[1]) > 0:
							if check_uvvertdist(uv_vertcoords[j], uv_vertcoords[smoothlist[1][0]], 0.01):
								smoothlist[1].append(j)
							else:
								if len(smoothlist[2]) > 0:
									if check_uvvertdist(uv_vertcoords[j], uv_vertcoords[smoothlist[2][0]], 0.01):
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
		
		# actual smoothing is done here:
		smooth_vertcusttangents(tempvect, smoothlist, me_normals, me_tangents, me_binormals, new_tangents)
		
		# reset vars for next iteration
		smoothlist = [[],[],[],[]]
		vertstoremove = []
		tempvect.zero()
	
	me_tangents = [v for v in new_tangents]
	
	return me_tangents, me_binormals


'''
		Smoothing pass for each vert
	- averages the tangents of vertices that are on the same uv island
	- 4 uv islands / vertex max, anything else gets averaged into fourth island for now
'''
def smooth_vertcusttangents(tempvect, smoothlist, me_normals, me_tangents, me_binormals, new_tangents):
	if len(smoothlist[0]) > 0:
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
	
