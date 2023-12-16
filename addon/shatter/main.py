"""
Main file for Shatter tools
"""

import common as common

SH_MAX_STR_LEN = common.MAX_STRING_LENGTH

import xml.etree.ElementTree as et
import bpy
import gzip
import random
import os
import webbrowser
import tempfile
import secrets
import obstacle_db
import segment_export
import segment_import
import segstrate
import extra_tools
import quick_test
import updater
import autogen
import remote_api
import util
import butil
import level_pack_ui
import patcher_ui
import progression_crypto_ui

from bpy.props import (
	StringProperty,
	BoolProperty,
	IntProperty,
	IntVectorProperty,
	FloatProperty,
	FloatVectorProperty,
	EnumProperty,
	PointerProperty,
)

from bpy.types import (
	Panel,
	Menu,
	Operator,
	PropertyGroup,
	AddonPreferences,
)

from bpy_extras.io_utils import ImportHelper

# The name of the test server. If set to false initially, the test server will
# be disabled.
g_process_test_server = True

# :-3
g_got_ricked = False

def get_prefs():
	"""
	Get a reference to the addon preferences
	"""
	
	return bpy.context.preferences.addons["shatter"].preferences

class ExportHelper2:
	"""
	Extended from blender's default ExportHelper to fix some bugs.
	"""
	
	filepath: StringProperty(
		name = "File Path",
		description = "Filepath used for exporting the file",
		maxlen = 1024,
		subtype = 'FILE_PATH',
	)
	
	check_existing: BoolProperty(
		name = "Check Existing",
		description = "Check and warn on overwriting existing files",
		default = True,
		options = {'HIDDEN'},
	)
	
	# subclasses can override with decorator
	# True == use ext, False == no ext, None == do nothing.
	check_extension = True
	
	def invoke(self, context, _event):
		if not self.filepath:
			blend_filepath = context.blend_data.filepath
			if not blend_filepath:
				blend_filepath = "untitled"
			else:
				blend_filepath = os.path.splitext(blend_filepath)[0]
			
			self.filepath = blend_filepath + self.filename_ext
		
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}
	
	def check(self, _context):
		"""
		Custom version of filepath check that fixes issues with two dots in names
		"""
		
		change_ext = False
		
		if self.check_extension is not None and self.check_extension:
			if not self.filepath.endswith(self.filename_ext):
				self.filepath += self.filename_ext
				change_ext = True
		
		return change_ext

class sh_ExportCommon(bpy.types.Operator, ExportHelper2):
	"""
	Common code and values between export types
	"""
	
	sh_meshbake_template: StringProperty(
		name = "Template",
		description = "A relitive or full path to the template file used for baking meshes. If you use APK Editor Studio and the Smash Hit APK is open, the path to the file will be pre-filled",
		default = "",
		subtype = "FILE_PATH",
		maxlen = SH_MAX_STR_LEN,
	)
	
	def __init__(self):
		"""
		Automatic templates.xml detection
		"""
		
		if (not self.sh_meshbake_template):
			self.sh_meshbake_template = segment_export.tryTemplatesPath()

################################################################################
# UNCOMPRESSED
################################################################################
class sh_export(sh_ExportCommon):
	"""
	Uncompressed segment export
	"""
	
	bl_idname = "shatter.export"
	bl_label = "Export Segment"
	
	filename_ext = ".xml.mp3"
	filter_glob = bpy.props.StringProperty(default='*.xml.mp3', options={'HIDDEN'}, maxlen=255)
	
	def execute(self, context):
		segment_export.sh_export_segment(self.filepath, context)
		
		return {"FINISHED"}

def sh_draw_export(self, context):
	self.layout.operator("shatter.export", text="Segment (.xml.mp3)")

################################################################################
# COMPRESSED
################################################################################
class sh_export_gz(sh_ExportCommon):
	"""
	Compressed segment export
	"""
	
	bl_idname = "shatter.export_compressed"
	bl_label = "Export Compressed Segment"
	
	filename_ext = ".xml.gz.mp3"
	filter_glob = bpy.props.StringProperty(default='*.xml.gz.mp3', options={'HIDDEN'}, maxlen=255)
	
	def execute(self, context):
		segment_export.sh_export_segment(self.filepath, context, True)
		
		return {"FINISHED"}

def sh_draw_export_gz(self, context):
	self.layout.operator("shatter.export_compressed", text="Compressed Segment (.xml.gz.mp3)")

################################################################################
# AUTO EXPORT
################################################################################
class sh_export_auto(bpy.types.Operator):
	"""
	Auto find APK path and use level/room/segment name to export
	"""
	
	bl_idname = "shatter.export_auto"
	bl_label = "Export to APK"
	
	def execute(self, context):
		segment_export.sh_export_segment(None, context, get_prefs().auto_export_compressed)
		
		return {"FINISHED"}

def sh_draw_export_auto(self, context):
	self.layout.operator("shatter.export_auto", text="Shatter: Export to APK")

################################################################################
# AUTO EXPORT ALL SCENES
################################################################################
class sh_export_all_auto(bpy.types.Operator):
	"""
	Auto find APK path and use level/room/segment name to export for all scenes
	in this blender file
	"""
	
	bl_idname = "shatter.export_all_auto"
	bl_label = "Export all to APK"
	
	def execute(self, context):
		segment_export.sh_export_all_segments(context, get_prefs().auto_export_compressed)
		
		return {"FINISHED"}

def sh_draw_export_all_auto(self, context):
	self.layout.operator("shatter.export_all_auto", text="Shatter: Export All to APK")

################################################################################
# TESTSERVER
################################################################################
class sh_export_test(Operator):
	"""
	Compressed segment export
	"""
	
	bl_idname = "shatter.export_test_server"
	bl_label = "Export segment to test server"
	
	def execute(self, context):
		segment_export.sh_export_segment(None, context, False, True)
		
		return {"FINISHED"}

def sh_draw_export_test(self, context):
	self.layout.operator("shatter.export_test_server", text="Shatter: Quick Test Server")

class sh_import(bpy.types.Operator, ImportHelper):
	"""
	Import for uncompressed segments
	"""
	
	bl_idname = "shatter.import"
	bl_label = "Import Segment"
	
	check_extension = False
	filename_ext = ".xml.mp3"
	filter_glob = bpy.props.StringProperty(default='*.xml.mp3', options={'HIDDEN'}, maxlen=255)
	
	def execute(self, context):
		return segment_import.sh_import_segment(self.filepath, context)

def sh_draw_import(self, context):
	self.layout.operator("shatter.import", text="Segment (.xml.mp3)")

class sh_import_gz(bpy.types.Operator, ImportHelper):
	"""
	Import for compressed segments
	"""
	
	bl_idname = "shatter.import_gz"
	bl_label = "Import Compressed Segment"
	
	check_extension = False
	filename_ext = ".xml.gz.mp3"
	filter_glob = bpy.props.StringProperty(default='*.xml.gz.mp3', options={'HIDDEN'}, maxlen=255)
	
	def execute(self, context):
		return segment_import.sh_import_segment(self.filepath, context, True)

def sh_draw_import_gz(self, context):
	self.layout.operator("shatter.import_gz", text="Compressed Segment (.xml.gz.mp3)")

class sh_static_segstrate(bpy.types.Operator, ImportHelper):
	"""
	Allows you to permantently lock an APK file using segstrate. You won't be
	able to add any new segments after this! Segstrate makes it harder to copy
	any segments in your mod, but it is still possible for someone with
	exprience. To use it, select the main folder of the mod (e.g. the one where
	you can see assets, lib, res, etc.) and then click the main button.
	"""
	
	bl_idname = "shatter.segstrate_static"
	bl_label = "Lock APK with Segstrate"
	
	agreement: BoolProperty(
		name = "Agree to notice (hover to see)",
		description = "Locking your APK will make you unable to import or export any segments to the APK. Please only use this when you are making a copy of the APK that you want to distribute.",
		default = False,
	)
	
	def execute(self, context):
		if (self.agreement):
			context.window.cursor_set('WAIT')
			segstrate.setup_apk(self.filepath, False)
			context.window.cursor_set('DEFAULT')
		else:
			butil.show_message("Segstrate error", "The agreement has not been accepted and the protection has not been preformed.")
		
		return {"FINISHED"}

