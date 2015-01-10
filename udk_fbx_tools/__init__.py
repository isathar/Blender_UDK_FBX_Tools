bl_info = {
	"name": "UE FBX Normals Tools",
	"author": "Andreas Wiehn (isathar)",
	"version": (0, 10, 1),
	"blender": (2, 70, 0),
	"location": "View3D > Toolbar",
	"description": "Adds an editor for vertex normals and an exporter "
					"with some Unreal Engine-specific optimizations. "
					" Also supports tangent and binormal calculation/export for UDK. "
					"",
	"warning": "",
	"wiki_url": "",
	"tracker_url": "https://github.com/isathar/Blender_UDK_FBX_Tools/issues/",
	"category": "Mesh"}


import bpy
from bpy.types import Panel

from . import export_menu
from . import editorfunctions
from . import import_normals


#########################
# Main Menu

# UI Panel
class fbxtools_panel(bpy.types.Panel):
	bl_idname = "object.fbxtools_panel"
	bl_label = 'UDK FBX Tools'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = "FBX Tools"
	
	def __init__(self):
		pass
	
	@classmethod
	def poll(self, context):
		return context.active_object != None
	
	def draw(self, context):
		layout = self.layout
		if context.active_object != None:
			if context.active_object.type == 'MESH':
				box = layout.box()
				row = box.row()
				row.operator('export_scene.fbx_custom', text='Export')
				if context.window_manager.edit_splitnormals:
					row = box.row()
					row.operator('object.import_customnormals', text='Import Normals')
				box = layout.box()
				label = box.label("  Mesh Data:", 'NONE')
				row = box.row()
				if (context.window_manager.edit_splitnormals and 'polyn_meshdata' in context.active_object) or (not context.window_manager.edit_splitnormals and 'vertexn_meshdata' in context.active_object):
					row.operator('object.reset_polydata', text='Reset')
					row.operator('object.clear_polydata', text='Clear')
				else:
					row.operator('object.reset_polydata', text='Initialize')
			else:
				row = layout.row()
				label = row.label("Object needs to be a mesh", 'NONE')
		else:
			row = layout.row()
			label = row.label("No object selected", 'NONE')


class reset_polydata(bpy.types.Operator):
	bl_idname = 'object.reset_polydata'
	bl_label = 'Create Mesh Data'
	bl_description = 'Recreate mesh data struct'
	
	@classmethod
	def poll(cls, context):
		return context.active_object != None and context.active_object.type == 'MESH'
	
	def execute(self, context):
		if 'polyn_meshdata' not in context.active_object:
			context.active_object['polyn_meshdata'] = []
		if 'vertexn_meshdata' not in context.active_object:
			context.active_object['vertexn_meshdata'] = []
		if 'temp_copypastelist' not in bpy.context.window_manager:
			context.window_manager['temp_copypastelist'] = []
		
		if context.mode != "EDIT_MESH":
			bpy.ops.object.mode_set(mode='EDIT')
		
		editorfunctions.reset_normals(context)
		
		return {'FINISHED'}


class clear_polydata(bpy.types.Operator):
	bl_idname = 'object.clear_polydata'
	bl_label = 'Delete Mesh Data'
	bl_description = 'Delete mesh data struct'
	
	@classmethod
	def poll(cls, context):
		if context.window_manager.edit_splitnormals and 'polyn_meshdata' in context.active_object:
			return True
		elif not context.window_manager.edit_splitnormals and 'vertexn_meshdata' in context.active_object:
			return True
		else:
			return False
	
	def execute(self, context):
		if 'showing_vnormals' in context.window_manager:
			context.window_manager.showing_vnormals = -1
		if 'polyn_meshdata' in context.active_object:
			del context.active_object['polyn_meshdata']
		if 'vertexn_meshdata' in context.active_object:
			del context.active_object['vertexn_meshdata']
		if 'temp_copypastelist' in bpy.context.window_manager:
			del context.window_manager['temp_copypastelist']
		return {'FINISHED'}


