"""
Main file for Shatter tools
"""

import common as common

SH_MAX_STR_LEN = common.MAX_STRING_LENGTH

import bpy
import os
import webbrowser
import traceback
import secrets
import obstacle_db
import segment_export
import segment_import
import room_export
import updater
import autogen_ui
import util
import butil
import level_pack_ui
import patcher_ui
import progression_crypto_ui
import server_manager
import assets

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

# The level test server manager
gServerManager = None

# :-3
g_got_ricked = False

ExportHelper2 = butil.ExportHelper2
get_prefs = butil.prefs

class ShatterExportCommon(bpy.types.Operator, ExportHelper2):
	"""
	Common code and values between export types
	"""
	
	sh_meshbake_template: StringProperty(
		name = "Template",
		description = "A relitive or full path to the template file used for baking meshes. If you use APK Editor Studio and the Smash Hit APK is open, the path to the file will be pre-filled",
		default = "",
		subtype = "FILE_PATH",
	)
	
	def __init__(self):
		"""
		Automatic templates.xml detection
		"""
		
		if (not self.sh_meshbake_template):
			self.sh_meshbake_template = segment_export.tryTemplatesPath()

class SegmentExport(ShatterExportCommon):
	"""Export an uncompressed (.xml.mp3) segment"""
	
	bl_idname = "shatter.export"
	bl_label = "Export Segment"
	
	filename_ext = ".xml.mp3"
	filter_glob = bpy.props.StringProperty(default='*.xml.mp3', options={'HIDDEN'}, maxlen=255)
	
	def execute(self, context):
		segment_export.sh_export_segment(self.filepath, context, globals())
		
		return {"FINISHED"}

def sh_draw_export(self, context):
	self.layout.operator("shatter.export", text="Segment (.xml.mp3)")

class SegmentExportGz(ShatterExportCommon):
	"""Export a compressed (.xml.gz.mp3) segment. Choose this when you don't know which to use"""
	
	bl_idname = "shatter.export_compressed"
	bl_label = "Export Compressed Segment"
	
	filename_ext = ".xml.gz.mp3"
	filter_glob = bpy.props.StringProperty(default='*.xml.gz.mp3', options={'HIDDEN'}, maxlen=255)
	
	def execute(self, context):
		segment_export.sh_export_segment(self.filepath, context, globals(), True)
		
		return {"FINISHED"}

def sh_draw_export_gz(self, context):
	self.layout.operator("shatter.export_compressed", text="Compressed Segment (.xml.gz.mp3)")

class SegmentExportAuto(bpy.types.Operator):
	"""Automatically find an asset folder and save the segment to the segments folder in the correct location from the info given in the scene tab"""
	
	bl_idname = "shatter.export_auto"
	bl_label = "Export to Assets"
	
	def execute(self, context):
		segment_export.sh_export_segment(None, context, globals(), get_prefs().auto_export_compressed)
		
		return {"FINISHED"}

class SegmentExportAllAuto(bpy.types.Operator):
	"""Automatically find an asset path and export every segment in this file to the proper locations"""
	
	bl_idname = "shatter.export_all_auto"
	bl_label = "Export all to APK"
	
	def execute(self, context):
		segment_export.sh_export_all_segments(context, get_prefs().auto_export_compressed)
		
		return {"FINISHED"}

class SegmentExportTest(Operator):
	"""Export a segment to the quick test server"""
	
	bl_idname = "shatter.export_test_server"
	bl_label = "Export segment to quick test"
	
	def execute(self, context):
		if (get_prefs().quick_test_server == "builtin"):
			segment_export.sh_export_segment(None, context, globals(), False, True)
		else:
			butil.show_message("Quick test not running", "The quick test server is not running right now. If you're using Yorshex's asset server, use auto export (Alt + Shift + R by default) instead.")
		
		return {"FINISHED"}

class SegmentImport(bpy.types.Operator, ImportHelper):
	"""Imports an uncompressed (.xml.mp3) segment to the current scene"""
	
	bl_idname = "shatter.import"
	bl_label = "Import Segment"
	
	check_extension = False
	filename_ext = ".xml.mp3"
	filter_glob = bpy.props.StringProperty(default='*.xml.mp3', options={'HIDDEN'}, maxlen=255)
	
	def execute(self, context):
		return segment_import.sh_import_segment(self.filepath, context)

def sh_draw_import(self, context):
	self.layout.operator("shatter.import", text="Segment (.xml.mp3)")

