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

bl_info = {
	"name": "FBX Normals & Smoothing Tools",
	"author": "Andreas Wiehn (isathar)",
	"version": (0, 5, 0),
	"blender": (2, 70, 0),
	"location": "View3D > Toolbar",
	"description": "Adds editors for smoothing groups and vertex normals,"
					"as well as an exporter with some UDK-specific optimizations "
					"that supports both. Also supports tangent and binormal "
					"calculation and export, (almost completely) synced with "
					"UDK's (and xNormal's default) tangent space.",
	"warning": "",
	"wiki_url": "",
	"tracker_url": "",
	"category": "Mesh"}

import bpy
from bpy.types import Panel

from . import export_menu
from . import editorfunctions

#########################
# Main Menu

# UI Panel
class udk_fbxtools_panel(bpy.types.Panel):
	bl_idname = "object.udk_fbxtools_panel"
	bl_label = 'UDK FBX Tools'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = "FBX Tools"

	def __init__(self):
		pass

	@classmethod
	def poll(self, context):
		return context.active_object != None and bpy.context.active_object.type == 'MESH'

	def draw(self, context):
		layout = self.layout
		
		row = layout.row()
		label = row.label("Tools", 'NONE')
		box = layout.box()
		row = box.row()
		row.operator('export_scene.fbx_custom', text='Export')
				
		row = layout.row()
		label = row.label("  Mesh Data:", 'NONE')
		if 'custom_meshdata' in bpy.context.object:
			box = layout.box()
			row = box.row()
			row.operator('object.reset_polydata', text='Reset')
			row.operator('object.clear_polydata', text='Clear')
			
			row = box.row()
			label = row.label("   Smoothing Groups:", 'NONE')
			
			row = box.row()
			if bpy.context.window_manager.smoothinggroups_enabled:
				row.operator('object.enable_smoothinggroups', text='Disable')
			else:
				row.operator('object.enable_smoothinggroups', text='Enable')
					
			row = box.row()
			label = row.label("   Custom Normals:", 'NONE')
			row = box.row()
				
			if bpy.context.window_manager.vertexnormals_enabled:
				row.operator('object.enable_vertexnormals', text='Disable')
			else:
				row.operator('object.enable_vertexnormals', text='Enable')
		else:
			box = layout.box()
			row = box.row()
			row.operator('object.reset_polydata', text='Initialize Data')
		
		row = layout.row()
		label = row.label(" Tweaks:", 'NONE')
		box = layout.box()
		row = box.row()
		
		
			
		if bpy.context.window_manager.tweak_gridsettings_on or (context.space_data.grid_scale < 16.0 or context.space_data.grid_subdivisions < 16.0):
			row.operator('object.tweak_gridsettings', text='Reset Grid')
		else:
			row.operator('object.tweak_gridsettings', text='Match Grid')
		
		row = layout.row()
		label = row.label(" Debug:", 'NONE')
		row = layout.row()
		row.operator('object.debug_shownums', text='Show')
		row = layout.row()
		
		
		

class reset_polydata(bpy.types.Operator):
	bl_idname = 'object.reset_polydata'
	bl_label = 'Create Mesh Data'
	bl_description = 'Recreate mesh data struct'

	@classmethod
	def poll(cls, context):
		return context.active_object != None and bpy.context.active_object.type == 'MESH'

	def execute(self, context):
		if 'custom_meshdata' not in bpy.context.object:
			bpy.context.object['custom_meshdata'] = []
		if 'temp_meshdata' not in bpy.context.window_manager:
			bpy.context.window_manager['temp_meshdata'] = []
		
		if context.mode != "EDIT_MESH":
			bpy.ops.object.mode_set(mode='EDIT')
		
		editorfunctions.reset_normals(self, context)
		
		return {'FINISHED'}


class clear_polydata(bpy.types.Operator):
	bl_idname = 'object.clear_polydata'
	bl_label = 'Delete Mesh Data'
	bl_description = 'Delete mesh data struct'

	@classmethod
	def poll(cls, context):
		return bpy.context.object.custom_meshdata != None

	def execute(self, context):
		if 'showing_vnormals' in bpy.context.window_manager:
			bpy.context.window_manager.showing_vnormals = -1
		
		bpy.context.window_manager.smoothinggroups_enabled = False
		bpy.context.window_manager.vertexnormals_enabled = False
		
		if 'custom_meshdata' in bpy.context.object:
			del bpy.context.object['custom_meshdata']
		
		return {'FINISHED'}
		
		


