bl_info = {
	"name": "UE FBX Normals Tools",
	"author": "Andreas Wiehn (isathar)",
	"version": (1, 0, 2),
	"blender": (2, 70, 0),
	"location": "View3D > Toolbar",
	"description": "Vertex normal editor + modified FBX exporter for "
					"custom normals, tangents and tweaks for UDK/UE",
	"warning": "",
	"wiki_url": "",
	"tracker_url": "https://github.com/isathar/Blender_UDK_FBX_Tools/issues/",
	"category": "Mesh"}


import bpy
import sys

from . import export_menu
from . import editorfunctions
from . import import_normals

##########################
# Editor:

# UI Panel
class vertex_normals_panel(bpy.types.Panel):
	bl_idname = "object.vertex_normals_panel"
	bl_label = ' Normals Editor'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = "Shading / UVs"
	
	@classmethod
	def poll(self, context):
		if context.active_object != None:
			if context.active_object.type == 'MESH':
				return True
		return False
	
	def draw(self, context):
		layout = self.layout
		
		usingMontBuild = hasattr(context.active_object.data, "define_normals_split_custom")
		
		# check if editor tab should be visible
		showeditor = False
		if context.window_manager.edit_splitnormals:
			if 'polyn_meshdata' in context.active_object:
				if len(editorfunctions.normals_data.cust_normals_ppoly) == len(context.active_object.polyn_meshdata):
					showeditor = True
		elif 'vertexn_meshdata' in context.active_object:
			if len(editorfunctions.normals_data.cust_normals_pvertex) == len(context.active_object.vertexn_meshdata):
				showeditor = True
			
		if showeditor:
			# Mesh Data (editor variables are synced)
			box = layout.box()
			if context.window_manager.edit_splitnormals:
				box.prop(context.window_manager, 'vnpanel_showmeshdata', 
						text='Mesh Data (Poly)', toggle=True)
			else:
				box.prop(context.window_manager, 'vnpanel_showmeshdata', 
						text='Mesh Data (Vertex)', toggle=True)
			
			if context.window_manager.vnpanel_showmeshdata:
				box2 = box.box()
				box2.row().operator('object.reset_polydata', text='Reset')
				box2.row().operator('object.clear_polydata', text='Clear')
				
				box2.row().prop(context.window_manager,'convert_splitnormals',
						text='Convert on Switch')
				box2.row().operator('object.switch_normalsmode', 
						text='Switch Mode')
				
				box2.row().operator('object.display_normalsonmesh', 
						text='Apply to Mesh')
				
				if 'vertex_normal_list' in context.active_object:
					box2.row().operator('object.copy_normals_recalcvertexnormals', 
							text='Copy from RVN')
			
			# Auto Generate
			genmode = context.window_manager.vn_genmode
			box = layout.box()
			box.prop(context.window_manager, 'vnpanel_showautogen', 
						text='Auto Generate', toggle=True)
			if context.window_manager.vnpanel_showautogen:
				#if context.mode == "EDIT_MESH":
				box2 = box.box()
				
				if genmode == 'UPVECT':
					box2.row().label("Direction:", 'NONE')
					box2.row().column().prop(context.window_manager,
							'vn_dirvector',
							text='')
				
				if genmode != 'G_FOLIAGE' and genmode != 'DEFAULT':
					if genmode == 'BENT':
						box2.row().prop(context.window_manager,
							'vn_genbendingratio',
							text='Bend Ratio')
					box2.row().prop(context.window_manager, 
							'vn_genselectiononly',
							text='Selected Only')
					
					if usingMontBuild or not context.window_manager.edit_splitnormals:
						box2.row().column().prop(context.window_manager,
								'vn_settomeshongen',
								text='Apply to Mesh')
					
				elif genmode == 'G_FOLIAGE':
					box2.row().column().prop(context.window_manager,
							'vn_centeroffset',
							text='Center Offset')
					box2.row().prop(context.window_manager,
							'vn_genignorehidden',
							text='Ignore Hidden')
				
				box2.row().prop(context.window_manager,
						'vn_genmode', text='')
				box2.row().operator('object.generate_vnormals',
						text='Generate')
			
			# Transfer Normals
			box = layout.box()
			box.prop(context.window_manager, 'vnpanel_showtransnormals',
					text='Transfer', toggle=True)
			if context.window_manager.vnpanel_showtransnormals:
				if context.mode == "OBJECT":
					box2 = box.box()
					if "object_transfervertexnorms" in context.user_preferences.addons.keys():
						box2.row().prop_search(context.window_manager, 
								"normtrans_sourceobj", 
								context.scene, 
								"objects", 
								"Source",
								"Source",
								False,
								'MESH_CUBE')
						box2.row().prop(context.window_manager,
								'normtrans_influence', 
								text='Influence')
						box2.row().prop(context.window_manager,
								'normtrans_maxdist', 
								text='Distance')
						box2.row().prop(context.window_manager,
								'normtrans_bounds', 
								text='Bounds')
						box2.row().operator('object.transfer_normalstoobj',
								text='Transfer Normals')
					else:
						box2.row().label(
								"Transfer Vertex Normals Addon required",
								'NONE')
					
				else:
					box.box().row().label("Object Mode required", 'NONE')
			
			# Manual edit
			box = layout.box()
			box.prop(context.window_manager, 'vnpanel_showmanualedit',
						text='Manual Edit', toggle=True)
			if context.window_manager.vnpanel_showmanualedit:
				if context.mode == "EDIT_MESH":
					box2 = box.box()
					box2.row().column().prop(context.window_manager,
							'vn_curnormal_disp', text='')
					if context.window_manager.edit_splitnormals:
						box2.row().prop(context.window_manager,
								'vn_selected_face', text='Vert Index')
					
					row = box2.row()
					row.operator('object.get_vnormal', text='Get')
					row.operator('object.set_vnormal', text='Set')
					
					box2.row().prop(context.window_manager,
							'vn_realtimeedit', text='Real-Time')
					
					if context.window_manager.edit_splitnormals:
						box2.row().prop(context.window_manager,
								'vn_changeasone', text='Edit All')
				else:
					box.box().row().label("Edit Mode required", 'NONE')
			
			# Display
			box = layout.box()
			box.prop(context.window_manager, 'vnpanel_showdisplay',
						text='Display', toggle=True)
			if context.window_manager.vnpanel_showdisplay:
				box2 = box.box()
				box2.prop(context.window_manager,
						'vn_disp_scale', text='Scale')
				box2.prop(context.window_manager,
						'vn_displaycolor', text='Color')
				
				if context.mode == "EDIT_MESH":
					box2.row().prop(context.window_manager,
							'vndisp_selectiononly', text='Selected Only')
				
				if context.window_manager.showing_vnormals < 1:
					box2.row().operator('view3d.show_vertexnormals',
							text='Show Normals')
				else:
					box2.row().operator('view3d.show_vertexnormals',
							text='Hide Normals')
			
		else:
			# Mesh Data (editor variables are empty or not synced)
			box = layout.box()
			box.prop(context.window_manager, 'vnpanel_showmeshdata',
					text='Mesh Data', toggle=True)
			if context.window_manager.vnpanel_showmeshdata:
				box.row().operator('object.reset_polydata', text='Initialize')
				# load saved normals from data if it exists
				if context.window_manager.edit_splitnormals:
					if 'polyn_meshdata' in context.active_object:
						box.row().operator('object.load_polydata',
								text='Load')
				elif 'vertexn_meshdata' in context.active_object:
					box.row().operator('object.load_polydata', text='Load')