class SegmentImportGz(bpy.types.Operator, ImportHelper):
	"""Imports a compressed (.xml.gz.mp3) segment to the current scene"""
	
	bl_idname = "shatter.import_gz"
	bl_label = "Import Compressed Segment"
	
	check_extension = False
	filename_ext = ".xml.gz.mp3"
	filter_glob = bpy.props.StringProperty(default='*.xml.gz.mp3', options={'HIDDEN'}, maxlen=255)
	
	def execute(self, context):
		return segment_import.sh_import_segment(self.filepath, context, True)

def sh_draw_import_gz(self, context):
	self.layout.operator("shatter.import_gz", text="Compressed Segment (.xml.gz.mp3)")

################################################################################
# Server manager related
################################################################################

def server_manager_update(_self = None, _context = None):
	"""
	Note: self and context can be none
	"""
	
	server_type = get_prefs().quick_test_server
	
	try:
		global gServerManager
		
		gServerManager.stop()
		gServerManager.set_type(server_type)
		
		if (server_type == "yorshex"):
			level_name = get_prefs().test_level
			level_name = level_name if level_name != "/" else (bpy.context.scene.sh_properties.sh_level if _context else "")
			
			gServerManager.set_params((butil.find_apk(), level_name))
		else:
			gServerManager.set_params(tuple())
		
		gServerManager.start()
	except Exception as e:
		util.log(f"*** Exception in server manager!!! ***")
		util.log(traceback.format_exc())

gLevelList = None

def get_test_level_list(self, context):
	global gLevelList
	
	gLevelList = assets.list_levels(gLevelList)
	
	levels = [("/", "Segment's level", "Use the segment's level attribute to determine the level"), None]
	
	for l in gLevelList["results"]:
		levels.append((l, l, ""))
	
	return levels

################################################################################
# Item and scene data structures
################################################################################