class enable_smoothinggroups(bpy.types.Operator):
	bl_idname = 'object.enable_smoothinggroups'
	bl_label = 'Enable Smoothing Groups'
	bl_description = 'Toggle Smoothing Groups Editor'

	@classmethod
	def poll(cls, context):
		return bpy.context.object.custom_meshdata != None

	def execute(self, context):
		if bpy.context.window_manager.smoothinggroups_enabled:
			bpy.context.window_manager.smoothinggroups_enabled = False
		else:
			bpy.context.window_manager.smoothinggroups_enabled = True
			
		return {'FINISHED'}


class enable_vertexnormals(bpy.types.Operator):
	bl_idname = 'object.enable_vertexnormals'
	bl_label = 'Enable Custom Normals'
	bl_description = 'Toggle Vertex Normals Editor'

	@classmethod
	def poll(cls, context):
		return bpy.context.object.custom_meshdata != None

	def execute(self, context):
		if bpy.context.window_manager.vertexnormals_enabled:
			bpy.context.window_manager.vertexnormals_enabled = False
		else:
			bpy.context.window_manager.vertexnormals_enabled = True
			
		return {'FINISHED'}


class tweak_gridsettings(bpy.types.Operator):
	bl_idname = 'object.tweak_gridsettings'
	bl_label = 'Optimize Grid'
	bl_description = 'Optimize grid for UDK units'

	@classmethod
	def poll(cls, context):
		return True

	def execute(self, context):
		if bpy.context.window_manager.tweak_gridsettings_on:
			bpy.context.window_manager.tweak_gridsettings_on = False
			context.space_data.grid_scale = 1.0
			context.space_data.grid_subdivisions = 1.0
		else:
			bpy.context.window_manager.tweak_gridsettings_on = True
			context.space_data.grid_scale = 16.0
			context.space_data.grid_subdivisions = 16.0
			
		return {'FINISHED'}


class debug_shownums(bpy.types.Operator):
	bl_idname = 'object.debug_shownums'
	bl_label = 'Debug'
	bl_description = 'temp debug stuff'

	@classmethod
	def poll(cls, context):
		return context.active_object != None and bpy.context.active_object.type == 'MESH'

	def execute(self, context):
		me = bpy.context.object.data
		me.update(calc_tessface=True)
		editorfunctions.debug_getmeshdata(self, me)

		return {'FINISHED'}



######################################
# Smoothing Groups Editor:

# UI Panel
class smoothing_groups_panel(bpy.types.Panel):
	bl_idname = "object.smoothing_groups_panel"
	bl_label = ' Smoothing Groups'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = "FBX Tools"
	
	@classmethod
	def poll(self, context):
		return context.active_object != None and bpy.context.active_object.type == 'MESH'

	def draw(self, context):
		layout = self.layout

		row = layout.row(align=True)
		if bpy.context.window_manager.smoothinggroups_enabled:
			if context.mode != "EDIT_MESH":
				label = row.label("Edit Mode required", 'NONE')
			else:
				if 'custom_meshdata' not in bpy.context.object:
					label = row.label("No smoothing data", 'NONE')
				else:

					row = layout.row(align=True)
					label = row.label(" Group Tools:", 'NONE')

					box = layout.box()
					row = box.row(align=True)
					row.prop(bpy.context.window_manager, 'sg_selectedgroup', text='')
					row.operator('object.set_sgroup', text='Set')

					row = box.row(align=True)
					row.operator('object.select_sgroup', text='Select Group')


					row = layout.row(align=True)
					label = row.label(" Display:", 'NONE')

					box = layout.box()
					row = box.row(align=True)
					if bpy.context.window_manager.showing_smoothgroups < 1:
						row.operator('view3d.show_smoothgroups', text='Show Groups')
					else:
						row.operator('view3d.show_smoothgroups', text='Hide Groups')

					row = box.row(align=True)
					row.prop(bpy.context.window_manager, 'sg_showselected', text = 'Selection Only', toggle=True)
		else:
			row = layout.row()
			label = row.label("Disabled", 'NONE')

# Set group num for selected faces
class set_sgroup(bpy.types.Operator):
	bl_idname = 'object.set_sgroup'
	bl_label = 'Set Group'

	@classmethod
	def poll(cls, context):
		return context.active_object != None and bpy.context.active_object.type == 'MESH'

	def execute(self, context):
		editorfunctions.set_sgroup(context, bpy.context.window_manager.sg_selectedgroup)
		return {'FINISHED'}
		