# reset data to default normals
class reset_polydata(bpy.types.Operator):
	bl_idname = 'object.reset_polydata'
	bl_label = 'Create Normals Data'
	bl_description = 'Recreate mesh data struct'
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if context.active_object != None:
			if context.active_object.type == 'MESH':
				return True
		return False
	
	def execute(self, context):
		if len(editorfunctions.normals_data.cust_normals_ppoly) > 0:
			editorfunctions.normals_data.cust_normals_ppoly.clear()
		if len(editorfunctions.normals_data.cust_normals_pvertex) > 0:
			editorfunctions.normals_data.cust_normals_pvertex.clear()
		
		editorfunctions.reset_normals(context)
		
		return {'FINISHED'}


# delete data
class clear_polydata(bpy.types.Operator):
	bl_idname = 'object.clear_polydata'
	bl_label = 'Delete Normals Data'
	bl_description = 'Delete mesh data struct'
	bl_options = {'REGISTER', 'UNDO'}
	# doesn't work with undo
	
	@classmethod
	def poll(cls, context):
		return True
	
	def execute(self, context):
		if 'showing_vnormals' in context.window_manager:
			context.window_manager.showing_vnormals = -1
		if len(editorfunctions.normals_data.cust_normals_ppoly) > 0:
			editorfunctions.normals_data.cust_normals_ppoly.clear()
		if len(editorfunctions.normals_data.cust_normals_pvertex) > 0:
			editorfunctions.normals_data.cust_normals_pvertex.clear()
		
		if 'polyn_meshdata' in context.active_object:
			del context.active_object['polyn_meshdata']
		if 'vertexn_meshdata' in context.active_object:
			del context.active_object['vertexn_meshdata']
		
		return {'FINISHED'}