class SegmentProperties(PropertyGroup):
	"""
	Segment (scene) properties
	"""
	
	sh_level: StringProperty(
		name = "Level",
		description = "The name of the checkpoint that this segment belongs to.",
		default = "",
		update = server_manager_update,
	)
	
	sh_room: StringProperty(
		name = "Room",
		description = "The name of the room that this segment belongs to.",
		default = "",
	)
	
	sh_segment: StringProperty(
		name = "Segment",
		description = "The name of this segment",
		default = "",
	)
	
	sh_len: FloatVectorProperty(
		name = "Size",
		description = "Segment size in the order Width, Height, Depth. Last paramater changes the length (depth) of the segment",
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
	)
	
	sh_default_template: StringProperty(
		name = "Default template",
		description = "The base name of the template to use when no template is specified for an entity. Format: boxes 🡒 '{basename}', obstacles 🡒 '{basename}_glass', obstacles starting with 'score' 🡒 '{basename}_st', segment 🡒 '{basename}_s'",
		default = "",
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
		name = "Advanced lighting (deprecated)",
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
		description = "Name of the music file to play in quick test. The track must be in the apk. Default is to choose a random track. Using \\ in the name will break it :-)",
		default = "",
	)
	
	sh_reverb: StringProperty(
		name = "Reverb",
		description = "Reverb parameters as real numbers sepreated by spaces. [volume: [0, 1]] [reverb time: sec] [lowpass amount: [0, 1]]",
		default = "",
	)
	
	sh_echo: StringProperty(
		name = "Echo",
		description = "Echo parameters as real numbers sepreated by spaces. [volume: [0, 1]] [delay: sec] [feedback volume: [0, 1]] [lowpass amount: [0, 1]]",
		default = "",
	)
	
	sh_rotation: StringProperty(
		name = "Rotation",
		description = "The rotation parameters as real numbers sepreated by spaces. [amount of rotations: int] [angle: radians]",
		default = "",
	)
	
	sh_particles: EnumProperty(
		name = "Particles",
		description = "The particles that appear when looking at the stage in quick test",
		items = (
			("None", "None", ""),
			("bubbles", "Bubbles", ""),
			("sides", "Sides", ""),
			("lowrising", "Low rising 1", ""),
			("lowrising2", "Low rising 2", ""),
			("lowrising3", "Low rising 3", ""),
			("sidesrising", "Sides rising", ""),
			("falling", "Falling", ""),
			("fallinglite", "Falling lite", ""),
			("dustyfalling", "Dusty falling", ""),
			("starfield", "Star field", ""),
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
		min = -1.0,
		max = 3.0,
	)
	
	sh_extra_code: StringProperty(
		name = "Extra code",
		description = "Extra code to include the in room file. Multipule statements can be seperated by ';'.",
		default = "",
	)
	
	sh_room_length: IntProperty(
		name = "Room length",
		description = "The length of the room in quick test",
		default = 100,
		min = 0,
	)

class EntityProperties(PropertyGroup):
	
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
	
	sh_param0: StringProperty(
		name = "param0",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param1: StringProperty(
		name = "param1",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param2: StringProperty(
		name = "param2",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param3: StringProperty(
		name = "param3",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param4: StringProperty(
		name = "param4",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param5: StringProperty(
		name = "param5",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param6: StringProperty(
		name = "param6",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param7: StringProperty(
		name = "param7",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param8: StringProperty(
		name = "param8",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param9: StringProperty(
		name = "param9",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param10: StringProperty(
		name = "param10",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
	sh_param11: StringProperty(
		name = "param11",
		description = "Parameter which is given to the obstacle when spawned",
		default = "",
	)
	
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
		size = 2,
	)
	
	sh_resolution: FloatVectorProperty(
		name = "Resolution",
		description = "Controls how detailed the water effect looks. Smaller values will lead to larger but lower quality splashes when an object hits the water",
		default = (32.0, 32.0),
		min = 0.0,
		size = 2,
	)
	
	sh_glow: FloatProperty(
		name = "Glow",
		description = "The intensity of the light in \"watts\"; zero if this isn't a light",
		default = 0.0,
		min = 0.0,
		max = 1000.0,
	)

################################################################################
# Addon, item and scene panels
################################################################################

class ShatterPreferences(AddonPreferences):
	bl_idname = "shatter"
	
	tab: EnumProperty(
		name = "",
		description = "",
		items = [
			('General', "General", ""),
			('Features', "Features", ""),
			('About', "About", ""),
		],
		default = "General",
	)
	
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
		description = "Enables segment compression when using the 'Export to Assets' option. Smash Hit does not compress segments by default in 1.5.x and later",
		default = True,
	)
	
	resolve_templates: BoolProperty(
		name = "Resolve templates at export time",
		description = "Solves templates when a segment is exported. This avoids the need for adding used templates to templates.xml, but makes the filesize larger and the XML file less readable",
		default = False,
	)
	
	purist_mode: BoolProperty(
		name = "Limit UI to classic Smash Hit features",
		description = "Removes shatter extended features from the UI, for example gradients and advanced lighting",
		default = False,
	)
	
	compact_ui: BoolProperty(
		name = "Compact UI mode",
		description = "Avoids drawing any excessive UI elements that would make the UI larger than needed",
		default = False,
	)
	
	show_deprecated_advanced_lights: BoolProperty(
		name = "Show advanced lights (deprecated)",
		description = "Shows the advanced lights panel when not relevant. Note that advanced lights is *deprecated* meaning it could be removed at any time",
		default = False,
	)
	
	enable_auto_update: BoolProperty(
		name = "Enable automatic updates",
		description = "Automatically downloads and installs the newest version of the addon",
		default = True,
	)
	
	update_check_frequency: IntProperty(
		name = "Updater checking frequency (hours)",
		description = "This controls how frequently the updater will check for new updates, in hours",
		min = 4,
		max = 720,
		default = 12,
	)
	
	updater_channel: EnumProperty(
		name = "Channel",
		description = "This controls how frequently you will recieve updates, tweaks and new features. Faster updates might be buggier and break your workflow but contain better features, while slower updates will give a better exprience without newer features",
		items = [
			('stable', "Normal", "Contains new updates and features as soon as they are available, but might also break sometimes."),
			None,
			('updatertest', "Updater test", "A testing channel. This doesn't get real updates."),
		],
		default = "stable",
	)
	
	quick_test_server: EnumProperty(
		name = "Level test server",
		description = "Selects which, if any, level test server will be used. This will create a local HTTP server on port 8000, which might pose a security risk",
		items = [
			('none', "None", "Don't use any quick test server"),
			('builtin', "Quick test server", "The classic quick test server integrated with Shatter, simplest and fastest to use but only loads one segment at a time"),
			('yorshex', "Yorshex's asset server", "More advanced test server that allows loading an entire level from a Smash Hit assets folder, written by Yorshex. Shatter integration is a work in progress but should be usable"),
		],
		update = server_manager_update,
		default = "builtin",
	)
	
	test_level: EnumProperty(
		name = "Test level",
		description = "The name of the level to test",
		items = get_test_level_list,
		update = server_manager_update,
		default = 0,
	)
	
	force_disallow_import: BoolProperty(
		name = "Always disallow import",
		description = "Enabling this option will force every segment to have the \"disallow import\" flag set, even if you did not configure it via the obstacle panel. Please note that marking segments with this flag does not prevent someone bypassing it",
		default = False,
	)
	
	####################
	## Advanced settings
	####################
	mesh_baker: EnumProperty(
		name = "Mesh baker",
		description = "Selects which mesh baker to use",
		items = [
			('bakemesh', "BakeMesh", "Shatter's default mesh baker, written in Python. Slow in some cases and also completely fucks up tile rotations, but supports some extras like gradients"),
			('command', "Custom command (advanced)", "Run a custom command to bake the mesh"),
		],
		default = "bakemesh",
	)
	
	mesh_command: StringProperty(
		name = "External mesh bake command",
		description = "If specified, this command is run instead of the built-in mesh baker",
		default = "",
	)
	
	def draw(self, context):
		main = self.layout
		
		ui = butil.UIDrawingHelper(context, self.layout, self)
		
		# tab = ui.prop("tab", use_tabs = True)
		# HACK Make this part of the generic thing
		r = self.layout.row(align = True)
		r.prop_enum(self, "tab", "General")
		r.prop_enum(self, "tab", "Features")
		r.prop_enum(self, "tab", "About")
		tab = self.tab
		
		getattr(self, f"draw_{tab.lower()}")(ui)
	
	def draw_general(self, ui):
		ui.region("EXPORT", "Export and import")
		ui.prop("default_assets_path")
		ui.prop("enable_segment_warnings")
		ui.prop("auto_export_compressed")
		ui.prop("resolve_templates")
		ui.prop("force_disallow_import")
		ui.end()
		
		ui.region("DESKTOP", "Interface")
		ui.prop("compact_ui")
		ui.prop("purist_mode")
		ui.prop("show_deprecated_advanced_lights")
		ui.end()
		
		ui.region("WORLD", "Automatic updates")
		ui.prop("enable_auto_update")
		
		if (self.enable_auto_update):
			ui.prop("update_check_frequency")
			ui.prop("updater_channel")
		
		ui.end()
	
	def draw_features(self, ui):
		ui.region("AUTO", "Quick test")
		
		if (ui.prop("quick_test_server") == "yorshex"):
			ui.warn("To use asset server you should agree with the zlib licence.")
		
		ui.region("UV_DATA", "Mesh baking")
		
		if (ui.prop("mesh_baker") == "command"):
			ui.prop("mesh_command")
		
		ui.end()
	
	def draw_about(self, ui):
		ui.region("INFO", "About Shatter")
		ui.op("shatter.open_discord")
		ui.op("shatter.open_credits_page")
		ui.op("shatter.open_privacy_page")
		
		if (g_got_ricked):
			ui.region("INFO", "Trolled !!!", new = False)
			import getpass
			ui.label(f"Anyway, I hope you are doing well in life {getpass.getuser().capitalize()}. :)")
			ui.label("-- Knot126")
			ui.end()
		
		ui.end()

class SegmentPanel(Panel):
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
			
			sub.prop(sh_properties, "sh_light_right")
			sub.prop(sh_properties, "sh_light_left")
			sub.prop(sh_properties, "sh_light_top")
			sub.prop(sh_properties, "sh_light_bottom")
			sub.prop(sh_properties, "sh_light_front")
			sub.prop(sh_properties, "sh_light_back")
			
			if ((not get_prefs().purist_mode and get_prefs().show_deprecated_advanced_lights) or sh_properties.sh_lighting):
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
		server_type = get_prefs().quick_test_server
		
		if (server_type == "builtin"):
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
		elif (server_type == "yorshex"):
			sub = layout.box()
			sub.label(text = "Asset server", icon = "AUTO")
			sub.prop(get_prefs(), "test_level")
			sub.label(text = f"Your IP: {util.get_local_ip()}")
		
		# DRM
		if (not bpy.context.preferences.addons["shatter"].preferences.force_disallow_import):
			sub = layout.box()
			sub.label(text = "Protection", icon = "LOCKED")
			sub.prop(sh_properties, "sh_drm_disallow_import")
		
		layout.separator()

class EntityPanel(Panel):
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
			
			if (not get_prefs().purist_mode or ui.get("sh_graddir") != "none"):
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
			ui.prop("sh_resolution")
		
		ui.prop("sh_export")

################################################################################
# Operators for creating entities
################################################################################

class CreateBox(Operator):
	"""Creates a new box"""
	
	bl_idname = "shatter.create_box"
	bl_label = "Create box"
	
	def execute(self, context):
		o = butil.add_box((0,0,0), (1,1,1))
		
		return {"FINISHED"}

class CreateObstacle(Operator):
	"""Creates a new obstacle"""
	
	bl_idname = "shatter.create_obstacle"
	bl_label = "Create obstacle"
	
	def execute(self, context):
		o = butil.add_empty()
		o.sh_properties.sh_type = "OBS"
		
		return {"FINISHED"}

class CreateDecal(Operator):
	"""Creates a new decal"""
	
	bl_idname = "shatter.create_decal"
	bl_label = "Create decal"
	
	def execute(self, context):
		o = butil.add_empty()
		o.sh_properties.sh_type = "DEC"
		
		return {"FINISHED"}

class CreatePowerup(Operator):
	"""Creates a new powerup"""
	
	bl_idname = "shatter.create_powerup"
	bl_label = "Create powerup"
	
	def execute(self, context):
		o = butil.add_empty()
		o.sh_properties.sh_type = "POW"
		
		return {"FINISHED"}

class CreateWater(Operator):
	"""Creates a new water plane"""
	
	bl_idname = "shatter.create_water"
	bl_label = "Create water"
	
	def execute(self, context):
		o = butil.add_box((0,0,0), (1,1,0))
		o.sh_properties.sh_type = "WAT"
		
		return {"FINISHED"}

################################################################################
# Misc. operators related to opening pages
################################################################################

class OpenShatterCreditsPage(Operator):
	"""Open Shatter's credits web page"""
	
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
	"""Open Shatter's statement about privacy and security"""
	
	bl_idname = "shatter.open_privacy_page"
	bl_label = "Privacy and Security Statement"
	
	def execute(self, context):
		webbrowser.open(f"https://github.com/Shatter-Team/Shatter/blob/trunk/PRIVACY.md")
		return {"FINISHED"}

class OpenShatterDiscord(Operator):
	"""Get a join link for the Smash Hit Lab discord"""
	
	bl_idname = "shatter.open_discord"
	bl_label = "Join the Smash Hit Lab Discord"
	
	def execute(self, context):
		webbrowser.open(f"https://discord.gg/7kra7Z3UNn")
		return {"FINISHED"}

class OpenObstaclesTextFile(Operator):
	"""Open the obstacles.txt file"""
	
	bl_idname = "shatter.open_obstacles_txt"
	bl_label = "Edit custom obstacles"
	
	def execute(self, context):
		util.user_edit_file(common.TOOLS_HOME_FOLDER + "/obstacles.txt")
		return {"FINISHED"}

class OpenCurrentAssetFolder(Operator):
	"""Open the currently used asset folder"""
	
	bl_idname = "shatter.open_current_asset_folder"
	bl_label = "Open current asset folder"
	
	def execute(self, context):
		folder = butil.find_apk()
		
		if (folder):
			util.user_edit_file(folder)
		else:
			butil.show_message("Folder not found", "The assets folder was not found. Try setting a default asset path in Shatter preferences or open an APK in APK Editor Studio.")
		
		return {"FINISHED"}

################################################################################
# Shatter menu
################################################################################

class SHATTER_MT_3DViewportMenu(Menu):
	bl_label = "Shatter"
	
	def draw(self, context):
		self.layout.menu("SHATTER_MT_3DViewportMenuExtras")
		
		self.layout.separator()
		
		for t in [("box", "MESH_CUBE"), ("obstacle", "MESH_CONE"), ("decal", "TEXTURE"), ("powerup", "SOLO_OFF"), ("water", "MATFLUID")]:
			self.layout.operator(f"shatter.create_{t[0]}", icon = t[1])
		
		self.layout.separator()
		
		self.layout.operator("shatter.export_auto", icon = "MOD_BEVEL")
		
		if (get_prefs().quick_test_server == "builtin"):
			self.layout.operator("shatter.export_test_server", icon = "AUTO")

def SHATTER_MT_3DViewportMenu_draw(self, context):
	self.layout.menu("SHATTER_MT_3DViewportMenu")

class SHATTER_MT_3DViewportMenuExtras(Menu):
	bl_label = "Extra features"
	
	def draw(self, context):
		self.layout.label(text = "Common")
		self.layout.operator("shatter.patch_libsmashhit")
		self.layout.separator()
		self.layout.label(text = "Export")
		self.layout.operator("shatter.export_all_auto")
		if (get_prefs().quick_test_server == "builtin"):
			self.layout.operator("shatter.export_room")
		self.layout.operator("shatter.export_level_package")
		self.layout.separator()
		self.layout.label(text = "Others")
		self.layout.operator("shatter.progression_crypto")
		self.layout.operator("shatter.open_obstacles_txt")
		self.layout.operator("shatter.open_current_asset_folder")

################################################################################
# UTILITIES AND STUFF
################################################################################

def run_updater():
	try:
		# Blender seems fucking stupid and isn't writing the update time
		# properly so i just have to use a file for that :/
		last_update_time = util.get_file(common.TOOLS_HOME_FOLDER + "/udcheck.txt")
		last_update_time = int(last_update_time) if last_update_time != None else 0
		
		util.log(f"Last checked for updates at {last_update_time} (unix time)")
		
		# Check if we've recently checked for updates
		next_update_time = last_update_time + 60 * 60 * get_prefs().update_check_frequency
		should_check = util.get_time() >= next_update_time
		
		if (should_check):
			updater.run_updater(common.BL_INFO["version"], get_prefs().updater_channel, bpy.app.version)
			util.set_file(common.TOOLS_HOME_FOLDER + "/udcheck.txt", str(int(util.get_time())))
		else:
			util.log(f"Updates checked for recently, will check for update in at least {next_update_time - util.get_time()} seconds")
	except Exception as e:
		import traceback
		util.log(f"Shatter for Blender: Had an exception whilst checking for updates:")
		util.log(traceback.format_exc())

###############################################################################

# Also WHY THE FUCK DO I HAVE TO DO THIS???
classes = (
	SegmentProperties,
	EntityProperties,
	SegmentPanel,
	EntityPanel,
	ShatterPreferences,
	SegmentExport,
	SegmentExportGz,
	SegmentExportAuto,
	SegmentExportAllAuto,
	SegmentExportTest,
	SegmentImport,
	SegmentImportGz,
	SHATTER_MT_3DViewportMenuExtras,
	SHATTER_MT_3DViewportMenu,
	CreateBox,
	CreateObstacle,
	CreateDecal,
	CreatePowerup,
	CreateWater,
	OpenShatterCreditsPage,
	OpenShatterPrivacyPage,
	OpenShatterDiscord,
	OpenObstaclesTextFile,
	OpenCurrentAssetFolder,
	autogen_ui.AutogenProperties,
	autogen_ui.AutogenPanel,
	autogen_ui.RunRandomiseSeedAction,
	autogen_ui.RunAutogenAction,
	level_pack_ui.ExportLevelPackage,
	patcher_ui.PatchLibsmashhit,
	progression_crypto_ui.ProgressionCrypto,
	room_export.ExportRoom,
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
}

keymaps_registered = []

def register():
	util.log(f"Shatter version {common.BL_INFO['version'][0]}.{common.BL_INFO['version'][1]}.{common.BL_INFO['version'][2]} starting up!")
	util.log("""**************************************************************
* \x1b[1;32m"With the power of the prism, there's nothing I can't do."\x1b[0m *
*         - \x1b[33mTails Nine\x1b[0m, \x1b[35m2024\x1b[0m                                 *
**************************************************************""")
	
	from bpy.utils import register_class
	
	for cls in classes:
		register_class(cls)
	
	bpy.types.Scene.sh_properties = PointerProperty(type=SegmentProperties)
	bpy.types.Scene.shatter_autogen = PointerProperty(type=autogen_ui.AutogenProperties)
	bpy.types.Object.sh_properties = PointerProperty(type=EntityProperties)
	
	# Add the export operator to menu
	bpy.types.TOPBAR_MT_file_export.append(sh_draw_export)
	bpy.types.TOPBAR_MT_file_export.append(sh_draw_export_gz)
	
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
	
	# Start level server
	global gServerManager
	gServerManager = server_manager.LevelServerManager()
	server_manager_update()
	
	# Check for updates
	if (get_prefs().enable_auto_update):
		run_updater()

def unregister():
	from bpy.utils import unregister_class
	
	# Remove export operators
	bpy.types.TOPBAR_MT_file_export.remove(sh_draw_export)
	bpy.types.TOPBAR_MT_file_export.remove(sh_draw_export_gz)
	
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
			util.log(f"Blender is being a little shit while unregistering class {cls}:\n\n{e}")
	
	# Shutdown server
	global gServerManager
	gServerManager.stop()
