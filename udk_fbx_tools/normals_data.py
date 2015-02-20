############################################################
# variables for faster access to normals data in the editor
#
lastdisplaymesh = ''

cust_normals_ppoly = []
cust_normals_pvertex = []

def clear_normalsdata():
	del cust_normals_ppoly[:]
	del cust_normals_pvertex[:]