# load editor variabes from previously saved mesh data
class load_polydata(bpy.types.Operator):
	bl_idname = 'object.load_polydata'
	bl_label = 'Load Normals Data'
	bl_description = 'Load mesh data struct'
	bl_options = {'REGISTER', 'UNDO'}
	# undo doesn't work for this since no mesh data is changed
	
	@classmethod
	def poll(cls, context):
		if context.active_object != None:
			if context.active_object.type == 'MESH':
				return True
		return False
	
	def execute(self, context):
		editorfunctions.load_normalsdata(context)
		return {'FINISHED'}
	

# get selected normal(s)
class get_vnormal(bpy.types.Operator):
	bl_idname = 'object.get_vnormal'
	bl_label = 'Get Normal'
	bl_description = 'Get normal for selection'
	# no need for undo
	
	@classmethod
	def poll(cls, context):
		if context.mode=="EDIT_MESH":
			if context.window_manager.edit_splitnormals:
				return (len(editorfunctions.normals_data.cust_normals_ppoly) > 0)
			else:
				return (len(editorfunctions.normals_data.cust_normals_pvertex) > 0)
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
			if context.window_manager.edit_splitnormals:
				return (len(editorfunctions.normals_data.cust_normals_ppoly) > 0)
			else:
				return (len(editorfunctions.normals_data.cust_normals_pvertex) > 0)
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
		if context.window_manager.edit_splitnormals:
			if len(editorfunctions.normals_data.cust_normals_ppoly) <= 0:
				context.window_manager.showing_vnormals = -1
				return False
		elif len(editorfunctions.normals_data.cust_normals_pvertex) <= 0:
			context.window_manager.showing_vnormals = -1
			return False
		return True
	
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
				curobjname = context.active_object.data.name
				
				if editorfunctions.normals_data.lastdisplaymesh != curobjname:
					editorfunctions.normals_data.lastdisplaymesh = curobjname
				context.window_manager.showing_vnormals = 1
				
				self._handle = bpy.types.SpaceView3D.draw_handler_add(
					editorfunctions.draw_vertex_normals,
					(self, context), 'WINDOW', 'POST_VIEW')
				context.window_manager.modal_handler_add(self)
				context.area.tag_redraw()
				return {"RUNNING_MODAL"}
			else:
				context.window_manager.showing_vnormals = -1
				editorfunctions.normals_data.lastdisplaymesh = ''
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
		if context.window_manager.edit_splitnormals:
			return len(editorfunctions.normals_data.cust_normals_ppoly) > 0
		return len(editorfunctions.normals_data.cust_normals_pvertex) > 0
	
	def execute(self, context):
		editorfunctions.generate_newnormals(self, context)
		return {'FINISHED'}