##########################
# Vertex Normals Editor:

# UI Panel
class vertex_normals_panel(bpy.types.Panel):
	bl_idname = "object.vertex_normals_panel"
	bl_label = ' Normals Editor'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = "FBX Tools"
	
	@classmethod
	def poll(self, context):
		return context.active_object != None and context.active_object.type == 'MESH'
	
	def draw(self, context):
		layout = self.layout
		
		row = layout.row()
		if 'polyn_meshdata' not in context.active_object and 'vertexn_meshdata' not in context.active_object:
			label = row.label("No vertex data", 'NONE')
		else:
			if context.mode != "EDIT_MESH":
				label = row.label("Edit Mode required", 'NONE')
			else:
				row.operator('object.display_normalsonmesh', text='Apply to Mesh')
				box = layout.box()
				if context.window_manager.edit_splitnormals:
					label = box.label(" Mode: Per Poly", 'NONE')
				else:
					label = box.label(" Mode: Per Vertex", 'NONE')
				row = box.row()
				row.operator('object.switch_normalsmode', text='Switch Mode')
				row = box.row()
				row.prop(context.window_manager, 'convert_splitnormals', text='Convert on Switch')
				
				# Auto Generation
				box = layout.box()
				label = box.label(" Auto Generation:", 'NONE')
				box2 = box.box()
				row = box2.row()
				row.prop(context.window_manager, 'vn_generatemode', text='')
				row = box2.row()
				row.operator('object.generate_vnormals', text='Generate')
				row = box2.row()
				row.prop(context.window_manager, 'vn_resetongenerate', text='Reset First')
				
				if context.window_manager.vn_generatemode != 'G_FOLIAGE':
					if context.window_manager.vn_generatemode != 'DEFAULT':
						row = box2.row()
						row.prop(context.window_manager, 'vn_genselectiononly', text='Selected Only')
				else:
					row = box2.row()
					row.column().prop(context.window_manager, 'vn_centeroffset', text='Center Offset')
					row = box2.row()
					row.prop(context.window_manager, 'vn_genignorehidden', text='Ignore Hidden')
				
				if context.window_manager.vn_generatemode == 'UPVECT':
					row = box2.row()
					label = row.label("Direction:", 'NONE')
					row = box2.row()
					row.column().prop(context.window_manager, 'vn_directionalvector', text='')
				
				if context.window_manager.vn_generatemode == 'POINT':
					row = box2.row()
					row.column().prop(context.window_manager, 'vn_genbendingratio', text='Bend Ratio')
				
				if not context.window_manager.edit_splitnormals:
					row = box2.row()
					row.column().prop(context.window_manager, 'vn_settomeshongen', text='Set to Mesh')
				
				# Manual edit
				box = layout.box()
				label = box.label(" Manual Edit:", 'NONE')
				box2 = box.box()
				row = box2.row()
				row.column().prop(context.window_manager, 'vn_curnormal_disp', text='')
				if context.window_manager.edit_splitnormals:
					row = box2.row()
					row.prop(context.window_manager, 'vn_selected_face', text='Vert Index')
				row = box2.row()
				row.operator('object.get_vnormal', text='Show')
				row.operator('object.set_vnormal', text='Set')
				
				row = box2.row()
				row.prop(context.window_manager, 'vn_realtimeedit', text='Real-Time')
				if context.window_manager.edit_splitnormals:
					row = box2.row()
					row.prop(context.window_manager, 'vn_changeasone', text='Edit All')
				
				# copy/paste
				box = layout.box()
				label = box.label("Transfer Normals:", 'NONE')
				row = box.row()
				row.operator('object.copy_selectednormals', text='Copy')
				row.operator('object.paste_selectednormals', text='Paste')
				
				# Display
				box = layout.box()
				label = box.label(" Display:", 'NONE')
				row = box.row()
				if context.window_manager.showing_vnormals < 1:
					row.operator('view3d.show_vertexnormals', text='Show Normals')
				else:
					row.operator('view3d.show_vertexnormals', text='Hide Normals')
					row = box.row()
					row.prop(context.window_manager, 'vn_disp_scale', text='Scale')
					row = box.row()
					row.prop(context.window_manager, 'vn_displaycolor', text='Color')
					row = box.row()
					row.prop(context.window_manager, 'vndisp_selectiononly', text='Selection Only', toggle=True)
				
				# Testing Features:
				#row = box.row()
				#row.operator('object.set_normalvertcolors', text='VColor Test')
				#row = box.row()
				#row.operator('object.tangent_testread', text='Tangent Test')
				
				