class sh_rebake_meshes(bpy.types.Operator, ImportHelper):
	"""
	Rebake many meshes from a selected folder
	"""
	
	bl_idname = "shatter.rebake_meshes"
	bl_label = "Rebake multipule meshes"
	
	def execute(self, context):
		assets = butil.find_apk()
		
		context.window.cursor_set('WAIT')
		extra_tools.rebake_all(self.filepath, f"{assets}/templates.xml.mp3" if assets else None)
		context.window.cursor_set('DEFAULT')
		
		return {"FINISHED"}

## EDITOR
## The following things are more related to the editor and are not specifically
## for exporting or importing segments.

class sh_SceneProperties(PropertyGroup):
	"""
	Segment (scene) properties
	"""
	
	sh_level: StringProperty(
		name = "Level",
		description = "The name of the checkpoint that this segment belongs to.",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_room: StringProperty(
		name = "Room",
		description = "The name of the room that this segment belongs to.",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_segment: StringProperty(
		name = "Segment",
		description = "The name of this segment",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_len: FloatVectorProperty(
		name = "Size",
		description = "Segment size (Width, Height, Depth). Hint: Last paramater changes the length (depth) of the segment",
		subtype = "XYZ",
		default = (12.0, 10.0, 8.0), 
	)
	
	sh_auto_length: BoolProperty(
		name = "Auto length",
		description = "Automatically determine the length of the segment based on the furthest object from the origin.",
		default = False,
	)
	
	sh_box_bake_mode: EnumProperty(
		name = "Box bake mode",
		description = "This will control how the boxes should be exported. Hover over each option for an explation of how it works",
		items = [
			('Mesh', "Mesh", "Exports a .mesh file alongside the segment for showing visible box geometry"),
			('StoneHack', "Obstacle", "Adds a custom obstacle named 'stone' for every box that attempts to simulate stone. Only colour is supported: there are no textures"),
			('None', "None", "Don't do anything related to baking stone; only exports the raw segment data"),
		],
		default = "Mesh"
	)
	
	sh_template: StringProperty(
		name = "Template",
		description = "The template paramater that is passed for the entire segment",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_default_template: StringProperty(
		name = "Default template",
		description = "The base name of the template to use when no template is specified for an entity. Format: boxes 🡒 '{basename}', obstacles 🡒 '{basename}_glass', obstacles starting with 'score' 🡒 '{basename}_st', segment 🡒 '{basename}_s'",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_softshadow: FloatProperty(
		name = "Soft shadow",
		description = "Opacity of soft shadow on dynamic objects",
		default = 0.6,
		min = 0.0,
		max = 1.0
	)
	
	sh_vrmultiply: FloatProperty(
		name = "Segment strech",
		description = "This option tries to strech the segment's depth to make more time between obstacles. The intent is to allow it to be played in Smash Hit VR easier and without modifications to the segment",
		default = 1.0,
	)
	
	sh_light_left: FloatProperty(
		name = "Left",
		description = "Light going on to the left side of boxes",
		default = 1.0,
		min = 0.0,
		max = 1.0,
	)
	
	sh_light_right: FloatProperty(
		name = "Right",
		description = "Light going on to the right side of boxes",
		default = 1.0,
		min = 0.0,
		max = 1.0,
	)
	
	sh_light_top: FloatProperty(
		name = "Top",
		description = "Light going on to the top side of boxes",
		default = 1.0,
		min = 0.0,
		max = 1.0,
	)
	
	sh_light_bottom: FloatProperty(
		name = "Bottom",
		description = "Light going on to the bottom side of boxes",
		default = 1.0,
		min = 0.0,
		max = 1.0,
	)
	
	sh_light_front: FloatProperty(
		name = "Front",
		description = "Light going on to the front side of boxes",
		default = 1.0,
		min = 0.0,
		max = 1.0,
	)
	
	sh_light_back: FloatProperty(
		name = "Back",
		description = "Light going on to the back side of boxes",
		default = 1.0,
		min = 0.0,
		max = 1.0,
	)
	
	sh_menu_segment: BoolProperty(
		name = "Menu segment mode",
		description = "Treats the segment like it will appear on the main menu. Bakes faces that cannot be seen by the player",
		default = False
	)
	
	sh_ambient_occlusion: BoolProperty(
		name = "Ambient occlusion",
		description = "Enables ambient occlusion (per-vertex lighting)",
		default = True
	)
	
	sh_lighting: BoolProperty(
		name = "Lighting",
		description = "Enables some lighting features when baking the mesh",
		default = False
	)
	
	sh_drm_disallow_import: BoolProperty(
		name = "Disallow import",
		description = "This will disallow importing the exported segment. It can very easily be bypassed, but might prevent a casual user from editing your segment without asking. Please use this feature wisely and consider providing Blender files for people who ask nicely",
		default = False
	)
	
	sh_lighting_ambient: FloatVectorProperty(
		name = "Ambient",
		description = "Colour and intensity of the ambient light",
		subtype = "COLOR_GAMMA",
		default = (0.0, 0.0, 0.0), 
		soft_min = 0.0,
		soft_max = 1.0,
	)
	
	sh_stone_obstacle_name: StringProperty(
		name = "Stone obstacle name",
		description = "Name of the obstacle to use for stone",
		default = "stone",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_legacy_colour_model: BoolProperty(
		name = "Legacy colour model",
		description = "Uses the colour inheritance model from SHBT v0.9x, which can avoid extra effort when using the stone hack without templates",
		default = False
	)
	
	sh_legacy_colour_default: FloatVectorProperty(
		name = "Default colour",
		description = "The default colour for all (non-visible marked) boxes when using the legacy colour model",
		subtype = "COLOR_GAMMA",
		default = (1.0, 1.0, 1.0), 
		soft_min = 0.0,
		soft_max = 1.0,
	)
	
	sh_fog_colour_top: FloatVectorProperty(
		name = "Top fog",
		description = "Fog colour for quick test. While this does use the fogcolor xml attribute, this property cannot be inherited from templates or used like a normal property",
		subtype = "COLOR_GAMMA",
		default = (1.0, 1.0, 1.0), 
		soft_min = 0.0,
		soft_max = 1.0,
	)
	
	sh_fog_colour_bottom: FloatVectorProperty(
		name = "Bottom fog",
		description = "Fog colour for quick test. While this does use the fogcolor xml attribute, this property cannot be inherited from templates or used like a normal property",
		subtype = "COLOR_GAMMA",
		default = (0.0, 0.0, 0.0),
		soft_min = 0.0,
		soft_max = 1.0,
	)
	
	sh_music: StringProperty(
		name = "Music track",
		description = "Name of the music file to play in quick test. The track must be in the apk. Default is to choose a random track",
		default = "",
	)
	
	sh_reverb: StringProperty(
		name = "Reverb",
		description = "Reverb parameters in quick test. No one knows what these do ‾\\_o_/‾",
		default = "",
	)
	
	sh_echo: StringProperty(
		name = "Echo",
		description = "Echo parameters in quick test. No one knows what these do ‾\\_o_/‾",
		default = "",
	)
	
	sh_rotation: StringProperty(
		name = "Rotation",
		description = "The rotation of the room in quick test. The first param is required and is the amount of rotations to do, the second is optional and is the angle of the rotations in radians",
		default = "",
	)
	
	sh_particles: EnumProperty(
		name = "Particles",
		description = "The particles that appear when looking at the stage in quick test",
		items = (
			("None", "None", ""),
			("starfield", "Star feild", ""),
			("lowrising", "Low rising 1", ""),
			("lowrising2", "Low rising 2", ""),
			("sidesrising", "Sides rising", ""),
			("fallinglite", "Falling lite", ""),
			("bubbles", "Bubbles", ""),
			("dustyfalling", "Dusty falling", ""),
		),
		default = "None",
	)
	
	sh_difficulty: FloatProperty(
		name = "Difficulty",
		description = "Sets the difficulty level of the room",
		default = 0.0,
		min = 0.0,
		max = 1.0,
	)
	
	sh_gravity: FloatProperty(
		name = "Gravity",
		description = "The amount of gravity to use in quick test",
		default = 1.0,
	)
	
	sh_extra_code: StringProperty(
		name = "Extra code",
		description = "Extra code to include the in room file. Multipule statements can be seperated by ';'.",
		default = "",
	)
	
	sh_room_length: IntProperty(
		name = "Room length",
		description = "The length of the room in quick test",
		default = 200,
        	min = 1,
	)

# Object (box/obstacle/powerup/decal/water) properties

class sh_EntityProperties(PropertyGroup):
	
	sh_type: EnumProperty(
		name = "Kind",
		description = "The kind of object that the currently selected object should be treated as.",
		items = [
			('BOX', "Box", "", "MESH_CUBE", 0),
			('OBS', "Obstacle", "", "NODE_MATERIAL", 1),
			('DEC', "Decal", "", "TEXTURE", 2),
			('POW', "Power-up", "", "LIGHT_SUN", 3),
			('WAT', "Water", "", "MATFLUID", 4),
		],
		default = "BOX"
	)
	
	sh_template: StringProperty(
		name = "Template",
		description = "The template for the obstacle/box (see templates.xml), remember that this can be easily overridden per obstacle/box",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_use_chooser: BoolProperty(
		name = "Use obstacle chooser",
		description = "Use the obstacle chooser instead of typing the name by hand",
		default = False,
	)
	
	sh_obstacle: StringProperty(
		name = "Obstacle",
		description = "Type of obstacle to be used (as a file name string)",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_obstacle_chooser: EnumProperty(
		name = "Obstacle",
		description = "Type of obstacle to be used (pick a name)",
		items = obstacle_db.OBSTACLES,
		default = "scoretop",
	)
	
	sh_powerup: EnumProperty(
		name = "Power-up",
		description = "The type of power-up that will appear",
		items = [
			('ballfrenzy', "Ball Frenzy", "Allows the player infinite balls for some time", "LIGHTPROBE_GRID", 0),
			('slowmotion', "Slow Motion", "Slows down the game", "MOD_TIME", 1),
			('nitroballs', "Nitro Balls", "Turns balls into exposlives for a short period of time", "PROP_OFF", 2),
			None,
			('barrel', "Barrel", "Creates a large explosion which breaks glass (lefover from beta versions)", "EXPERIMENTAL", 3),
			None,
			('multiball', "Multi-ball*", "*Does not work anymore. Old power up that would enable five-ball multiball"),
			('freebie', "Freebie*", "*Does not work anymore. Old power up found in binary strings but no known usage"),
			('antigravity', "Anti-gravity*", "*Does not work anymore. Old power up that probably would have reversed gravity"),
			('rewind', "Rewind*", "*Does not work anymore. Old power up that probably would have reversed time"),
			('sheild', "Sheild*", "*Does not work anymore. Old power up that probably would have protected the player"),
			('homing', "Homing*", "*Does not work anymore. Old power up that probably would have homed to obstacles"),
			('life', "Life*", "*Does not work anymore. Old power up that gave the player a life"),
			('balls', "Balls*", "*Does not work anymore. Old power up that gave the player ten balls"),
		],
		default = "ballfrenzy",
	)
	
	sh_export: BoolProperty(
		name = "Export object",
		description = "If the object should be exported to the XML at all. Change \"hidden\" if you'd like it to be hidden but still present in the exported file",
		default = True,
	)
	
	sh_hidden: BoolProperty(
		name = "Hidden",
		description = "Controls if the entity will show in the official level editor. This is basically useless but included for completeness",
		default = False,
	)
	
	sh_mode: EnumProperty(
		name = "Mode",
		options = {"ENUM_FLAG"},
		description = "The game modes in which this obstacle should appear",
		items = [
			('training', "Training", "Obstacle should appear in Training mode", 1),
			('classic', "Classic and Zen", "Obstacle should appear in Classic and Zen modes", 2),
			('expert', "Mayhem", "Obstacle should appear in Mayhem mode", 4),
			('versus', "Versus", "Obstacle should appear in Versus mode", 16),
			('coop', "Co-op", "Obstacle should appear in Co-op mode", 32),
		],
		default = {'training', 'classic', 'expert', 'versus', 'coop'},
	)
	
	sh_difficulty: FloatVectorProperty(
		name = "Difficulty",
		description = "The range of difficulty values for which this entity will appear. Difficulty is different than game modes, and is mainly used in Endless Mode to include or exclude obstacle based on a value set per room (using mgSetDifficulty) indicating how hard the room should be. As an example, this is used to exclude crystals in later levels in the Endless mode without creating entirely new segments",
		default = (0.0, 1.0),
		min = 0.0,
		max = 1.0,
		size = 2,
	)
	
	##################
	# Mesh properties
	##################
	
	sh_visible: BoolProperty(
		name = "Visible",
		description = "If the box will appear in the exported mesh",
		default = True
	)
	
	sh_use_multitile: BoolProperty(
		name = "Tile per-side",
		description = "Specifiy a colour for each parallel pair of faces on the box",
		default = False,
	)
	
	sh_tile: IntProperty(
		name = "Tile",
		description = "The texture that will appear on the surface of the box or decal",
		default = 0,
		min = 0,
		max = 63
	)
	
	sh_tile1: IntProperty(
		name = "Right Left",
		description = "The texture that will appear on the surface of the box or decal",
		default = 0,
		min = 0,
		max = 63
	)
	
	sh_tile2: IntProperty(
		name = "Top Bottom",
		description = "The texture that will appear on the surface of the box or decal",
		default = 0,
		min = 0,
		max = 63
	)
	
	sh_tile3: IntProperty(
		name = "Front Back",
		description = "The texture that will appear on the surface of the box or decal",
		default = 0,
		min = 0,
		max = 63
	)
	
	sh_tilerot: IntVectorProperty(
		name = "Tile orientation",
		description = "Orientation of the tile, where 0 is facing up",
		default = (0, 0, 0), 
		min = 0,
		max = 3,
	) 
	
	sh_tilesize: FloatVectorProperty(
		name = "Tile size",
		description = "The appearing size of the tiles on the box when exported. In RightLeft, TopBottom, FrontBack",
		default = (1.0, 1.0, 1.0), 
		soft_min = 0.0,
		soft_max = 128.0,
		size = 3
	) 
	
	########################
	# Back to normal things
	########################
	
	sh_decal: IntProperty(
		name = "Decal",
		description = "The image ID for the decal (negitive numbers are doors)",
		default = 1,
		min = -4,
		max = 63
	)
	
	sh_reflective: BoolProperty(
		name = "Reflective",
		description = "If this box should show reflections",
		default = False
	)
	
	#############
	# Paramaters
	#############
	
	sh_param0: StringProperty(
		name = "param0",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param1: StringProperty(
		name = "param1",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param2: StringProperty(
		name = "param2",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param3: StringProperty(
		name = "param3",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param4: StringProperty(
		name = "param4",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param5: StringProperty(
		name = "param5",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param6: StringProperty(
		name = "param6",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param7: StringProperty(
		name = "param7",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param8: StringProperty(
		name = "param8",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param9: StringProperty(
		name = "param9",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param10: StringProperty(
		name = "param10",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	sh_param11: StringProperty(
		name = "param11",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	###############
	# Other values
	###############
	
	sh_havetint: BoolProperty(
		name = "Decal colourisation",
		description = "Changes the tint (colourisation) of the decal",
		default = False
	)
	
	sh_use_multitint: BoolProperty(
		name = "Colour per-side",
		description = "Specifiy a colour for each parallel pair of faces on the box",
		default = False,
	)
	
	sh_tint: FloatVectorProperty(
		name = "Colour",
		description = "The colour to be used for tinting, colouring and mesh data",
		subtype = "COLOR_GAMMA",
		default = (1.0, 1.0, 1.0, 1.0), 
		size = 4,
		soft_min = 0.0,
		soft_max = 1.0,
	)
	
	sh_tint1: FloatVectorProperty(
		name = "Right Left",
		description = "The colour to be used for tinting, colouring and mesh data",
		subtype = "COLOR_GAMMA",
		default = (1.0, 1.0, 1.0, 1.0), 
		size = 4,
		soft_min = 0.0,
		soft_max = 1.0,
	)
	
	sh_tint2: FloatVectorProperty(
		name = "Top Bottom",
		description = "The colour to be used for tinting, colouring and mesh data",
		subtype = "COLOR_GAMMA",
		default = (1.0, 1.0, 1.0, 1.0), 
		size = 4,
		soft_min = 0.0,
		soft_max = 1.0,
	)
	
	sh_tint3: FloatVectorProperty(
		name = "Front Back",
		description = "The colour to be used for tinting, colouring and mesh data",
		subtype = "COLOR_GAMMA",
		default = (1.0, 1.0, 1.0, 1.0), 
		size = 4,
		soft_min = 0.0,
		soft_max = 1.0,
	)
	
	sh_gradientraw: StringProperty(
		name = "Linear gradient",
		description = "(\"A \"?) A.x A.y A.z  B.x B.y B.z  A.r A.g A.b  B.r B.g B.b. Normally relative where -1 and 1 are the extremes but prefix with 'A ' to get absolute mode",
		default = "",
	)
	
	sh_graddir: EnumProperty(
		name = "Direction",
		description = "The game modes in which this obstacle should appear",
		items = [
			('none', "None", "The regular box colour will be used"),
			('relative', "Relative points", "Pick two points for each axis that are in [-1, 1] and scale with the box"),
			('absolute', "Absolute points", "Pick two points that are relative to the scene"),
			('right', "To right", ""),
			('left', "To left", ""),
			('top', "To top", ""),
			('bottom', "To bottom", ""),
			('front', "To front", ""),
			('back', "To back", ""),
		],
		default = "none",
	)
	
	sh_gradpoint1: FloatVectorProperty(
		name = "Point A",
		description = "The first gradient colour",
		subtype = "XYZ",
		default = (0.0, 0.0, 0.0),
	)
	
	sh_gradcolour1: FloatVectorProperty(
		name = "Colour A",
		description = "The colour for point A",
		subtype = "COLOR_GAMMA",
		default = (1.0, 1.0, 1.0), 
		size = 3,
		soft_min = 0.0,
		soft_max = 1.0,
	)
	
	sh_gradpoint2: FloatVectorProperty(
		name = "Point B",
		description = "The first gradient colour",
		subtype = "XYZ",
		default = (0.0, 0.0, 0.0),
	)
	
	sh_gradcolour2: FloatVectorProperty(
		name = "Colour B",
		description = "The colour for point B",
		subtype = "COLOR_GAMMA",
		default = (1.0, 1.0, 1.0), 
		size = 3,
		soft_min = 0.0,
		soft_max = 1.0,
	)
	
	sh_blend: FloatProperty(
		name = "Blend mode",
		description = "How the colour of the decal and the existing colour will be blended. 1 = normal, 0 = added or numbers in between",
		default = 1.0,
		min = 0.0,
		max = 1.0,
	)
	
	sh_size: FloatVectorProperty(
		name = "Size",
		description = "The size of the object when exported",
		default = (1.0, 1.0), 
		min = 0.0,
		max = 256.0,
		size = 2,
	)
	
	sh_glow: FloatProperty(
		name = "Glow",
		description = "The intensity of the light in \"watts\"; zero if this isn't a light",
		default = 0.0,
		min = 0.0,
		max = 1000.0,
	)

class sh_AddonPreferences(AddonPreferences):
	bl_idname = "shatter"
	
	## General ##
	default_assets_path: StringProperty(
		name = "Default assets path",
		description = "The path to your Smash Hit assets folder, if you want to override the default automatic APK finding",
		subtype = "DIR_PATH",
		default = "",
	)
	
	enable_segment_warnings: BoolProperty(
		name = "Enable export and import warnings",
		description = "Export and import warnings can warn you about possible issues that might result in odd or unexpected behaviour in Smash Hit",
		default = True,
	)
	
	auto_export_compressed: BoolProperty(
		name = "Compress exported segments in auto export",
		description = "Enables segment compression when using the 'Export to APK' option. Smash Hit does not compress segments by default in 1.5.x and later",
		default = True,
	)
	
	resolve_templates: BoolProperty(
		name = "Resolve templates at export time",
		description = "Solves templates when a segment is exported. This avoids the need for adding used templates to templates.xml, but makes the filesize larger and the XML file less readable",
		default = False,
	)
	
	show_gradient_raw: BoolProperty(
		name = "Enable linear gradient editor",
		description = "Always show the box to edit linear gradients, instead of just when a box has one already set",
		default = True,
	)
	
	compact_ui: BoolProperty(
		name = "Compact UI mode",
		description = "Avoids drawing any excessive UI elements that would make the UI larger than needed",
		default = False,
	)
	
	## Network ##
	enable_update_notifier: BoolProperty(
		name = "Enable update checking",
		description = "Enables checking for updates. This will try to contact github, which may pose a privacy risk",
		default = True,
	)
	
	enable_auto_update: BoolProperty(
		name = "Enable automatic updates",
		description = "Automatically downloads and installs the newest version of the addon",
		default = True,
	)
	
	updater_channel: EnumProperty(
		name = "Update freqency",
		description = "This controls how frequently you will recieve updates, tweaks and new features. Faster updates might be buggier and break your workflow but contain better features, while slower updates will give a better exprience without newer features",
		items = [
			('stable', "Normal", "Contains new updates and features as soon as they are available, but might also break sometimes."),
			('updatertest', "Updater test", "A testing channel. This doesn't get real updates."),
		],
		default = "stable",
	)
	
	enable_quick_test_server: BoolProperty(
		name = "Enable quick test server",
		description = "Enables the quick test server. This will create a local http server using python, which might pose a security risk",
		default = True,
	)
	
	## Protection options ##
	force_disallow_import: BoolProperty(
		name = "Always disallow import",
		description = "Enabling this option will force every segment to have the \"disallow import\" flag set, even if you did not configure it via the obstacle panel. Please note that marking segments with this flag does not prevent someone bypassing it",
		default = False,
	)
	
	segment_encrypt: BoolProperty(
		name = "Obfuscate exported segments (alpha)",
		description = "This will obfuscate segments using a very basic implementation of the XTEA-CTR cipher. THIS IS NOT INTENDED TO BE SECURE OR CONFIDENTIAL IN ANY WAY. Note: In the future there may be mods that allow loading encrypted segments and providing some protection against copying, but this does not exist yet and so this is only for development right now",
		default = False,
	)
	
	# Yes, I technically imply that this is not a "password" even though it is.
	# But really I don't want ppl to use their one password for everything (ugh)
	# in this. Maybe it would be better to switch to a keyfile of some kind?
	segment_encrypt_password: StringProperty(
		name = "Keyphrase",
		description = "The unique keyphrase to obfuscate segments with. This should be a mix of random symbols, similar to a password, but does not need to be memorable",
		# subtype = "PASSWORD",
		default = "",
	)
	
	def draw(self, context):
		main = self.layout
		
		ui = butil.UIDrawingHelper(context, self.layout, self)
		
		ui.region("PREFERENCES", "General options")
		ui.prop("default_assets_path")
		ui.prop("enable_segment_warnings")
		ui.prop("auto_export_compressed")
		ui.prop("resolve_templates")
		ui.prop("show_gradient_raw")
		ui.prop("compact_ui")
		ui.end()
		
		ui.region("WORLD", "Network features")
		ui.prop("enable_quick_test_server")
		ui.prop("enable_update_notifier")
		ui.prop("updater_channel")
		
		if (self.enable_update_notifier):
			ui.prop("enable_auto_update")
		
		ui.end()
		
		ui.region("LOCKED", "Protection")
		ui.prop("force_disallow_import")
		ui.prop("segment_encrypt")
		
		if (self.segment_encrypt):
			ui.prop("segment_encrypt_password")
			ui.op("shatter.obfuscation_randomise_keyphrase")
			ui.warn("Segment obfuscation is not supported ingame. Developers only!")
		
		ui.end()
		
		ui.region("INFO", "About Shatter")
		ui.op("shatter.open_discord")
		ui.op("shatter.open_credits_page")
		ui.op("shatter.open_privacy_page")
		
		if (g_got_ricked):
			ui.region("INFO", "Trolled !!!", new = False)
			ui.label("Anyway, I hope you are doing well in life :)")
			ui.label("-- Knot126")
			ui.end()
		
		ui.end()

class RandomiseKeyphrase(Operator):
	bl_idname = "shatter.obfuscation_randomise_keyphrase"
	bl_label = "Randomise keyphrase"
	
	def execute(self, context):
		p = get_prefs()
		p.segment_encrypt_password = util.randpw()
		return {"FINISHED"}

class sh_SegmentPanel(Panel):
	bl_label = "Smash Hit Scene"
	bl_idname = "OBJECT_PT_segment_panel"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Scene"
	
	@classmethod
	def poll(self, context):
		return True
	
	def draw(self, context):
		layout = self.layout
		scene = context.scene
		sh_properties = scene.sh_properties
		
		sub = layout.box()
		sub.label(text = "Location", icon = "NODE")
		sub.prop(sh_properties, "sh_level")
		sub.prop(sh_properties, "sh_room")
		sub.prop(sh_properties, "sh_segment")
		
		sub = layout.box()
		sub.label(text = "Segment data", icon = "SCENE_DATA")
		sub.prop(sh_properties, "sh_auto_length", toggle = 1)
		if (not sh_properties.sh_auto_length):
			sub.prop(sh_properties, "sh_len")
		sub.prop(sh_properties, "sh_box_bake_mode")
		sub.prop(sh_properties, "sh_template")
		sub.prop(sh_properties, "sh_default_template")
		sub.prop(sh_properties, "sh_softshadow")
		sub.prop(sh_properties, "sh_vrmultiply")
		
		bake_mode = sh_properties.sh_box_bake_mode
		
		if (bake_mode == "Mesh"):
			# Lighting
			sub = layout.box()
			sub.label(text = "Light", icon = "LIGHT")
			# sub.prop(sh_properties, "sh_basic_lighting")
			#if (sh_properties.sh_basic_lighting):
			if (True):
				sub.prop(sh_properties, "sh_light_right")
				sub.prop(sh_properties, "sh_light_left")
				sub.prop(sh_properties, "sh_light_top")
				sub.prop(sh_properties, "sh_light_bottom")
				sub.prop(sh_properties, "sh_light_front")
				sub.prop(sh_properties, "sh_light_back")
			
			sub.prop(sh_properties, "sh_lighting")
			if (sh_properties.sh_lighting):
				sub.prop(sh_properties, "sh_lighting_ambient")
			
			# Mesh settings
			sub = layout.box()
			sub.label(text = "Meshes", icon = "MESH_DATA")
			sub.prop(sh_properties, "sh_menu_segment")
			sub.prop(sh_properties, "sh_ambient_occlusion")
		
		if (bake_mode == "StoneHack"):
			sub = layout.box()
			sub.label(text = "Stone", icon = "UV_DATA")
			sub.prop(sh_properties, "sh_stone_obstacle_name")
			sub.prop(sh_properties, "sh_legacy_colour_model")
			if (sh_properties.sh_legacy_colour_model):
				sub.prop(sh_properties, "sh_legacy_colour_default")
		
		# Quick test
		if (bpy.context.preferences.addons["shatter"].preferences.enable_quick_test_server):
			sub = layout.box()
			sub.label(text = "Quick test", icon = "AUTO")
			sub.prop(sh_properties, "sh_fog_colour_top")
			sub.prop(sh_properties, "sh_fog_colour_bottom")
			sub.prop(sh_properties, "sh_room_length")
			sub.prop(sh_properties, "sh_gravity")
			sub.prop(sh_properties, "sh_music")
			sub.prop(sh_properties, "sh_echo")
			sub.prop(sh_properties, "sh_reverb")
			sub.prop(sh_properties, "sh_rotation")
			sub.prop(sh_properties, "sh_particles")
			sub.prop(sh_properties, "sh_difficulty")
			sub.prop(sh_properties, "sh_extra_code")
			sub.label(text = f"Your IP: {util.get_local_ip()}")
		
		# DRM
		if (not bpy.context.preferences.addons["shatter"].preferences.force_disallow_import):
			sub = layout.box()
			sub.label(text = "Protection", icon = "LOCKED")
			sub.prop(sh_properties, "sh_drm_disallow_import")
		
		layout.separator()

class sh_ItemPropertiesPanel(Panel):
	bl_label = "Smash Hit Item"
	bl_idname = "OBJECT_PT_obstacle_panel"
	bl_space_type = "VIEW_3D"   
	bl_region_type = "UI"
	bl_category = "Item"
	bl_context = "objectmode"
	
	@classmethod
	def poll(self, context):
		return context.object is not None
	
	def draw(self, context):
		layout = self.layout
		object = context.object
		sh_properties = object.sh_properties
		
		ui = butil.UIDrawingHelper(context, layout, sh_properties, compact = get_prefs().compact_ui)
		
		# All objects will have all properties, but only some will be used for
		# each of obstacle there is.
		t = ui.prop("sh_type", text = "")
		ui.prop("sh_template")
		
		if (t == "BOX"):
			ui.prop("sh_visible", disabled = not not ui.get("sh_template"))
			
			# silly little loop wrapper :-3
			for x in ["tint", "tile"]:
				word = {"tint": "Colour", "tile": "Tile"}[x]
				
				ui.region(
					{"tint": "COLOR", "tile": "TEXTURE"}[x],
					word,
				)
				
				if (ui.get(f"sh_use_multi{x}")):
					ui.prop(f"sh_use_multi{x}", text = "Per-axis", text_compact = f"Per-axis {word.lower()}", use_button = True)
					ui.prop(f"sh_{x}1")
					ui.prop(f"sh_{x}2")
					ui.prop(f"sh_{x}3")
				else:
					ui.prop(f"sh_use_multi{x}", text = "Uniform", text_compact = f"Uniform {word.lower()}", use_button = True)
					ui.prop(f"sh_{x}")
				
				ui.end()
			
			if (get_prefs().show_gradient_raw or ui.get("sh_graddir") != "none"):
				ui.region("NODE_TEXTURE", "Gradient")
				v = ui.prop("sh_graddir", text_compact = "Gradient direction")
				
				if (v == "none"):
					pass
				elif (v == "relative" or v == "absolute"):
					ui.prop("sh_gradpoint1")
					ui.prop("sh_gradcolour1")
					ui.prop("sh_gradpoint2")
					ui.prop("sh_gradcolour2")
				else:
					ui.prop("sh_gradcolour1", text = "From", text_compact = "Grad from")
					ui.prop("sh_gradcolour2", text = "To", text_compact = "Grad to")
				
				ui.end()
			
			if (context.scene.sh_properties.sh_lighting):
				ui.region("LIGHT", "Light")
				ui.prop("sh_glow")
				ui.end()
			
			ui.region("GRAPH", "Tile transforms")
			ui.prop("sh_tilesize")
			ui.prop("sh_tilerot")
			ui.end()
			
			ui.prop("sh_reflective")
		elif (t == "OBS"):
			ui.region("COPY_ID", "Type")
			ui.prop("sh_use_chooser", use_button = True)
			ui.prop("sh_obstacle_chooser" if ui.get("sh_use_chooser") else "sh_obstacle", text = "", text_compact = "Type")
			ui.end()
			
			ui.region("HIDE_OFF", "Visibility")
			ui.prop("sh_mode")
			ui.prop("sh_difficulty")
			ui.end()
			
			ui.region("SETTINGS", "Parameters", force = True)
			for i in range(12):
				ui.prop(f"sh_param{i}", text = "", disabled = (i == 0) and (ui.get("sh_template") != ""))
			ui.end()
		elif (t == "DEC"):
			ui.region("TEXTURE", "Sprite")
			ui.prop("sh_decal")
			ui.end()
			
			ui.region("COLOR", "Colour")
			ui.prop("sh_havetint", use_button = True, icon = "COLOR")
			if (ui.get("sh_havetint")):
				ui.prop("sh_tint")
			ui.prop("sh_blend")
			ui.end()
			
			if (context.object.dimensions[1] == 0.0 and context.object.dimensions[2] == 0.0):
				ui.region("SETTINGS", "Size")
				ui.prop("sh_size")
				ui.end()
			
			ui.region("HIDE_OFF", "Visibility")
			ui.prop("sh_difficulty")
			ui.end()
		elif (t == "POW"):
			ui.prop("sh_powerup")
			ui.prop("sh_difficulty")
		elif (t == "WAT"):
			pass
		
		ui.prop("sh_hidden")
		ui.prop("sh_export")

class sh_CreateBox(Operator):
	"""
	Operator to create a box
	"""
	
	bl_idname = "shatter.create_box"
	bl_label = "Create box"
	
	def execute(self, context):
		o = butil.add_box((0,0,0), (1,1,1))
		
		return {"FINISHED"}

class sh_CreateObstacle(Operator):
	"""
	Operator to create a obstacle
	"""
	
	bl_idname = "shatter.create_obstacle"
	bl_label = "Create obstacle"
	
	def execute(self, context):
		o = butil.add_empty()
		o.sh_properties.sh_type = "OBS"
		
		return {"FINISHED"}

class sh_CreateDecal(Operator):
	"""
	Operator to create a decal
	"""
	
	bl_idname = "shatter.create_decal"
	bl_label = "Create decal"
	
	def execute(self, context):
		o = butil.add_empty()
		o.sh_properties.sh_type = "DEC"
		
		return {"FINISHED"}

class sh_CreatePowerup(Operator):
	"""
	Operator to create a powerup
	"""
	
	bl_idname = "shatter.create_powerup"
	bl_label = "Create powerup"
	
	def execute(self, context):
		o = butil.add_empty()
		o.sh_properties.sh_type = "POW"
		
		return {"FINISHED"}

class sh_CreateWater(Operator):
	"""
	Operator to create a water
	"""
	
	bl_idname = "shatter.create_water"
	bl_label = "Create water"
	
	def execute(self, context):
		o = butil.add_box((0,0,0), (1,1,0))
		o.sh_properties.sh_type = "WAT"
		
		return {"FINISHED"}

class SHATTER_MT_3DViewportMenuExtras(Menu):
	bl_label = "Extra features"
	
	def draw(self, context):
		self.layout.operator("shatter.export_all_auto")
		self.layout.operator("shatter.export_level_package")
		self.layout.operator("shatter.rebake_meshes")
		self.layout.operator("shatter.progression_crypto")
		self.layout.operator("shatter.segstrate_static")
		self.layout.operator("shatter.patch_libsmashhit")

class OpenShatterCreditsPage(Operator):
	"""
	Operator to create a water
	"""
	
	bl_idname = "shatter.open_credits_page"
	bl_label = "Credits and Third Party Libraries"
	
	def execute(self, context):
		if (secrets.randbelow(150) == 0):
			global g_got_ricked
			webbrowser.open(f"https://www.youtube.com/watch?v=dQw4w9WgXcQ")
			g_got_ricked = True
		else:
			webbrowser.open(f"https://github.com/Shatter-Team/Shatter/blob/trunk/CREDITS.md")
		return {"FINISHED"}

class OpenShatterPrivacyPage(Operator):
	"""
	Operator to create a water
	"""
	
	bl_idname = "shatter.open_privacy_page"
	bl_label = "Privacy and Security Statement"
	
	def execute(self, context):
		webbrowser.open(f"https://github.com/Shatter-Team/Shatter/blob/trunk/PRIVACY.md")
		return {"FINISHED"}

class OpenShatterDiscord(Operator):
	"""
	Operator to open shatter discrd
	"""
	
	bl_idname = "shatter.open_discord"
	bl_label = "Join the Smash Hit Lab Discord"
	
	def execute(self, context):
		webbrowser.open(f"https://discord.gg/7kra7Z3UNn")
		return {"FINISHED"}

class SHATTER_MT_3DViewportMenu(Menu):
	bl_label = "Shatter"
	
	def draw(self, context):
		self.layout.menu("SHATTER_MT_3DViewportMenuExtras")
		
		self.layout.separator()
		
		for t in [("box", "MESH_CUBE"), ("obstacle", "MESH_CONE"), ("decal", "TEXTURE"), ("powerup", "SOLO_OFF"), ("water", "MATFLUID")]:
			self.layout.operator(f"shatter.create_{t[0]}", icon = t[1])
		
		self.layout.separator()
		
		self.layout.operator("shatter.export_auto", icon = "MOD_BEVEL")
		self.layout.operator("shatter.export_test_server", icon = "AUTO")

def SHATTER_MT_3DViewportMenu_draw(self, context):
	self.layout.menu("SHATTER_MT_3DViewportMenu")

################################################################################
# UTILITIES AND STUFF
################################################################################

def run_updater():
	try:
		updater.check_for_updates(common.BL_INFO["version"])
	except Exception as e:
		import traceback
		print(f"Shatter for Blender: Had an exception whilst checking for updates:")
		print(traceback.format_exc())

###############
### AUTOGEN ###
###############

class AutogenProperties(PropertyGroup):
	
	seed: IntProperty(
		name = "Seed",
		description = "The seed to feed to the randomiser. Knowing the seed that you will run with allows you to recreate the exact results later",
		default = 0,
	)
	
	auto_randomise: BoolProperty(
		name = "Auto randomise",
		description = "Automatically generate a new, random seed every time a generation action is run",
		default = True,
	)
	
	type: EnumProperty(
		name = "Type",
		description = "Type of thing you would like to generate",
		items = [
			('BasicRoom', "Room structure", "Adds a basic room-like structure, optionally including a door area"),
			('SingleRow', "Row of boxes", "A single row of boxes, often used before and after chasms. Look at the first room of the game for an example of this"),
			('ArchWay', "Archway", "Creates an arch-like structure with bumps and floor parts"),
		],
		default = "SingleRow",
	)
	
	algorithm: EnumProperty(
		name = "Algorithm",
		description = "Algorithm to use to generate the thing",
		items = [
			('ActualRandom', "ActualRandom", "Purely random box heights"),
			('UpAndDownPath', "UpAndDownPath", ""),
			('ArithmeticProgressionSet', "ArithmeticProgressionSet", "Randomly selected from a subset of a arithmetic series (ex: random of 1/2, 1/4, 1/6)"),
			('GeometricProgressionSet', "GeometricProgressionSet", "Randomly selected from a subset of a geometric series (ex: random of 1/2, 1/4, 1/8)"),
		],
		default = "ActualRandom",
	)
	
	template: StringProperty(
		name = "Template",
		description = "Template to use for these boxes. You can also select a target box to copy properties from that box",
		default = "",
		maxlen = SH_MAX_STR_LEN,
	)
	
	size: FloatVectorProperty(
		name = "Box size",
		description = "First is width, second is depth. Height is the random part",
		default = (1.0, 1.0), 
		size = 2,
	)
	
	max_height: FloatProperty(
		name = "Max height",
		description = "",
		default = 0.5,
	)
	
	### Up and down path options ###
	
	udpath_start: FloatProperty(
		name = "Initial height",
		description = "",
		default = 0.25,
	)
	
	udpath_step: FloatProperty(
		name = "Step",
		description = "",
		default = 0.125,
	)
	
	udpath_minmax: FloatVectorProperty(
		name = "Min/max height",
		description = "",
		default = (0.125, 0.5), 
		size = 2,
	)
	
	### Geometric/Airthmetic progression generator options ###
	
	geometric_ratio: FloatProperty(
		name = "Ratio",
		description = "",
		default = 0.5,
	)
	
	geometric_exponent_minmax: IntVectorProperty(
		name = "Exponent",
		description = "",
		default = (1, 4),
		size = 2,
	)
	
	geometric_require_unique: BoolProperty(
		name = "No repeating heights",
		description = "",
		default = False,
	)
	
	### Room ###
	
	room_length: FloatProperty(
		name = "Length",
		description = "",
		default = 16.0,
	)
	
	room_door_part: BoolProperty(
		name = "Door part",
		description = "",
		default = False,
	)
	
	room_yoffset: FloatProperty(
		name = "Height offset",
		description = "How high or low the room will appear to the player",
		default = 1.0,
	)
	
	### Arch ###
	
	arch_top_parts: BoolProperty(
		name = "Top decorations",
		description = "",
		default = True,
	)

class AutogenPanel(Panel):
	bl_label = "Shatter Autogen"
	bl_idname = "OBJECT_PT_autogen_panel"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Autogen"
	
	@classmethod
	def poll(self, context):
		return True
	
	def draw(self, context):
		layout = self.layout
		props = context.scene.shatter_autogen
		
		sub = layout.box()
		sub.label(text = "Seed", icon = "GRAPH")
		sub.prop(props, "auto_randomise")
		if (not props.auto_randomise):
			sub.prop(props, "seed")
			sub.operator("shatter.randomise_autogen_seed", text = "Randomise seed")
		
		sub = layout.box()
		sub.label(text = "Generate", icon = "BRUSHES_ALL")
		sub.prop(props, "type")
		if (props.type == "SingleRow"):
			sub.prop(props, "algorithm")
		if (not context.object):
			sub.prop(props, "template")
		else:
			sub.label(text = "Copying props from selected")
		if (props.type == "SingleRow" and props.algorithm != "ArithmeticProgressionSet"):
			sub.prop(props, "max_height")
		sub.prop(props, "size")
		
		# Single row options
		if (props.type == "SingleRow"):
			if (props.algorithm in ["UpAndDownPath"]):
				sub.prop(props, "udpath_start")
				sub.prop(props, "udpath_step")
				sub.prop(props, "udpath_minmax")
			
			if (props.algorithm in ["GeometricProgressionSet", "ArithmeticProgressionSet"]):
				sub.prop(props, "geometric_ratio")
				sub.prop(props, "geometric_exponent_minmax", text = "Exponent" if props.algorithm.startswith("G") else "Scalar")
				sub.prop(props, "geometric_require_unique")
		
		# Room options
		if (props.type == "BasicRoom"):
			sub.prop(props, "room_length")
			sub.prop(props, "room_yoffset")
			sub.prop(props, "room_door_part")
		
		# Archway
		if (props.type == "ArchWay"):
			sub.prop(props, "arch_top_parts")
		
		sub.operator("shatter.run_autogen", text = "Generate")
		
		layout.separator()

class RunRandomiseSeedAction(bpy.types.Operator):
	"""
	Run the seed randomiser action
	"""
	
	bl_idname = "shatter.randomise_autogen_seed"
	bl_label = "Randomise Autogen Seed"
	
	def execute(self, context):
		context.scene.shatter_autogen.seed = random.randint(0, 2 ** 31 - 1)
		
		return {'FINISHED'}

class BlenderPlacer:
	"""
	Provides an interface for the autogenerator to create boxes in blender in
	a generic way.
	"""
	
	def __init__(self, basePos, baseSize, param3):
		if (basePos and baseSize):
			self.setBase(basePos, baseSize)
		
		# This is probably a bit insane, but it's probably not the worst way of
		# doing this...
		if (type(param3) == str):
			self.template = param3
		else:
			self.visible_object_props = param3.sh_properties
		
		self.objects = []
	
	def setBase(self, basePos, baseSize):
		"""
		Make a base box from the blender location and size
		"""
		
		self.base = autogen.Box(autogen.Vector3(basePos[1], basePos[2], basePos[0]), autogen.Vector3(baseSize[1] / 2, baseSize[2] / 2, baseSize[0] / 2))
	
	def getBase(self):
		"""
		Get the base box as a generic box
		"""
		
		return self.base if hasattr(self, "base") else None
	
	def inheritProperties(self, obj, template_append = ""):
		"""
		Inherit the template or visible properties
		"""
		
		# Use the base box if one exists, otherwise just fallback to using the
		# template value
		if (hasattr(self, "base")):
			update_properties = ["sh_visible", "sh_template", "sh_tint", "sh_use_multitint", "sh_tint1", "sh_tint2", "sh_tint3", "sh_tile", "sh_use_multitile", "sh_tile1", "sh_tile2", "sh_tile3", "sh_tilerot", "sh_tilesize"]
			
			for prop in update_properties:
				val = getattr(self.visible_object_props, prop)
				setattr(obj.sh_properties, prop, val)
		else:
			obj.sh_properties.sh_template = self.template + template_append
	
	def addBox(self, box):
		"""
		Add a box to the scene
		"""
		
		# Add the mesh
		bpy.ops.mesh.primitive_cube_add(size = 1.0, location = (box.pos.z, box.pos.x, box.pos.y), scale = (box.size.z * 2, box.size.x * 2, box.size.y * 2))
		
		# The added mesh is always selected after, so we do this to get the object
		box = bpy.context.active_object
		
		# Set the template or visible settings
		self.inheritProperties(box)
		
		# Append the box to the list of objects we have made
		self.objects.append(box)
	
	def addObstacle(self, obs):
		"""
		Add an obstacle to the scene
		"""
		
		o = bpy.data.objects.new("empty", None)
		
		bpy.context.scene.collection.objects.link(o)
		
		o.empty_display_size = 1
		o.empty_display_type = "PLAIN_AXES"
		
		o.location = (obs.pos.z, obs.pos.x, obs.pos.y)
		
		o.sh_properties.sh_type = "OBS"
		o.sh_properties.sh_obstacle = obs.type
		self.inheritProperties(o, "_glass")
		
		self.objects.append(o)
	
	def addDecal(self, dec):
		"""
		Add a new decal to the scene
		"""
		
		o = bpy.data.objects.new("empty", None)
		
		bpy.context.scene.collection.objects.link(o)
		
		o.empty_display_size = 1
		o.empty_display_type = "PLAIN_AXES"
		
		o.location = (dec.pos.z, dec.pos.x, dec.pos.y)
		
		o.sh_properties.sh_type = "DEC"
		o.sh_properties.sh_decal = dec.id
		self.inheritProperties(o)
		
		self.objects.append(o)
	
	def selectAll(self):
		"""
		Select all objects that were part of this round
		"""
		
		for o in self.objects:
			o.select_set(True)

class RunAutogenAction(bpy.types.Operator):
	"""
	Run the automatic generator
	"""
	
	bl_idname = "shatter.run_autogen"
	bl_label = "Run Shatter Autogen"
	
	def execute(self, context):
		"""
		Furries Furries Furries Furries Furries Furries Furries Furries Furries
		Furries Furries Furries Furries Furries Furries Furries Furries Furries
		Furries Furries Furries Furries Furries Furries Furries Furries Furries
		Furries Furries Furries Furries Furries Furries Furries Furries Furries
		"""
		
		props = context.scene.shatter_autogen
		
		if (props.auto_randomise):
			context.scene.shatter_autogen.seed = random.randint(0, 2 ** 31 - 1)
		
		placer = BlenderPlacer(
			context.object.location if context.object else None,
			context.object.dimensions if context.object else None,
			context.object if context.object and (context.object.sh_properties.sh_visible or not props.template) else props.template,
		)
		
		params = {
			"seed": props.seed,
			"type": props.type,
			"size": props.size,
			"max_height": props.max_height,
		}
		
		# For all single row types
		if (props.type == "SingleRow"):
			# Check if a box is currently selected, error if not
			if (not placer.getBase()):
				butil.show_message("Shatter Autogen error", "To use the single row generator, please select a box to build on top of.")
				return {"FINISHED"}
			
			params["algorithm"] = props.algorithm
			
			# Geometric options
			if (props.algorithm in ["GeometricProgressionSet", "ArithmeticProgressionSet"]):
				params["geometric_exponent_minmax"] = props.geometric_exponent_minmax
				params["geometric_ratio"] = props.geometric_ratio
				params["geometric_require_unique"] = props.geometric_require_unique
			
			# UpDownPath options
			if (props.algorithm in ["UpAndDownPath"]):
				params["udpath_min"] = props.udpath_minmax[0]
				params["udpath_max"] = props.udpath_minmax[1]
				params["udpath_start"] = props.udpath_start
				params["udpath_step"] = props.udpath_step
		
		# Room options
		if (props.type == "BasicRoom"):
			params["room_length"] = props.room_length
			params["room_yoffset"] = props.room_yoffset
			params["room_door_part"] = props.room_door_part
		
		# Archway
		if (props.type == "ArchWay"):
			params["top_parts"] = props.arch_top_parts
		
		autogen.generate(placer, params)
		
		placer.selectAll()
		
		return {'FINISHED'}

################################################################################
################################################################################
################################################################################
################################################################################

# Ignore the naming scheme for classes, please
# Also WHY THE FUCK DO I HAVE TO DO THIS???
classes = (
	sh_SceneProperties,
	sh_EntityProperties,
	sh_SegmentPanel,
	sh_ItemPropertiesPanel,
	sh_AddonPreferences,
	sh_export,
	sh_export_gz,
	sh_export_auto,
	sh_export_all_auto,
	sh_export_test,
	sh_import,
	sh_import_gz,
	sh_static_segstrate,
	sh_rebake_meshes,
	SHATTER_MT_3DViewportMenuExtras,
	SHATTER_MT_3DViewportMenu,
	sh_CreateBox,
	sh_CreateObstacle,
	sh_CreateDecal,
	sh_CreatePowerup,
	sh_CreateWater,
	OpenShatterCreditsPage,
	OpenShatterPrivacyPage,
	OpenShatterDiscord,
	AutogenProperties,
	AutogenPanel,
	RunRandomiseSeedAction,
	RunAutogenAction,
	level_pack_ui.ExportLevelPackage,
	patcher_ui.PatchLibsmashhit,
	progression_crypto_ui.ProgressionCrypto,
	RandomiseKeyphrase,
)

keymaps = {
	"D": "shatter.create_box",
	"F": "shatter.create_obstacle",
	"X": "shatter.create_decal",
	"C": "shatter.create_powerup",
	"V": "shatter.create_water",
	
	"R": "shatter.export_auto",
	"Q": "shatter.export_all_auto",
	"E": "shatter.export_test_server",
	"P": "shatter.export_compressed",
	"L": "shatter.export",
	
	"I": "shatter.import",
	"O": "shatter.import_gz",
	
	"Y": "shatter.segstrate_static",
}

keymaps_registered = []

def register():
	from bpy.utils import register_class
	
	for cls in classes:
		register_class(cls)
	
	bpy.types.Scene.sh_properties = PointerProperty(type=sh_SceneProperties)
	bpy.types.Scene.shatter_autogen = PointerProperty(type=AutogenProperties)
	bpy.types.Object.sh_properties = PointerProperty(type=sh_EntityProperties)
	
	# Add the export operator to menu
	bpy.types.TOPBAR_MT_file_export.append(sh_draw_export)
	bpy.types.TOPBAR_MT_file_export.append(sh_draw_export_gz)
	bpy.types.TOPBAR_MT_file_export.append(sh_draw_export_auto)
	bpy.types.TOPBAR_MT_file_export.append(sh_draw_export_all_auto)
	bpy.types.TOPBAR_MT_file_export.append(sh_draw_export_test)
	
	# Add import operators to menu
	bpy.types.TOPBAR_MT_file_import.append(sh_draw_import)
	bpy.types.TOPBAR_MT_file_import.append(sh_draw_import_gz)
	
	# Add Shatter menu in 3D viewport
	bpy.types.VIEW3D_MT_editor_menus.append(SHATTER_MT_3DViewportMenu_draw)
	
	# Register keymaps
	window_manager = bpy.context.window_manager
	
	if (window_manager.keyconfigs.addon):
		for a in keymaps:
			keymap = window_manager.keyconfigs.addon.keymaps.new(name = '3D View', space_type = 'VIEW_3D')
			keymap_item = keymap.keymap_items.new(keymaps[a], type = a, value = 'PRESS', shift = 1, alt = 1)
			keymaps_registered.append((keymap, keymap_item))
	
	# Start server
	global g_process_test_server
	
	if (g_process_test_server and get_prefs().enable_quick_test_server):
		try:
			g_process_test_server = quick_test.runServerProcess()
		except Exception as e:
			print(f"*** Exception while starting quick test server ***")
			print(traceback.format_exc())
	
	# Check for updates
	run_updater()
	
	# A little easter egg for those who remember
	print(f"User has been detected as bad user: False")

def unregister():
	from bpy.utils import unregister_class
	
	# Remove export operators
	bpy.types.TOPBAR_MT_file_export.remove(sh_draw_export)
	bpy.types.TOPBAR_MT_file_export.remove(sh_draw_export_gz)
	bpy.types.TOPBAR_MT_file_export.remove(sh_draw_export_auto)
	bpy.types.TOPBAR_MT_file_export.remove(sh_draw_export_all_auto)
	bpy.types.TOPBAR_MT_file_export.remove(sh_draw_export_test)
	
	# Remove import operators
	bpy.types.TOPBAR_MT_file_import.remove(sh_draw_import)
	bpy.types.TOPBAR_MT_file_import.remove(sh_draw_import_gz)
	
	# Remove editor menu UI
	bpy.types.VIEW3D_MT_editor_menus.remove(SHATTER_MT_3DViewportMenu_draw)
	
	# Delete property types
	del bpy.types.Scene.sh_properties
	del bpy.types.Scene.shatter_autogen
	del bpy.types.Object.sh_properties
	
	# Delete keymaps
	for a, b in keymaps_registered:
		a.keymap_items.remove(b)
	
	keymaps_registered.clear()
	
	# Unregister classes
	for cls in reversed(classes):
		# Blender decided it would be a piece of shit today 
		try:
			unregister_class(cls)
		except RuntimeError as e:
			print(f"Blender is being a little shit while unregistering class {cls}:\n\n{e}")
	
	# Shutdown server
	global g_process_test_server
	
	if (g_process_test_server):
		g_process_test_server.terminate()