# 	display normals on mesh (perpoly mode or Mont29's build only)
class display_normalsonmesh(bpy.types.Operator):
	bl_idname = 'object.display_normalsonmesh'
	bl_label = 'Display Normals'
	bl_description = 'Applies normals to mesh in vertex mode'
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if context.active_object != None:
			if hasattr(context.active_object.data, "define_normals_split_custom"):
				if not context.window_manager.edit_splitnormals:
					return len(editorfunctions.normals_data.cust_normals_pvertex) > 0
				else:
					return len(editorfunctions.normals_data.cust_normals_ppoly) > 0
			else:
				if not context.window_manager.edit_splitnormals:
					return len(editorfunctions.normals_data.cust_normals_pvertex) > 0
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
		if context.active_object != None:
			if context.active_object.type == 'MESH':
				return True
		return False
	
	def execute(self, context):
		if context.window_manager.edit_splitnormals:
			context.window_manager.edit_splitnormals = False
		else:
			context.window_manager.edit_splitnormals = True
		
		editorfunctions.reset_normals(context)
		return {'FINISHED'}


# bridge to transfer vertex normals addon
class transfer_normalstoobj(bpy.types.Operator):
	bl_idname = 'object.transfer_normalstoobj'
	bl_label = 'Transfer'
	bl_description = 'Transfer normals between objects'
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if context.mode == 'OBJECT':
			if not context.window_manager.edit_splitnormals:
				if context.window_manager.normtrans_bounds == 'ONLY':
					return True
				elif context.window_manager.normtrans_sourceobj != "":
					return context.scene.objects[
						context.window_manager.normtrans_sourceobj
						].type == 'MESH'
		return False
	
	def execute(self, context):
		editorfunctions.transfer_normals(self, context)
		return {'FINISHED'}


class copy_normals_recalcvertexnormals(bpy.types.Operator):
	bl_idname = 'object.copy_normals_recalcvertexnormals'
	bl_label = 'Copy from RVN'
	bl_description = 'Copy normals saved by the Recalc Vertex Normals addon'
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		if not context.window_manager.edit_splitnormals:
			return ('vertex_normal_list' in context.active_object)
		return False
	
	def execute(self, context):
		editorfunctions.copy_fromadsn(context)
		return {'FINISHED'}
	


#####################
# mesh data lists:

class vert_data(bpy.types.PropertyGroup):
	vnormal = bpy.props.FloatVectorProperty(
		default=(0.00000000,0.00000000,0.00000000),
		subtype='DIRECTION',
		precision=6
	)

class normalslist_polymode(bpy.types.PropertyGroup):
	vdata = bpy.props.CollectionProperty(type=vert_data)


#############################
# init:

