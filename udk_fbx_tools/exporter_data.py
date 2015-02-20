###############################
# Index for exported data
#
# - handles Object -> Number conversions for FBX 7.3
# - system has room for 9999 of each object type.... should be enough
'''
	Numbering:
	# static:
	0 			= RootNode
	10 			= Document
	100 		= Pose
	
	# objects:
	10xxxx 		= Geometry
	11xxxx		= ShapeGeometry
	20xxxx 		= Mesh
	22xxxx		= Model::Null
	30xxxx 		= Mesh::LimbNode/Root
	31xxxx 		= NodeAttribute::LimbNode/Root
	32xxxx		= NodeAttribute::Null
	
	40xxxx 		= Material
	41xxxx 		= Texture
	42xxxx 		= Video
	
	# skins/shapes
	50xxxx 		= Skin
	51xxxx 		= Cluster
	60xxxx		= Shape
	61xxxx		= ShapeChannel
	
	#animations:
	800000		= AnimationStack
	810000		= AnimationLayer
	
	# animation curve data may need a bigger index 
	# - thanks to every vector component curve needing its own unique id :(
	1000000		= AnimationCurveNode
	2000000		= AnimationCurve
'''


# index vars
index_fbxModels = []
index_fbxBones = []

index_fbxNulls = []

index_fbxMaterials = []
index_fbxTextures = []

# not sure about this
# - some files include the skeleton as a null object, 
# but it doesn't seem to affect anything
#index_fbxSkeletons = []

index_fbxSkins = []
index_fbxClusters = []

index_fbxShapeGeom = []
index_fbxShapes = []
index_fbxShapeChannels = []

#animations
index_fbxAnimStacks = []
index_fbxAnimLayers = []
index_fbxAnimCurveNodes = []
index_fbxAnimCurves = []


# moved other exporter data since it was already global 

fbx_meshes = []#ob_meshes
fbx_bones = []#ob_bones
fbx_nulls = []#ob_nulls

fbx_poses = []#pose_items

fbx_actions = []#temp_actions
fbx_taggedactions = []#tagged_actions

ob_anim_lists = []#


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
	
def get_fbx_NullModelID(innull):
	for i in range(len(index_fbxNulls)):
		if innull == index_fbxNulls[i]:
			return 220000 + i
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
	
def get_fbx_NullAttributeID(innull):
	for i in range(len(index_fbxNulls)):
		if innull == index_fbxNulls[i]:
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

def get_fbx_AnimStackID(animname):
	for i in range(len(index_fbxAnimStacks)):
		if animname == index_fbxAnimStacks[i]:
			return 800000 + i
	return 0

def get_fbx_AnimLayerID(animname):
	for i in range(len(index_fbxAnimStacks)):
		if animname == index_fbxAnimStacks[i]:
			return 810000 + i
	return 0

def get_fbx_AnimCurveNodeID(animname):
	for i in range(len(index_fbxAnimCurveNodes)):
		if animname == index_fbxAnimCurveNodes[i]:
			return 1000000 + i
	return 0

def get_fbx_AnimCurveID(animname):
	for i in range(len(index_fbxAnimCurves)):
		if animname == index_fbxAnimCurves[i]:
			return 2000000 + i
	return 0


def clear_fbxData():
	print("Exporter: Deleting temp files....")
	
	del index_fbxModels[:]
	del index_fbxBones[:]
	del index_fbxNulls[:]
	del index_fbxMaterials[:]
	del index_fbxTextures[:]
	del index_fbxSkins[:]
	del index_fbxClusters[:]
	del index_fbxShapeGeom[:]
	del index_fbxShapes[:]
	del index_fbxShapeChannels[:]
	del index_fbxAnimStacks[:]
	del index_fbxAnimCurveNodes[:]
	del index_fbxAnimCurves[:]
	
	del fbx_meshes[:]
	del fbx_bones[:]
	del fbx_nulls[:]
	del fbx_poses[:]
	del fbx_actions[:]
	del fbx_taggedactions[:]
	