# get selected normal(s)
class get_vnormal(bpy.types.Operator):
	bl_idname = 'object.get_vnormal'
	bl_label = 'Get Normal'
	bl_description = 'Get normal for selection'
	
	@classmethod
	def poll(cls, context):
		if context.mode=="EDIT_MESH":
			if context.window_manager.edit_splitnormals and 'polyn_meshdata' in context.active_object:
				return True
			elif not context.window_manager.edit_splitnormals and 'vertexn_meshdata' in context.active_object:
				return True
			else:
				return False
		else:
			return False
	
	def execute(self, context):
		editorfunctions.vn_get(context)
		return {'FINISHED'}


# set manually:
class set_vnormal(bpy.types.Operator):
	bl_idname = 'object.set_vnormal'
	bl_label = 'Set Normal'
	bl_description = 'Set normal for selection'
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if context.mode=="EDIT_MESH":
			if context.window_manager.edit_splitnormals and 'polyn_meshdata' in context.active_object:
				return True
			elif not context.window_manager.edit_splitnormals and 'vertexn_meshdata' in context.active_object:
				return True
			else:
				return False
		else:
			return False
	
	def execute(self, context):
		editorfunctions.vn_set_manual(context)
		return {'FINISHED'}


# Toggle normals display
class show_vertexnormals(bpy.types.Operator):
	bl_idname = "view3d.show_vertexnormals"
	bl_label = 'Show Normals'
	bl_description = 'Display custom normals as 3D lines'
	
	_handle = None
	
	@classmethod
	def poll(cls, context):
		if context.mode=="EDIT_MESH":
			if context.window_manager.edit_splitnormals and 'polyn_meshdata' in context.active_object:
				return True
			elif not context.window_manager.edit_splitnormals and 'vertexn_meshdata' in context.active_object:
				return True
			else:
				return False
		else:
			return False
	
	def modal(self, context, event):
		if context.area:
			context.area.tag_redraw()
		
		if context.window_manager.showing_vnormals == -1:
			bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
			context.window_manager.showing_vnormals = 0
			return {"CANCELLED"}
		return {"PASS_THROUGH"}
	
	def invoke(self, context, event):
		if context.area.type == "VIEW_3D":
			if context.window_manager.showing_vnormals < 1:
				context.window_manager.showing_vnormals = 1
				self._handle = bpy.types.SpaceView3D.draw_handler_add(editorfunctions.draw_vertex_normals,
					(self, context), 'WINDOW', 'POST_VIEW')
				context.window_manager.modal_handler_add(self)
				context.area.tag_redraw()
				return {"RUNNING_MODAL"}
			else:
				context.window_manager.showing_vnormals = -1
				return {'RUNNING_MODAL'}
		else:
			self.report({"WARNING"}, "View3D not found, can't run operator")
			return {"CANCELLED"}


# 	Generate:
class generate_vnormals(bpy.types.Operator):
	bl_idname = 'object.generate_vnormals'
	bl_label = 'Generate Normals'
	bl_description = 'Generate Vertex Normals'
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if context.mode=="EDIT_MESH":
			if context.window_manager.edit_splitnormals and 'polyn_meshdata' in context.active_object:
				return True
			elif not context.window_manager.edit_splitnormals and 'vertexn_meshdata' in context.active_object:
				return True
			else:
				return False
		else:
			return False
	
	def execute(self, context):
		editorfunctions.generate_newnormals(context)
		return {'FINISHED'}