# select faces in group
class select_sgroup(bpy.types.Operator):
	bl_idname = 'object.select_sgroup'
	bl_label = 'Select Group'

	@classmethod
	def poll(cls, context):
		return context.active_object != None and bpy.context.active_object.type == 'MESH'

	def execute(self, context):
		editorfunctions.select_facesingroup(context, bpy.context.window_manager.sg_selectedgroup)
		return {'FINISHED'}


# Toggle smoothing group display
class show_smoothgroups(bpy.types.Operator):
	bl_idname = "view3d.show_smoothgroups"
	bl_label = 'Show Groups'

	_handle = None

	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH"

	def modal(self, context, event):
		if context.area:
			context.area.tag_redraw()
		# removal of callbacks when operator is called again
		if bpy.context.window_manager.showing_smoothgroups == -1:
			bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
			bpy.context.window_manager.showing_smoothgroups = 0
			return {"CANCELLED"}
		return {"PASS_THROUGH"}

	def invoke(self, context, event):
		if context.area.type == "VIEW_3D":
			if bpy.context.window_manager.showing_smoothgroups < 1:
				
				# operator is called for the first time, start everything
				bpy.context.window_manager.showing_smoothgroups = 1
				self._handle = bpy.types.SpaceView3D.draw_handler_add(editorfunctions.draw_smoothing_groups,
					(self, context), 'WINDOW', 'POST_PIXEL')
				context.window_manager.modal_handler_add(self)
				return {"RUNNING_MODAL"}
			else:
				# operator is called again, stop displaying
				bpy.context.window_manager.showing_smoothgroups = -1
				return {'RUNNING_MODAL'}
		else:
			self.report({"WARNING"}, "View3D not found, can't run operator")
			return {"CANCELLED"}

#end Smoothing Groups
#######################################



##########################
# Vertex Normals Editor:

# UI Panel
class vertex_normals_panel(bpy.types.Panel):
	bl_idname = "object.vertex_normals_panel"
	bl_label = ' Vertex Normals'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = "FBX Tools"

	@classmethod
	def poll(self, context):
		return context.active_object != None and bpy.context.active_object.type == 'MESH'

	def draw(self, context):
		layout = self.layout

		if bpy.context.window_manager.vertexnormals_enabled:
			if context.mode != "EDIT_MESH":
				row = layout.row()
				label = row.label("Edit Mode required", 'NONE')
			else:
				if 'custom_meshdata' not in bpy.context.object:
					row = layout.row()
					label = row.label("No vertex data", 'NONE')
				else:
					row = layout.row()
					row.operator('object.reset_vnormals', text='Reset')
					
					row = layout.row()
					label = row.label(" Manual Edit:", 'NONE')

					box = layout.box()
					box2 = box.box()
					row = box2.row()
					row.column().prop(bpy.context.window_manager, 'vn_curnormal_disp', text='')
					row = box2.row()
					row.prop(bpy.context.window_manager, 'vn_selected_face', text='Face')
					row = box.row()
					row.operator('object.get_vnormal', text='Show')
					row.operator('object.set_vnormal', text='Set')
					
					row = box.row()
					row.prop(bpy.context.window_manager, 'vn_realtimeedit', text='Real-Time Edit')
					
					
					row = layout.row()
					label = row.label("Transfer Normals:", 'NONE')
					box = layout.box()
					row = box.row()
					row.operator('object.copy_selectednormals', text='Copy')
					row.operator('object.paste_selectednormals', text='Paste')

					#row = box.row()
					#row.prop(context.window_manager, 'edgesharpness', text='Sharp Amount')
					#row = box.row()
					#row.prop(context.window_manager, 'normalssplit', text='Split', toggle=True)

					row = layout.row()
					label = row.label(" Auto Generation:", 'NONE')
					box = layout.box()
					row = box.row()
					row.prop(bpy.context.window_manager, 'vn_generatemode', text='')
					row = box.row()
					row.operator('object.generate_vnormals', text='Generate')
					row = box.row()
					row.prop(bpy.context.window_manager, 'vn_resetongenerate', text='Reset First')
					row = box.row()
					row.prop(bpy.context.window_manager, 'vn_genselectiononly', text='Selected Only')
					
					if bpy.context.window_manager.vn_generatemode == 'SELECTION' or bpy.context.window_manager.vn_generatemode == 'ANGLES':
						row = box.row()
						label = row.label("Angle Thresholds:", 'NONE')
						row = box.row()
						row.prop(bpy.context.window_manager, 'vn_anglebased_dot_face', text='Face')
						row = box.row()
						row.prop(bpy.context.window_manager, 'vn_anglebased_dot_vert', text='Vertex')
					

					row = layout.row()
					label = row.label(" Display:", 'NONE')

					box = layout.box()
					row = box.row()
					if bpy.context.window_manager.showing_vnormals < 1:
						row.operator('view3d.show_vertexnormals', text='Show Normals')
					else:
						row.operator('view3d.show_vertexnormals', text='Hide Normals')
						row = box.row()
						row.prop(bpy.context.window_manager, 'vn_disp_scale', text='Scale')
						row = box.row()
						row.prop(bpy.context.window_manager, 'vn_displaycolor', text='Color')
						
						row = box.row()
						row.prop(bpy.context.window_manager, 'vndisp_selectiononly', text='Selection Only', toggle=True)
		else:
			row = layout.row()
			label = row.label("Disabled", 'NONE')