def initdefaults():
	types = bpy.types
	
	# 	data
	types.Object.polyn_meshdata = bpy.props.CollectionProperty(
			type=normalslist_polymode)
	types.Object.vertexn_meshdata = bpy.props.CollectionProperty(
			type=vert_data)
	
	# 	Editor Panel:
	types.WindowManager.edit_splitnormals = bpy.props.BoolProperty(
			default=False)
	types.WindowManager.convert_splitnormals = bpy.props.BoolProperty(
			default=False,
			description="Convert current normals on mode switch")
	# generate
	types.WindowManager.vn_genmode = bpy.props.EnumProperty(
			name="Mode",
			description='Method to use for generating normals',
			items=(
				('UPVECT', 
					'Uniform Vector', 
					"Calculate normals pointing in a " + 
					"direction specified by an input"),
				('G_FOLIAGE', 
					'Ground Foliage', 
					"Calculate selected normals pointing up, " +
					"the rest bent from cursor"),
				('BENT', 
					'Bent', 
					"Calculate normals relative to 3d cursor location"),
				('CUSTOM', 
					'Custom', 
					"Calculate normals based on mesh's face normals. " + 
					"Close to default, but also allows generating normals " +
					"for selected surfaces."),
				('DEFAULT', 
					'Smooth (Default)', 
					"Use default normals generated by Blender"),
				),
			default='DEFAULT',
			)
	types.WindowManager.vn_genselectiononly = bpy.props.BoolProperty(
			default=False,
			description='Generate normals for selected vertices only')
	types.WindowManager.vn_genignorehidden = bpy.props.BoolProperty(
			default=False,
			description='Ignore hidden faces')
	types.WindowManager.vn_genbendingratio = bpy.props.FloatProperty(
			default=1.0,min=0.0,max=1.0,subtype='FACTOR',
			description='Ratio to bend normals by')
	types.WindowManager.vn_centeroffset = bpy.props.FloatVectorProperty(
			default=(0.0,0.0,-1.0),subtype='TRANSLATION')
	types.WindowManager.vn_dirvector = bpy.props.FloatVectorProperty(
			default=(0.0,0.0,1.0),subtype='TRANSLATION',max=1.0,min=-1.0)
	types.WindowManager.vn_settomeshongen = bpy.props.BoolProperty(
			default=True,
			description='Update mesh normals with the generated result')
	
	# 	Manual Edit:
	types.WindowManager.vn_realtimeedit = bpy.props.BoolProperty(
			default=False,
			description='Update saved normals with changes automatically')
	types.WindowManager.vn_changeasone = bpy.props.BoolProperty(
			default=False,
			description='Edit all normals on selected face at once')
	types.WindowManager.vn_selected_face = bpy.props.IntProperty(
			default=0,min=0,max=3,
			description='The index of the vertex to change on this face')
	types.WindowManager.vn_curnormal_disp = bpy.props.FloatVectorProperty(
			default=(0.0,0.0,1.0),subtype='TRANSLATION',max=1.0,min=-1.0,
			update=editorfunctions.vn_set_auto)
	
	# 	Display:
	types.WindowManager.showing_vnormals = bpy.props.IntProperty(
			default=0)
	types.WindowManager.vndisp_selectiononly = bpy.props.BoolProperty(
			default=False)
	types.WindowManager.vn_disp_scale = bpy.props.FloatProperty(
			default=1.0,min=0.1,max=16.0,step=10,
			description='Length of the displayed lines')
	types.WindowManager.vn_displaycolor = bpy.props.FloatVectorProperty(
			default=(0.0,1.0,0.0),subtype='COLOR',max=1.0,min=0.0,
			description='Normals Color')
	
	# Transfer Vertex Normals:
	types.WindowManager.normtrans_sourceobj = bpy.props.StringProperty(
			default='',description='Object to get normals from')
	types.WindowManager.normtrans_influence = bpy.props.FloatProperty(
			description='Transfer strength, negative inverts',
			subtype='FACTOR',min=-1.0,max=1.0,default=1.0)
	types.WindowManager.normtrans_maxdist = bpy.props.FloatProperty(
			description='Transfer distance, 0 for infinite',
			subtype='DISTANCE',unit='LENGTH',
			min=0.0,max=sys.float_info.max,soft_max=20.0,default=0.01)
	types.WindowManager.normtrans_bounds = bpy.props.EnumProperty(
			name='Boundary Edges',
			description='Management for single-face edges.',
			items=[('IGNORE', 'Ignore', 'Discard source boundary edges.'),
				   ('INCLUDE', 'Include', 'Include source boundary edges.'),
				   ('ONLY', 'Only', 'Operate only on boundary edges.')],
			default='IGNORE'
			)
	
	# ui blocks
	types.WindowManager.vnpanel_showmeshdata = bpy.props.BoolProperty(
			default=True, description='Toggle Submenu')
	types.WindowManager.vnpanel_showautogen = bpy.props.BoolProperty(
			default=False, description='Toggle Submenu')
	types.WindowManager.vnpanel_showmanualedit = bpy.props.BoolProperty(
			default=False, description='Toggle Submenu')
	types.WindowManager.vnpanel_showtransnormals = bpy.props.BoolProperty(
			default=False, description='Toggle Submenu')
	types.WindowManager.vnpanel_showdisplay = bpy.props.BoolProperty(
			default=False, description='Toggle Submenu')
	