# 	copy selected normals:
class copy_selectednormals(bpy.types.Operator):
	bl_idname = 'object.copy_selectednormals'
	bl_label = 'Copy Selected'
	bl_description = 'Copy selected normals'
	
	@classmethod
	def poll(cls, context):
		if context.mode=="EDIT_MESH":
			if context.window_manager.edit_splitnormals and 'polyn_meshdata' in context.active_object:
				return True
			elif not context.window_manager.edit_splitnormals and 'vertexn_meshdata' in context.active_object:
				return True
			else:
				return False
		else:
			return False
	
	def execute(self, context):
		editorfunctions.copy_tempnormalslist(context)
		return {'FINISHED'}

# 	paste stored normals:
class paste_selectednormals(bpy.types.Operator):
	bl_idname = 'object.paste_selectednormals'
	bl_label = 'Paste'
	bl_description = 'Paste stored normals'
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if context.mode=="EDIT_MESH":
			if 'temp_copypastelist' in context.window_manager and len(context.window_manager.temp_copypastelist) > 0:
				if context.window_manager.edit_splitnormals and 'polyn_meshdata' in context.active_object:
					return True
				elif not context.window_manager.edit_splitnormals and 'vertexn_meshdata' in context.active_object:
					return True
				else:
					return False
			else:
				return False
		else:
			return False
	
	def execute(self, context):
		editorfunctions.paste_tempnormalslist(context)
		return {'FINISHED'}


# 	display normals on mesh (perpoly only)
class display_normalsonmesh(bpy.types.Operator):
	bl_idname = 'object.display_normalsonmesh'
	bl_label = 'Display Normals'
	bl_description = 'shows vertex normals on the mesh if per poly is disabled'
	
	@classmethod
	def poll(cls, context):
		if context.mode=="EDIT_MESH" and (not context.window_manager.edit_splitnormals and 'vertexn_meshdata' in context.active_object):
			return True
		else:
			return False
	
	def execute(self, context):
		editorfunctions.set_meshnormals(context)
		return {'FINISHED'}


# 	switch between poly and vertex mode
class switch_normalsmode(bpy.types.Operator):
	bl_idname = 'object.switch_normalsmode'
	bl_label = 'Switch Mode'
	bl_description = 'switch between poly and vertex mode'
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH"
	
	def execute(self, context):
		if 'polyn_meshdata' not in context.active_object:
				context.active_object['polyn_meshdata'] = []
		if 'vertexn_meshdata' not in context.active_object:
			context.active_object['vertexn_meshdata'] = []
		if 'temp_copypastelist' not in bpy.context.window_manager:
			context.window_manager['temp_copypastelist'] = []
		
		if context.mode != "EDIT_MESH":
			bpy.ops.object.mode_set(mode='EDIT')
		
		context.window_manager.edit_splitnormals = not context.window_manager.edit_splitnormals
		editorfunctions.reset_normals(context)
		return {'FINISHED'}


class set_normalvertcolors(bpy.types.Operator):
	bl_idname = 'object.set_normalvertcolors'
	bl_label = 'VColors Test'
	bl_description = 'creates a vertex color layer named normalcol that stores an object-space normal map'
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH"
	
	def execute(self, context):
		editorfunctions.set_vertcolnormal(context)
		return {'FINISHED'}


class tangent_testread(bpy.types.Operator):
	bl_idname = 'object.tangent_testread'
	bl_label = 'Tangent Test'
	bl_description = 'tangent test'
	
	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH"
	
	def execute(self, context):
		editorfunctions.tangent_test(context)
		return {'FINISHED'}


#####################
# mesh data lists:

class vert_data(bpy.types.PropertyGroup):
	vpos = bpy.props.FloatVectorProperty(default=(0.0,0.0,0.0))
	vnormal = bpy.props.FloatVectorProperty(default=(0.0,0.0,0.0))