# creates a clean list based on default normals
class reset_vnormals(bpy.types.Operator):
	bl_idname = 'object.reset_vnormals'
	bl_label = 'Reset Normals'
	bl_description = 'Recreate normals list from mesh data'

	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH"

	def execute(self, context):
		editorfunctions.reset_normals(self, context)

		return {'FINISHED'}



# get selected normal(s)
class get_vnormal(bpy.types.Operator):
	bl_idname = 'object.get_vnormal'
	bl_label = 'Reset Normal'
	bl_description = 'Reset Vertex Normal'

	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH" and ('custom_meshdata' in bpy.context.object)

	def execute(self, context):
		editorfunctions.vn_get(self, context)
		return {'FINISHED'}


# set manually:
class set_vnormal(bpy.types.Operator):
	bl_idname = 'object.set_vnormal'
	bl_label = 'Reset Normal'
	bl_description = 'Reset Vertex Normal'

	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH" and ('custom_meshdata' in bpy.context.object)

	def execute(self, context):
		editorfunctions.vn_set_manual(self,context)
		return {'FINISHED'}


# Toggle normals display
class show_vertexnormals(bpy.types.Operator):
	bl_idname = "view3d.show_vertexnormals"
	bl_label = 'Show Normals'

	_handle = None

	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH" and ('custom_meshdata' in bpy.context.object)

	def modal(self, context, event):
		if context.area:
			context.area.tag_redraw()

		# removal of callbacks when operator is called again
		if bpy.context.window_manager.showing_vnormals == -1:
			bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
			bpy.context.window_manager.showing_vnormals = 0
			return {"CANCELLED"}
		return {"PASS_THROUGH"}

	def invoke(self, context, event):
		if context.area.type == "VIEW_3D":
			if bpy.context.window_manager.showing_vnormals < 1:
				# operator is called for the first time, start everything
				bpy.context.window_manager.showing_vnormals = 1
				self._handle = bpy.types.SpaceView3D.draw_handler_add(editorfunctions.draw_vertex_normals,
					(self, context), 'WINDOW', 'POST_VIEW')
				context.window_manager.modal_handler_add(self)
				context.area.tag_redraw()
				return {"RUNNING_MODAL"}
			else:
				# operator is called again, stop displaying
				bpy.context.window_manager.showing_vnormals = -1
				return {'RUNNING_MODAL'}
		else:
			self.report({"WARNING"}, "View3D not found, can't run operator")
			return {"CANCELLED"}


# 	Generate:
class generate_vnormals(bpy.types.Operator):
	bl_idname = 'object.generate_vnormals'
	bl_label = 'Generate Normals'
	bl_description = 'Generate Vertex Normals'

	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH" and ('custom_meshdata' in bpy.context.object)
	def execute(self, context):
		editorfunctions.generate_newnormals(self, context)
		return {'FINISHED'}


# 	copy selected normals:
class copy_selectednormals(bpy.types.Operator):
	bl_idname = 'object.copy_selectednormals'
	bl_label = 'Copy Selected'
	bl_description = 'Copy selected normals'

	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH" and ('custom_meshdata' in bpy.context.object)
	def execute(self, context):
		editorfunctions.copy_tempnormalslist(self, context)
		return {'FINISHED'}

