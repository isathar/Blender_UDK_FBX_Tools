###############################
# Index for exported data
#
# - handles Object -> Number conversions for FBX 7.3
# - system has room for 9999 of each object type.... should be enough
'''
	Numbering:
	
	0 			= RootNode
	10 			= Document
	100 		= Pose
	
	10xxxx 		= Geometry
	11xxxx		= ShapeGeometry
	20xxxx 		= Mesh
	30xxxx 		= Mesh::LimbNode/Root
	31xxxx 		= Attribute::LimbNode/Root
	
	40xxxx 		= Material
	41xxxx 		= Texture
	42xxxx 		= Video
	
	50xxxx 		= Skin
	51xxxx 		= Cluster
	60xxxx		= Shape
	61xxxx		= ShapeChannel
'''


# index vars
index_fbxModels = []
index_fbxBones = []

index_fbxMaterials = []
index_fbxTextures = []

index_fbxSkins = []
index_fbxClusters = []

index_fbxShapeGeom = []
index_fbxShapes = []
index_fbxShapeChannels = []


# getters for id codes used to identify objects:
def get_fbx_GeomID(obname):
	for i in range(len(index_fbxModels)):
		if obname == index_fbxModels[i]:
			return 100000 + i
	return 0

def get_fbx_ShapeGeomID(obname):
	for i in range(len(index_fbxModels)):
		if obname == index_fbxModels[i]:
			return 110000 + i
	return 0

def get_fbx_MeshID(obname):
	for i in range(len(index_fbxModels)):
		if obname == index_fbxModels[i]:
			return 200000 + i
	return 0

def get_fbx_BoneID(inbone):
	for i in range(len(index_fbxBones)):
		if inbone == index_fbxBones[i]:
			return 300000 + i
	return 0

def get_fbx_BoneAttributeID(inbone):
	for i in range(len(index_fbxBones)):
		if inbone == index_fbxBones[i]:
			return 310000 + i
	return 0

def get_fbx_DeformerSkinID(instring):
	for i in range(len(index_fbxSkins)):
		if instring == index_fbxSkins[i]:
			return 500000 + i
	return 0

def get_fbx_DeformerClusterID(instring):
	for i in range(len(index_fbxClusters)):
		if instring == index_fbxClusters[i]:
			return 510000 + i
	return 0

def get_fbx_MaterialID(mat):
	for i in range(len(index_fbxMaterials)):
		if mat == index_fbxMaterials[i]:
			return 400000 + i
	return 0

def get_fbx_TextureID(texname):
	for i in range(len(index_fbxTextures)):
		if texname == index_fbxTextures[i]:
			return 410000 + i
	return 0

def get_fbx_VideoID(texname):
	for i in range(len(index_fbxTextures)):
		if texname == index_fbxTextures[i]:
			return 420000 + i
	return 0