class normalslist_polymode(bpy.types.PropertyGroup):
	fcenter = bpy.props.FloatVectorProperty(default=(0.0,0.0,0.0))
	vdata = bpy.props.CollectionProperty(type=vert_data)

class normalslist_vertmode(bpy.types.PropertyGroup):
	vpos = bpy.props.FloatVectorProperty(default=(0.0,0.0,0.0))
	vnormal = bpy.props.FloatVectorProperty(default=(0.0,0.0,0.0))


#############################
# init:

def initdefaults():
	# 	data
	bpy.types.Object.polyn_meshdata = bpy.props.CollectionProperty(type=normalslist_polymode)
	bpy.types.Object.vertexn_meshdata = bpy.props.CollectionProperty(type=normalslist_vertmode)
	# 	copy/paste data
	bpy.types.WindowManager.temp_copypastelist = bpy.props.CollectionProperty(type=normalslist_vertmode)
	# 	Editor Panel:
	bpy.types.WindowManager.edit_splitnormals = bpy.props.BoolProperty(default=False,)
	bpy.types.WindowManager.convert_splitnormals = bpy.props.BoolProperty(default=False,description="Convert current normals to the mode being switched to (Results can be weird if there are any splits)")
	# generate
	bpy.types.WindowManager.vn_generatemode = bpy.props.EnumProperty(
		name="Mode",
		items=(('CUSTOM', "Custom", "Calculate normals based on mesh's face normals. Close to default, but also allows generating normals for selected surfaces."),
				('POINT', "Bent", "Calculate normals relative to 3d cursor location - good for tree foliage, bushes, etc"),
				('UPVECT', "Uniform Vector", "Calculate normals pointing in a direction specified by an input (Up by default)"),
				('G_FOLIAGE', "Ground Foliage", "Calculate selected normals pointing up, the rest bent from cursor - good for ground foliage"),
				('DEFAULT', "Smooth (Default)", "Use default normals generated by Blender"),
				),
			default='DEFAULT',
			)
	bpy.types.WindowManager.vn_resetongenerate = bpy.props.BoolProperty(default=False,description="Recalculate normals in default mode before generation")
	bpy.types.WindowManager.vn_genselectiononly = bpy.props.BoolProperty(default=False,description="Generate normals for selected vertices only")
	bpy.types.WindowManager.vn_genignorehidden = bpy.props.BoolProperty(default=False,description="Ignore hidden faces. Replacement for selected only when using Ground Foliage mode")
	bpy.types.WindowManager.vn_genbendingratio = bpy.props.FloatProperty(default=1.0,min=0.0,max=1.0,step=0.05,description="Bending Amount - The ratio between the current normals and fully bent normals")
	bpy.types.WindowManager.vn_centeroffset = bpy.props.FloatVectorProperty(default=(0.0,0.0,-1.0),subtype='TRANSLATION',)
	bpy.types.WindowManager.vn_directionalvector = bpy.props.FloatVectorProperty(default=(0.0,0.0,1.0),subtype='TRANSLATION',max=1.0,min=-1.0,)
	bpy.types.WindowManager.vn_settomeshongen = bpy.props.BoolProperty(default=True,description="Set the mesh's normals to the generated result")
	# 	Manual Edit:
	bpy.types.WindowManager.vn_realtimeedit = bpy.props.BoolProperty(default=False,description="Update saved normals with changes immediately (no Set required)")
	bpy.types.WindowManager.vn_changeasone = bpy.props.BoolProperty(default=False,description="Edit all normals on this face at once")
	bpy.types.WindowManager.vn_selected_face = bpy.props.IntProperty(default=0,min=0,max=3,description="The index of the vertex to change on this face")
	bpy.types.WindowManager.vn_curnormal_disp = bpy.props.FloatVectorProperty(default=(0.0,0.0,1.0),subtype='TRANSLATION',max=1.0,min=-1.0,update=editorfunctions.vn_set_auto,)
	# 	Display:
	bpy.types.WindowManager.showing_vnormals = bpy.props.IntProperty(default=0)
	bpy.types.WindowManager.vndisp_selectiononly = bpy.props.BoolProperty(default=False)
	bpy.types.WindowManager.vn_disp_scale = bpy.props.FloatProperty(default=1.0,min=0.5,max=16.0,step=10,description="Scale the length of the 3D lines")
	bpy.types.WindowManager.vn_displaycolor = bpy.props.FloatVectorProperty(default=(0.0,1.0,0.0),subtype='COLOR',max=1.0,min=0.0,description="Color of the 3D lines")