def clearvars():
	props = ['edit_splitnormals','convert_splitnormals','vn_genmode',
	'vn_genselectiononly','vn_genignorehidden','vn_genbendingratio',
	'vn_centeroffset','vn_dirvector','vn_settomeshongen','vn_realtimeedit',
	'vn_changeasone','vn_selected_face','vn_curnormal_disp',
	'showing_vnormals','vndisp_selectiononly','vn_disp_scale',
	'vn_displaycolor','normtrans_sourceobj','normtrans_influence',
	'normtrans_maxdist','normtrans_bounds','vnpanel_showmeshdata',
	'vnpanel_showautogen','vnpanel_showmanualedit',
	'vnpanel_showtransnormals','vnpanel_showdisplay']
	
	for p in props:
		if bpy.context.window_manager.get(p) != None:
			del bpy.context.window_manager[p]
		try:
			x = getattr(bpy.types.WindowManager, p)
			del x
		except:
			pass
	
	editorfunctions.cleanup_datavars()


def exportmenu_func(self, context):
	self.layout.operator(export_menu.ExportFBX.bl_idname,
						text="FBX Custom (.fbx)")

def importmenu_func(self, context):
	self.layout.operator(import_normals.import_customnormals.bl_idname,
						text="Normals from FBX file (.fbx)")


def register():
	# Mesh Data
	bpy.utils.register_class(vert_data)
	bpy.utils.register_class(normalslist_polymode)
	# Export/Import:
	bpy.utils.register_class(export_menu.ExportFBX)
	bpy.utils.register_class(import_normals.import_customnormals)
	# Main Panel:
	bpy.utils.register_class(reset_polydata)
	bpy.utils.register_class(load_polydata)
	bpy.utils.register_class(clear_polydata)
	bpy.utils.register_class(switch_normalsmode)
	# Editor Panel
	bpy.utils.register_class(vertex_normals_panel)
	bpy.utils.register_class(get_vnormal)
	bpy.utils.register_class(set_vnormal)
	bpy.utils.register_class(generate_vnormals)
	bpy.utils.register_class(show_vertexnormals)
	bpy.utils.register_class(display_normalsonmesh)
	
	bpy.utils.register_class(transfer_normalstoobj)
	bpy.utils.register_class(copy_normals_recalcvertexnormals)
	
	bpy.types.INFO_MT_file_export.append(exportmenu_func)
	bpy.types.INFO_MT_file_import.append(importmenu_func)
	
	initdefaults()


def unregister():
	#Main Panel:
	bpy.utils.unregister_class(reset_polydata)
	bpy.utils.unregister_class(load_polydata)
	bpy.utils.unregister_class(clear_polydata)
	bpy.utils.unregister_class(switch_normalsmode)
	
	# Export/Import:
	bpy.utils.unregister_class(export_menu.ExportFBX)
	bpy.utils.unregister_class(import_normals.import_customnormals)
	# Editor Panel
	bpy.utils.unregister_class(get_vnormal)
	bpy.utils.unregister_class(set_vnormal)
	bpy.utils.unregister_class(generate_vnormals)
	bpy.utils.unregister_class(show_vertexnormals)
	bpy.utils.unregister_class(display_normalsonmesh)
	bpy.utils.unregister_class(vertex_normals_panel)
	# Mesh Data
	bpy.utils.unregister_class(vert_data)
	bpy.utils.unregister_class(normalslist_polymode)
	
	bpy.utils.unregister_class(transfer_normalstoobj)
	bpy.utils.unregister_class(copy_normals_recalcvertexnormals)
	
	bpy.types.INFO_MT_file_export.remove(exportmenu_func)
	bpy.types.INFO_MT_file_import.remove(importmenu_func)
	
	clearvars()


if __name__ == '__main__':
	register()