# 	paste stored normals:
class paste_selectednormals(bpy.types.Operator):
	bl_idname = 'object.paste_selectednormals'
	bl_label = 'Paste'
	bl_description = 'Paste stored normals'

	@classmethod
	def poll(cls, context):
		return context.mode=="EDIT_MESH" and ('custom_meshdata' in bpy.context.object)
	def execute(self, context):
		#editorfunctions.copy_tempnormalslist(self, context)
		editorfunctions.paste_tempnormalslist(self, context)
		return {'FINISHED'}
		
		
#end Vertex normals editor
#############################

# vertex normals lists
class vert_data(bpy.types.PropertyGroup):
	vpos = bpy.props.FloatVectorProperty(default=(0.0, 0.0, 0.0))
	vnormal = bpy.props.FloatVectorProperty(default=(0.0, 0.0, 0.0))

class face_data(bpy.types.PropertyGroup):
	fcenter = bpy.props.FloatVectorProperty(default=(0.0, 0.0, 0.0))
	fnormal = bpy.props.FloatVectorProperty(default=(0.0, 0.0, 0.0))
	fsgroup = bpy.props.IntProperty(default=0)
	vcount = bpy.props.IntProperty(default=0)
	vdata = bpy.props.CollectionProperty(type=vert_data)

# class for default group display colors
class group_colorsstruct(bpy.types.PropertyGroup):
	colval = bpy.props.FloatVectorProperty(default=(0.0,0.0,0.0))



def initdefaults():

	bpy.types.Object.custom_meshdata = bpy.props.CollectionProperty(
		type=face_data)
	bpy.types.WindowManager.temp_meshdata = bpy.props.CollectionProperty(
		type=face_data)

	bpy.types.WindowManager.group_colors = bpy.props.CollectionProperty(
		type=group_colorsstruct)
		
	bpy.types.WindowManager.vertexnormals_enabled = bpy.props.BoolProperty(
		default=False)
	bpy.types.WindowManager.smoothinggroups_enabled = bpy.props.BoolProperty(
		default=False)
	
	
	bpy.types.WindowManager.tweak_gridsettings_on = bpy.props.BoolProperty(
		default=False)
	

	# Smoothing Groups:
	bpy.types.WindowManager.showing_smoothgroups = bpy.props.IntProperty(
		name="SmoothingGroups",
		default=0)

	bpy.types.WindowManager.sg_selectedgroup = bpy.props.IntProperty(
		default=0,
		max=32,
		min=0)

	bpy.types.WindowManager.sg_showselected = bpy.props.BoolProperty(
		default=False)
	
	
	#Vertex Normals Panel:
	# 	Generate vars:
	bpy.types.WindowManager.vn_generatemode = bpy.props.EnumProperty(
		name="Mode",
		items=(('GROUPS', "Smoothing Groups", " *NOT IMPLEMENTED YET* calculate normals from smoothing groups"),
				('SHARP', "Sharp Edges", " *NOT IMPLEMENTED YET* calculate normals from edges marked as sharp"),
				('ANGLES', "Custom (angle-based)", " *EXPERIMENTAL* custom algorithm that calculates normals + sharp edges from customizable dot product thresholds"),
				('POINT', "Point-Based", "Calculate normals relative to 3d cursor location - good for tree foliage, hair, etc"),
				('UPVECT', "Up Vector", "Calculate normals pointing up - good for ground foliage"),
				('DEFAULT', "Smooth (Default)", "use default normals generated by Blender"),
				),
			default='DEFAULT',
			)
	bpy.types.WindowManager.vn_resetongenerate = bpy.props.BoolProperty(
		default=False)
	bpy.types.WindowManager.vn_genselectiononly = bpy.props.BoolProperty(
		default=False)
	bpy.types.WindowManager.vn_anglebased_dot_face = bpy.props.FloatProperty(
		default=0.86,
		min=-0.99,
		max=0.99,
		step=1,
		)
	bpy.types.WindowManager.vn_anglebased_dot_vert = bpy.props.FloatProperty(
		default=0.86,
		min=-0.99,
		max=0.99,
		step=1,
		)

	# 	Manual Edit vars:
	
	bpy.types.WindowManager.vn_selected_face = bpy.props.IntProperty(
		default=0,
		min=0,
		max=3,)
	bpy.types.WindowManager.vn_realtimeedit = bpy.props.BoolProperty(
		default=False)
	bpy.types.WindowManager.vn_curnormal_disp = bpy.props.FloatVectorProperty(
		default=(0.0,0.0,1.0),
		subtype='TRANSLATION',
		max=1.0,
		min=-1.0,
		update=editorfunctions.vn_set_auto,
		)
	
	# 	Display vars:
	
	bpy.types.WindowManager.showing_vnormals = bpy.props.IntProperty(
		default=0)
	
	bpy.types.WindowManager.vndisp_selectiononly = bpy.props.BoolProperty(
		default=True)

	bpy.types.WindowManager.vn_disp_scale = bpy.props.FloatProperty(
		default=1.0,
		min=0.5,
		max=16.0,
		step=10,
		)
	bpy.types.WindowManager.vn_displaycolor = bpy.props.FloatVectorProperty(
		default=(0.0,1.0,0.0),
		subtype='COLOR',
		max=1.0,
		min=0.0,
		)