def clearvars():
	props = ['temp_copypastelist','edit_splitnormals','vn_generatemode','vn_directionalvector','vn_resetongenerate','vn_genselectiononly','vn_genignorehidden','vn_centeroffset','vn_selected_face','vn_realtimeedit','vn_curnormal_disp','vn_changeasone','showing_vnormals','vndisp_selectiononly','vn_disp_scale','vn_displaycolor']
	for p in props:
		if bpy.context.window_manager.get(p) != None:
			del bpy.context.window_manager[p]
		try:
			x = getattr(bpy.types.WindowManager, p)
			del x
		except:
			pass
	
	if bpy.context.window_manager.get('polyn_meshdata') != None:
		del bpy.context.window_manager['polyn_meshdata']
	if bpy.context.window_manager.get('vertexn_meshdata') != None:
		del bpy.context.window_manager['vertexn_meshdata']


def register():
	# Mesh Data
	bpy.utils.register_class(vert_data)
	bpy.utils.register_class(normalslist_polymode)
	bpy.utils.register_class(normalslist_vertmode)
	# Export/Import:
	bpy.utils.register_class(export_menu.ExportFBX)
	bpy.utils.register_class(import_normals.import_customnormals)
	# Main Panel:
	bpy.utils.register_class(fbxtools_panel)
	bpy.utils.register_class(reset_polydata)
	bpy.utils.register_class(clear_polydata)
	bpy.utils.register_class(switch_normalsmode)
	# Editor Panel
	bpy.utils.register_class(vertex_normals_panel)
	bpy.utils.register_class(get_vnormal)
	bpy.utils.register_class(set_vnormal)
	bpy.utils.register_class(generate_vnormals)
	bpy.utils.register_class(show_vertexnormals)
	bpy.utils.register_class(copy_selectednormals)
	bpy.utils.register_class(paste_selectednormals)
	bpy.utils.register_class(display_normalsonmesh)
	bpy.utils.register_class(set_normalvertcolors)
	
	bpy.utils.register_class(tangent_testread)
	
	initdefaults()


def unregister():
	#Main Panel:
	bpy.utils.unregister_class(reset_polydata)
	bpy.utils.unregister_class(clear_polydata)
	bpy.utils.unregister_class(switch_normalsmode)
	bpy.utils.unregister_class(fbxtools_panel)
	
	bpy.utils.unregister_class(tangent_testread)
	# Export/Import:
	bpy.utils.unregister_class(export_menu.ExportFBX)
	bpy.utils.unregister_class(import_normals.import_customnormals)
	# Editor Panel
	bpy.utils.unregister_class(set_normalvertcolors)
	bpy.utils.unregister_class(get_vnormal)
	bpy.utils.unregister_class(set_vnormal)
	bpy.utils.unregister_class(generate_vnormals)
	bpy.utils.unregister_class(show_vertexnormals)
	bpy.utils.unregister_class(copy_selectednormals)
	bpy.utils.unregister_class(paste_selectednormals)
	bpy.utils.unregister_class(display_normalsonmesh)
	bpy.utils.unregister_class(vertex_normals_panel)
	# Mesh Data
	bpy.utils.unregister_class(vert_data)
	bpy.utils.unregister_class(normalslist_polymode)
	bpy.utils.unregister_class(normalslist_vertmode)
	
	clearvars()


if __name__ == '__main__':
	register()