def clearvars():
	props = ['vertexnormals_enabled','smoothinggroups_enabled','temp_meshdata','group_colors','tweak_gridsettings_on','showing_smoothgroups','sg_selectedgroup','sg_showselected','showing_vnormals','vn_curnormal_disp','vn_displaycolor','vn_generatemode','vndisp_selectiononly','vn_realtimeedit','vn_resetongenerate','vn_disp_scale','vn_selected_face','vn_genselectiononly']
	for p in props:
		if bpy.context.window_manager.get(p) != None:
			del bpy.context.window_manager[p]
		try:
			x = getattr(bpy.types.WindowManager, p)
			del x
		except:
			pass
	
	if bpy.context.window_manager.get('custom_meshdata') != None:
		del bpy.context.window_manager['custom_meshdata']


def register():
	# Mesh Data
	bpy.utils.register_class(vert_data)
	bpy.utils.register_class(face_data)
	# editor colors:
	bpy.utils.register_class(group_colorsstruct)
	


	################
	#Exporter:
	bpy.utils.register_class(export_menu.ExportFBX)
	
	######################
	#Main Panel:
	bpy.utils.register_class(udk_fbxtools_panel)
	
	bpy.utils.register_class(reset_polydata)
	bpy.utils.register_class(clear_polydata)
	bpy.utils.register_class(enable_smoothinggroups)
	bpy.utils.register_class(enable_vertexnormals)
	bpy.utils.register_class(debug_shownums)
	
	bpy.utils.register_class(tweak_gridsettings)
	
	#######################
	#Smoothing Groups Panel:
	bpy.utils.register_class(set_sgroup)
	bpy.utils.register_class(select_sgroup)
	bpy.utils.register_class(show_smoothgroups)
	
	bpy.utils.register_class(smoothing_groups_panel)
	
	##########################
	#Vertex Normals Panel
	bpy.utils.register_class(reset_vnormals)
	bpy.utils.register_class(get_vnormal)
	bpy.utils.register_class(set_vnormal)
	bpy.utils.register_class(generate_vnormals)
	bpy.utils.register_class(show_vertexnormals)
	bpy.utils.register_class(copy_selectednormals)
	bpy.utils.register_class(paste_selectednormals)
	
	bpy.utils.register_class(vertex_normals_panel)
	
	
	
	initdefaults()


def unregister():
	bpy.utils.unregister_class(vert_data)
	bpy.utils.unregister_class(face_data)
	bpy.utils.unregister_class(group_colorsstruct)
	
	#Export:
	bpy.utils.unregister_class(export_menu.ExportFBX)
	
	bpy.utils.unregister_class(udk_fbxtools_panel)
	
	bpy.utils.unregister_class(reset_polydata)
	bpy.utils.unregister_class(clear_polydata)
	bpy.utils.unregister_class(enable_smoothinggroups)
	bpy.utils.unregister_class(enable_vertexnormals)
	bpy.utils.unregister_class(debug_shownums)
	
	bpy.utils.unregister_class(tweak_gridsettings)
	
	
	#Smoothing Groups:
	bpy.utils.unregister_class(set_sgroup)
	bpy.utils.unregister_class(select_sgroup)
	bpy.utils.unregister_class(show_smoothgroups)
	bpy.utils.unregister_class(smoothing_groups_panel)
	
	#Vertex Normals:
	bpy.utils.unregister_class(reset_vnormals)
	bpy.utils.unregister_class(get_vnormal)
	bpy.utils.unregister_class(set_vnormal)
	bpy.utils.unregister_class(generate_vnormals)
	bpy.utils.unregister_class(show_vertexnormals)
	bpy.utils.unregister_class(copy_selectednormals)
	bpy.utils.unregister_class(paste_selectednormals)
	
	bpy.utils.unregister_class(vertex_normals_panel)
	
	clearvars()


if __name__ == '__main__':
	register()