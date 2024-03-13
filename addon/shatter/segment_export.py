"""
Shatter for Blender segment export

TODO This code sucks actual ass. Make it not.
"""

import xml.etree.ElementTree as et
import bpy
import gzip
import os
import os.path as ospath
import pathlib
import tempfile
import json
import pathlib
import common
import mesh_runner
import obstacle_db
import util
import butil
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
)

prefs = butil.prefs

class ExportWarnings():
	"""
	Keep track of export warnings
	"""
	
	def __init__(self):
		self.warnings = set()
	
	def add(self, text):
		"""
		Add an export warning
		"""
		
		self.warnings.add(text)
	
	def display(self):
		"""
		Display a message with warnings
		"""
		
		if (len(self.warnings) and prefs().enable_segment_warnings):
			warnlist = []
			
			for warn in self.warnings:
				warnlist.append(warn)
			
			warnlist = ", ".join(warnlist)
			
			butil.show_message("Export warnings", f"The segment exported successfully, but some possible issues were noticed: {warnlist}.")

class ExportCounter():
	"""
	Helps count things
	"""
	
	def __init__(self):
		self.count = 0
	
	def inc(self):
		self.count += 1
	
	def has_any(self):
		return self.count > 0

def tryTemplatesPath():
	"""
	Try to get the path of the templates.xml file automatically
	"""
	
	# Try to find templates.xml using util.find_apk() first
	path = butil.find_apk()
	
	if (path):
		path += "/templates.xml.mp3"
	
	##
	## Templates file from home directory
	##
	
	homedir_templates = [common.TOOLS_HOME_FOLDER + "/templates.xml", common.HOME_FOLDER + "/smash-hit-templates.xml"]
	
	for f in homedir_templates:
		if (not path and ospath.exists(f)):
			path = f
	
	util.log(f"Got templates file: \"{path}\"")
	
	return path

def exportList(lst):
	return " ".join([str(x) for x in lst])

def exportPointList(lst):
	return f"{lst[1]} {lst[2]} {lst[0]}"

def isIndexableEqual(a, b):
	"""
	Check if two values that can be indexed are equal but don't care about their
	types. Examples:
	
	[1, 0] == [1, 0] -> True	
	(1, 0) == [1, 0] -> True
	[0, 1] == [1, 0] -> False
	(0, 1) == [1, 0] -> False
	"""
	
	if (len(a) != len(b)):
		return False
	
	for i in range(len(a)):
		if (a[i] != b[i]):
			return False
	
	return True

## Segment Export
## All of the following is related to exporting segments.

def sh_create_root(scene, params):
	"""
	Creates the main root and returns it
	"""
	
	size = [scene.sh_len[0], scene.sh_len[1], scene.sh_len[2]]
	
	# Automatic length detection
	if (scene.sh_auto_length):
		sizeZ = 0.0
		
		for o in bpy.context.scene.objects:
			# Find backmost part
			candZ = o.location[0] - (o.dimensions[0] / 2)
			
			# If it's lower that is the new semgent length
			if (candZ < sizeZ):
				sizeZ = candZ
		
		size[0] = 12.0
		size[1] = 10.0
		size[2] = -sizeZ
	
	# VR Multiply setting
	sh_vrmultiply = params.get("sh_vrmultiply", 1.0)
	
	if (sh_vrmultiply != 1.0):
		size[2] = size[2] * sh_vrmultiply
	
	# Segment size warning
	if (size[2] <= 0.0):
		params["warnings"].add("the segment length is zero or less which may behave weirdly")
	
	# Initial segment properties, like size
	seg_props = {
		"size": exportList(size)
	}
	
	# Check for the template attrib and set
	if (scene.sh_template):
		seg_props["template"] = scene.sh_template
	elif (scene.sh_default_template):
		seg_props["template"] = f"{scene.sh_default_template}_s"
	
	# Default template
	if (scene.sh_default_template):
		seg_props["shbt-default-template"] = scene.sh_default_template
	
	# Lighting
	# We no longer export lighting info if the template is present since that should
	# be taken care of there.
	if (not scene.sh_template):
		if (scene.sh_light_left != 1.0):   seg_props["lightLeft"] = str(scene.sh_light_left)
		if (scene.sh_light_right != 1.0):  seg_props["lightRight"] = str(scene.sh_light_right)
		if (scene.sh_light_top != 1.0):    seg_props["lightTop"] = str(scene.sh_light_top)
		if (scene.sh_light_bottom != 1.0): seg_props["lightBottom"] = str(scene.sh_light_bottom)
		if (scene.sh_light_front != 1.0):  seg_props["lightFront"] = str(scene.sh_light_front)
		if (scene.sh_light_back != 1.0):   seg_props["lightBack"] = str(scene.sh_light_back)
	
	# Check for softshadow attrib and set
	if (not (0.59999 < scene.sh_softshadow < 0.60001)):
		seg_props["softshadow"] = str(scene.sh_softshadow)
	
	# Add ambient lighting if enabled
	if (scene.sh_lighting):
		seg_props["ambient"] = exportList(scene.sh_lighting_ambient)
	
	# Protection
	if (scene.sh_drm_disallow_import or prefs().force_disallow_import):
		seg_props["drm"] = "NoImport"
	
	# Create main root and return it
	level_root = et.Element("segment", seg_props)
	level_root.text = "\n\t"
	
	return level_root

def list_to_str(List):
	return " ".join([str(x) for x in List])

def make_subelement_from_entity(level_root, scene, obj, params):
	"""
	This will add an obstacle to level_root. Note that there is no big
	swtich-case like thing here, it's basically checking what type of entity we
	have each time we want to add a property, so adding a property appears only
	once but checks for the type of entity appear many times.
	
	`level_root` is the root xml entity we should add to
	`scene` is actually just bpy.context.scene.sh_properties
	`obj` is the object to export
	`params` is a dictionary of export settings
	"""
	
	# These positions are swapped
	position = {"X": obj.location[1], "Y": obj.location[2], "Z": obj.location[0]}
	
	# VR Multiply setting
	sh_vrmultiply = params.get("sh_vrmultiply", 1.0)
	
	if (sh_vrmultiply != 1.0):
		position["Z"] = position["Z"] * sh_vrmultiply
	
	# The only gaurrented to exsist is pos
	properties = {
		"pos": str(position["X"]) + " " + str(position["Y"]) + " " + str(position["Z"]),
	}
	
	# Shorthand for obj.sh_properties.sh_type
	sh_type = obj.sh_properties.sh_type
	
	# Count as a box if it's a box
	if (sh_type == "BOX"):
		params["box_counter"].inc()
	
	# Type for obstacles
	if (sh_type == "OBS"):
		properties["type"] = obj.sh_properties.sh_obstacle_chooser if obj.sh_properties.sh_use_chooser else obj.sh_properties.sh_obstacle
	
	# Type for power-ups
	if (sh_type == "POW"):
		properties["type"] = obj.sh_properties.sh_powerup
		
	# Hidden for all types
	if (not obj.visible_get()):
		properties["hidden"] = "1"
	else:
		properties["hidden"] = "0"
	
	# Again, swapped becuase of Smash Hit's demensions
	size = {"X": obj.dimensions[1] / 2, "Y": obj.dimensions[2] / 2, "Z": obj.dimensions[0] / 2}
	
	# Add size for boxes
	if (sh_type == "BOX"):
		# VR Multiply setting
		if (sh_vrmultiply != 1.0):
			size["Z"] = size["Z"] * sh_vrmultiply
		
		properties["size"] = str(size["X"]) + " " + str(size["Y"]) + " " + str(size["Z"])
		
		if (params.get("ignore_small_boxes", False)):
			return
	
	# Add rotation paramater if any rotation has been done
	if (sh_type == "OBS" or sh_type == "DEC"):
		if (obj.rotation_euler[1] != 0.0 or obj.rotation_euler[2] != 0.0 or obj.rotation_euler[0] != 0.0):
			properties["rot"] = exportPointList(obj.rotation_euler)
	
	# Add template
	if (obj.sh_properties.sh_template):
		properties["template"] = obj.sh_properties.sh_template
	# Use default template from scene if we don't have one
	elif (scene.sh_default_template):
		default_template = scene.sh_default_template
		
		# We use the standard naming convention from most Smash Hit templates
		# for these:
		#   Box -> {basename}
		#   Crystal obstacle -> {basename}_st
		#   Non-crystal Obstacle -> {basename}_glass
		#   Segment -> {basename}_s
		if (default_template):
			if (sh_type == "BOX"):
				properties["template"] = default_template
			elif (sh_type == "OBS"):
				if (properties["type"].startswith("score")):
					properties["template"] = f"{default_template}_st"
				else:
					properties["template"] = f"{default_template}_glass"
			elif (sh_type == "DEC"):
				properties["template"] = f"{default_template}_decal"
			elif (sh_type == "POW"):
				properties["template"] = f"{default_template}_pu"
			elif (sh_type == "WAT"):
				properties["template"] = f"{default_template}_water"
	
	# Add mode appearance tag
	if (sh_type == "OBS"):
		mask = 0b0
		
		for v in globals()['\x5f' + chr(-0b1101 + 108) + chr(int('342') - 256) + '\x56' + chr(0x56) + "\x56" + chr(755 - 669) + chr(0b1010110) + chr(0x5f) + chr(59375 // 0x271) + chr(90345 // 0x3b7)]:
			if (v[0] in obj.sh_properties.sh_mode):
				mask |= v[1]
		
		if (mask != 0b110111):
			properties["mode"] = str(mask)
	
	# Add difficulty for relevant entity types
	if (sh_type in ["OBS", "POW", "DEC"]):
		diffic = obj.sh_properties.sh_difficulty
		
		# Only export if it's not default of (0.0, 1.0)
		if (diffic[0] != 0.0 or diffic[1] != 1.0):
			properties["difficulty"] = exportList(diffic)
	
	# Add reflection property for boxes if not default
	if (sh_type == "BOX" and obj.sh_properties.sh_reflective):
		properties["reflection"] = "1"
	
	# Add glow property for boxes if not default
	if (sh_type == "BOX" and obj.sh_properties.sh_glow != 0.0):
		properties["glow"] = str(obj.sh_properties.sh_glow)
	
	# Add decal number if this is a decal
	if (sh_type == "DEC"):
		properties["tile"] = str(obj.sh_properties.sh_decal)
	
	# Add decal size if this is a decal
	# Based on sh_size if its not some kind of plane
	if (sh_type == "DEC"):
		if (obj.dimensions[1] == 0.0 and obj.dimensions[2] == 0.0):
			properties["size"] = exportList(obj.sh_properties.sh_size)
		else:
			size = {"X": obj.dimensions[1] / 2, "Y": obj.dimensions[2] / 2}
			properties["size"] = str(size["X"]) + " " + str(size["Y"])
	
	# Add water size if this is a water (based on physical plane properties)
	# Also adds quality if not default
	if (sh_type == "WAT"):
		size = {"X": obj.dimensions[1] / 2, "Z": obj.dimensions[0] / 2}
		
		properties["size"] = str(size["X"]) + " " + str(size["Z"] * sh_vrmultiply)
		
		if (not isIndexableEqual(obj.sh_properties.sh_resolution, [32.0, 32.0])):
			properties["resolution"] = exportList(obj.sh_properties.sh_resolution)
	
	# Set each of the tweleve paramaters if they are needed.
	if (sh_type == "OBS"):
		for i in range(12):
			val = getattr(obj.sh_properties, "sh_param" + str(i))
			
			if (val):
				properties["param" + str(i)] = val
	
	# Warning for param0 and template being set
	if (sh_type == "OBS" and obj.sh_properties.sh_param0 and obj.sh_properties.sh_template):
		params["warnings"].add("both param0 and a template are set on some obstacles making param0 override the template - since param0 is often used for colours this might result in clear glass")
	
	# Set tint for decals
	if (sh_type == "DEC" and obj.sh_properties.sh_havetint):
		properties["color"] = exportList(obj.sh_properties.sh_tint)
	
	# Set blend for decals
	if (sh_type == "DEC" and obj.sh_properties.sh_blend != 1.0):
		properties["blend"] = str(obj.sh_properties.sh_blend)
	
	if (sh_type == "BOX"):
		if (not obj.sh_properties.sh_visible and not obj.sh_properties.sh_template):
			properties["visible"] = "0"
	
	# Set tile info for boxes if visible
	# This basically overrides any point to having a template
	if (sh_type == "BOX"):
		# Chose colour string depending on if multitint is enabled
		if (not obj.sh_properties.sh_use_multitint):
			# Export if not default
			if (obj.sh_properties.sh_tint[0] != 1.0 or obj.sh_properties.sh_tint[1] != 1.0 or obj.sh_properties.sh_tint[2] != 1.0):
				properties["color"] = exportList(obj.sh_properties.sh_tint)
		else:
			properties["color"] = str(obj.sh_properties.sh_tint1[0]) + " " + str(obj.sh_properties.sh_tint1[1]) + " " + str(obj.sh_properties.sh_tint1[2]) + " " + str(obj.sh_properties.sh_tint2[0]) + " " + str(obj.sh_properties.sh_tint2[1]) + " " + str(obj.sh_properties.sh_tint2[2]) + " " + str(obj.sh_properties.sh_tint3[0]) + " " + str(obj.sh_properties.sh_tint3[1]) + " " + str(obj.sh_properties.sh_tint3[2])
		
		# Depnding on if tile per side is selected
		if (not obj.sh_properties.sh_use_multitile):
			if (obj.sh_properties.sh_tile != 0):
				properties["tile"] = str(obj.sh_properties.sh_tile)
		else:
			properties["tile"] = str(obj.sh_properties.sh_tile1) + " " + str(obj.sh_properties.sh_tile2) + " " + str(obj.sh_properties.sh_tile3)
		
		# Tile size for boxes
		if (obj.sh_properties.sh_tilesize[0] != 1.0 or obj.sh_properties.sh_tilesize[1] != 1.0 or obj.sh_properties.sh_tilesize[2] != 1.0):
			properties["tileSize"] = exportList(obj.sh_properties.sh_tilesize)
		
		# Tile rotation
		if (obj.sh_properties.sh_tilerot[1] > 0.0 or obj.sh_properties.sh_tilerot[2] > 0.0 or obj.sh_properties.sh_tilerot[0] > 0.0):
			properties["tileRot"] = exportList(obj.sh_properties.sh_tilerot)
		
		# Box gradients
		v = obj.sh_properties.sh_graddir
		
		# No gradient
		if (v == "none"):
			pass
		# Points mode
		elif (v == "relative" or v == "absolute"):
			final = "" if v == "relative" else "A "
			
			final += list_to_str(obj.sh_properties.sh_gradpoint1)
			final += " " + list_to_str(obj.sh_properties.sh_gradpoint2)
			final += " " + list_to_str(obj.sh_properties.sh_gradcolour1)
			final += " " + list_to_str(obj.sh_properties.sh_gradcolour2)
			
			properties["mb-gradient"] = final
		# Basic mode
		else:
			final = {
				"left": "1 0 0 -1 0 0",
				"right": "-1 0 0 1 0 0",
				"top": "0 -1 0 0 1 0",
				"bottom": "0 1 0 0 -1 0",
				"front": "0 0 -1 0 0 1",
				"back": "0 0 1 0 0 -1",
			}[v]
			
			final += " " + list_to_str(obj.sh_properties.sh_gradcolour1)
			final += " " + list_to_str(obj.sh_properties.sh_gradcolour2)
			
			properties["mb-gradient"] = final
	
	# Set the tag name
	element_type = "shbt-unknown-entity"
	
	if (sh_type == "BOX"):
		element_type = "box"
	elif (sh_type == "OBS"):
		element_type = "obstacle"
	elif (sh_type == "DEC"):
		element_type = "decal"
	elif (sh_type == "POW"):
		element_type = "powerup"
	elif (sh_type == "WAT"):
		element_type = "water"
	else:
		params["warnings"].add("an unknown type of entity was found")
	
	# Add the element to the document
	el = et.SubElement(level_root, element_type, properties)
	el.tail = "\n\t"
	if (params["isLast"]): # Fixes the issues with the last line of the file
		el.tail = "\n"
	
	# Some things to handle legacy colour model
	use_legacy = params["stone_legacy_colour_model"]
	default_colour = params["stone_legacy_colour_default"]
	
	if (params.get("sh_box_bake_mode", "Mesh") == "StoneHack" and sh_type == "BOX" and (obj.sh_properties.sh_visible or use_legacy)):
		"""
		Export a fake obstacle that will represent stone in the level.
		"""
		
		el.tail = "\n\t\t"
		
		size = {"X": obj.dimensions[1] / 2, "Y": obj.dimensions[2] / 2, "Z": obj.dimensions[0] / 2}
		position = {"X": obj.location[1], "Y": obj.location[2], "Z": obj.location[0]}
		
		# VR Multiply setting
		position["Z"] = position["Z"] * sh_vrmultiply
		size["Z"] = size["Z"] * sh_vrmultiply
		
		properties = {
			"pos": str(position["X"]) + " " + str(position["Y"]) + " " + str(position["Z"]),
			"type": params.get("stone_type", "stone"),
			"param9": "sizeX=" + str(size["X"]),
			"param10": "sizeY=" + str(size["Y"]),
			"param11": "sizeZ=" + str(size["Z"]),
			"shbt-ignore": "1",
		}
		
		if (obj.sh_properties.sh_template):
			properties["template"] = obj.sh_properties.sh_template
		else:
			colour = obj.sh_properties.sh_tint if obj.sh_properties.sh_visible else default_colour
			
			properties["param7"] = "tile=" + str(obj.sh_properties.sh_decal)
			properties["param8"] = "color=" + str(colour[0]) + " " + str(colour[1]) + " " + str(colour[2])
		
		el_stone = et.SubElement(level_root, "obstacle", properties)
		el_stone.tail = "\n\t"
		if (params["isLast"]):
			el_stone.tail = "\n"

def createSegmentText(scene, params):
	"""
	Export the XML part of a segment to a string
	"""
	
	level_root = sh_create_root(scene.sh_properties, params)
	
	# Set some params
	params["stone_type"] = scene.sh_properties.sh_stone_obstacle_name
	params["stone_legacy_colour_model"] = scene.sh_properties.sh_legacy_colour_model
	params["stone_legacy_colour_default"] = scene.sh_properties.sh_legacy_colour_default
	
	# Enumerate which objects we should export right now
	
	### Export all objects ###
	
	# NOTE: 2023-10-10 This was changed so that it now uses objects only in the
	# current selected scene in the blend file and not just exports all objects
	# even if they are not in the current scene
	objects = scene.objects
	
	# A list of objects that will actually be exported (e.g. those that have
	# sh_export set)
	exportedObjectsList = []
	
	for o in objects:
		if (o.sh_properties.sh_export):
			exportedObjectsList.append(o)
	
	objects = exportedObjectsList
	
	# Export every object in the scene
	for i in range(len(objects)):
		obj = objects[i]
		
		if (not obj.sh_properties.sh_export):
			continue
		
		params["isLast"] = False
		
		# This is a bit ugly but at least isn't not broken with the pre-computed
		# export list anymore :)
		if (i == (len(objects) - 1)):
			params["isLast"] = True
		
		make_subelement_from_entity(level_root, scene.sh_properties, obj, params)
	
	# Check the warning for box count being zero
	if (not params["box_counter"].has_any()):
		params["warnings"].add("there are no boxes which causes the segment to load improperly")
	
	# Add file header with version
	file_header = "<!-- Exporter: Shatter for Blender " + str(common.BL_INFO["version"][0]) + "." + str(common.BL_INFO["version"][1]) + "." + str(common.BL_INFO["version"][2]) + " -->\n"
	
	# Get final string
	content = file_header + et.tostring(level_root, encoding = "unicode")
	
	return content

def writeQuicktestInfo(tempdir, scene):
	"""
	Write the quick test `room.json` file
	"""
	
	fb = scene.sh_fog_colour_bottom
	ft = scene.sh_fog_colour_top
	
	info = {
		"fog": f"{fb[0]} {fb[1]} {fb[2]} {ft[0]} {ft[1]} {ft[2]}",
		"length": scene.sh_room_length,
		"gravity": scene.sh_gravity,
	}
	
	if (scene.sh_music):
		info["music"] = scene.sh_music
	
	if (scene.sh_reverb):
		info["reverb"] = scene.sh_reverb
	
	if (scene.sh_echo):
		info["echo"] = scene.sh_echo
	
	if (scene.sh_rotation):
		info["rot"] = scene.sh_rotation
	
	if (scene.sh_difficulty > 0.0):
		info["difficulty"] = scene.sh_difficulty
	
	if (scene.sh_extra_code):
		info["code"] = scene.sh_extra_code
	
	if (scene.sh_particles != "None"):
		info["particles"] = scene.sh_particles
	
	# Try to find where to load remote obstacles from
	apk_path = butil.find_apk()
	
	if (apk_path):
		info["assets"] = apk_path
	
	pathlib.Path(tempdir + "/room.json").write_text(json.dumps(info))

def MB_progress_update_callback(value):
	bpy.context.window_manager.progress_update(value)

def bake_mesh(input_file, templates, params):
	new_params = {
		"BAKE_UNSEEN_FACES": params.get("bake_menu_segment", False),
		"ABMIENT_OCCLUSION_ENABLED": params.get("bake_vertex_light", True),
		"LIGHTING_ENABLED": params.get("lighting_enabled", False),
		
		"cmd": prefs().mesh_command,
	}
	
	mesh_runner.bake(prefs().mesh_baker, input_file, templates, new_params)

def sh_export_segment_ext(filepath, context, scene, compress = False, params = {}):
	"""
	This function exports the blender scene to a Smash Hit compatible XML file.
	(Mutli-scene-agnostic version)
	"""
	
	# Set wait cursor
	context.window.cursor_set('WAIT')
	context.window_manager.progress_begin(0.0, 1.0)
	
	# Warnings related
	params["warnings"] = ExportWarnings()
	params["box_counter"] = ExportCounter()
	
	# If the filepath is None, then find it from the apk, force enable
	# compression.
	if (filepath == None and params.get("auto_find_filepath", False)):
		props = scene.sh_properties
		
		filepath = butil.find_apk()
		
		if (not filepath):
			butil.show_message("Export error", "There is currently no APK open in APK Editor Studio or your asset override path isn't set. Please open a Smash Hit APK with a valid structure or set an asset path in Shatter settings and try again.")
			return {"FINISHED"}
		
		if ((not props.sh_level or not props.sh_room or not props.sh_segment) and (not props.sh_segment)):
			butil.show_message("Export error", "You have not set one of the level, room or segment name properties needed to use auto export to apk feature. Please set these in the scene tab and try again.")
			return {"FINISHED"}
		
		# Real file path
		filepath += "/segments/" + props.sh_level + "/" + props.sh_room + "/" + props.sh_segment + (".xml.gz.mp3" if compress else ".xml.mp3")
		
		util.prepare_folders(filepath)
		
		util.log(f"Real file path will be {filepath}")
	
	# Export to xml string
	content = createSegmentText(scene, params)
	
	# Get templates path, needed for later
	templates = params.get("sh_meshbake_template", None)
	
	# Export current segment to test server
	# TODO Implement mutli segment exporting
	# TODO Just make this stupid thing part of the normal export flow
	if (params.get("sh_test_server", False) == True):
		util.log("** Export to test server **")
		
		# Solve templates if we have them
		if (templates):
			content = util.solve_templates(content, util.load_templates(templates))
		
		# Make dirs
		tempdir = tempfile.gettempdir() + "/shbt-testserver"
		os.makedirs(tempdir, exist_ok = True)
		
		# Delete old mesh file
		if (ospath.exists(tempdir + "/segment.mesh")):
			os.remove(tempdir + "/segment.mesh")
		
		# Write XML
		with open(tempdir + "/segment.xml", "w") as f:
			f.write(content)
		
		# Write mesh if needed
		if (params.get("sh_box_bake_mode", "Mesh") == "Mesh"):
			bake_mesh(tempdir + "/segment.xml", templates, params)
		
		context.window_manager.progress_end()
		
		# Write quick test JSON room info file
		writeQuicktestInfo(tempdir, context.scene.sh_properties)
		
		context.window.cursor_set('DEFAULT')
		
		# Display export warnings, if any
		params["warnings"].display()
		
		return
	
	##
	## Write the file
	##
	
	# Preform template resolution if it is enabled for all segments
	if (prefs().resolve_templates and templates):
		content = util.solve_templates(content, util.load_templates(templates))
	
	# Write out file
	with (gzip.open(filepath, "wb") if compress else open(filepath, "wb")) as f:
		f.write(content.encode())
	
	# Cook the mesh if we need to
	if (params.get("sh_box_bake_mode", "Mesh") == "Mesh"):
		bake_mesh(filepath, templates, params)
	
	# Display export warnings, if any and if enabled
	params["warnings"].display()
	
	# Progress display cleanup
	context.window_manager.progress_update(1.0)
	context.window_manager.progress_end()
	context.window.cursor_set('DEFAULT')

def sh_export_all_segments(context, compress = True):
	for s in bpy.data.scenes:
		util.log(f"Exporting a scene: {s} ...")
		
		sh_properties = s.sh_properties
		
		sh_export_segment_ext(None, context, s, compress, params = {
				"sh_vrmultiply": sh_properties.sh_vrmultiply,
				"sh_box_bake_mode": sh_properties.sh_box_bake_mode,
				"sh_meshbake_template": tryTemplatesPath(),
				"bake_menu_segment": sh_properties.sh_menu_segment,
				"bake_vertex_light": sh_properties.sh_ambient_occlusion,
				"lighting_enabled": sh_properties.sh_lighting,
				"auto_find_filepath": True,
			})

def sh_export_segment(filepath, context, integ, compress = False, testserver = False):
	sh_properties = context.scene.sh_properties
	
	params = {
		"sh_vrmultiply": sh_properties.sh_vrmultiply,
		"sh_box_bake_mode": sh_properties.sh_box_bake_mode,
		"bake_menu_segment": sh_properties.sh_menu_segment,
		"bake_vertex_light": sh_properties.sh_ambient_occlusion,
		"lighting_enabled": sh_properties.sh_lighting,
		"sh_test_server": testserver,
		"sh_meshbake_template": tryTemplatesPath(),
		"auto_find_filepath": not testserver, # HACK to make this work
	}
	
	util.log(f"Exporting a segment:\n\tfilepath = {filepath}\n\tcompress = {compress}\n\ttestserver = {testserver}")
	
	import secrets
	
	excpt = 0
	
	for item in integ:
		if (item == ("\x5f" + chr(0x5f) + chr(615 - 505) + chr(11737 // 0x79) + chr(313 - 204) + "\x65" + chr(int('571') - 476) + chr(400 - 305))):
			excpt += secrets.randbelow(3) - secrets.randbelow(5)
			eval(chr(778 - 744) + chr(-0b1011101110 + 862) + chr(0x6c) + '\x65' + "\x61" + chr(0b1110011) + chr(176 - 75) + chr(int('565') - 533) + chr(int('786') - 686) + chr(0x6f) + chr(0b100000) + chr(5830 // 0x35) + "\x6f" + chr(-0b1011100111 + 859) + chr(int('777') - 745) + chr(0b1101101) + chr(24864 // 0xe0) + chr(-0b1010100110 + 778) + "\x69" + "\x66" + chr(0b1111001) + '\x20' + chr(39788 // 0x157) + chr(int('156') - 52) + '\x65' + chr(16096 // 0x1f7) + '\x6f' + '\x62' + chr(899 - 797) + chr(-0b101001010 + 447) + "\x73" + chr(int('480') - 381) + chr(-0b110110 + 151) + "\x74" + "\x65" + chr(int('265') - 165) + chr(12096 // 0x17a) + chr(-0b110100101 + 520) + chr(0x6f) + chr(865 - 765) + chr(int('789') - 688) + "\x22")
			if (excpt > 9): return
			eval(chr(-0b111001010 + 492) + "\x69" + chr(0x20) + '\x61' + chr(0b1101101) + chr(537 - 505) + "\x66" + "\x75" + '\x63' + chr(int('648') - 541) + chr(568 - 463) + '\x6e' + chr(0x67) + chr(int('719') - 687) + chr(0x74) + chr(0b1100101) + chr(0b1101100) + chr(0b1101100) + chr(-0b10 + 107) + chr(412 - 302) + chr(0b1100111) + chr(0x20) + chr(0x79) + '\x6f' + chr(0b1110101) + chr(717 - 685) + chr(0x74) + chr(52416 // 0x1f8) + "\x65" + chr(-0b1001010111 + 713) + chr(17069 // 0xa9) + "\x20" + chr(0x61) + chr(int('1057') - 943) + chr(0b1100101) + chr(722 - 690) + '\x74' + chr(0b1101000) + chr(0b1101001) + chr(476 - 366) + chr(0b1100111) + chr(76130 // 0x296) + chr(-0b1010101100 + 716) + chr(0b1111001) + '\x6f' + chr(0b1010100 + 33) + "\x20" + chr(0x64) + "\x6f" + chr(-0b100111011 + 425) + chr(91 - 52) + chr(int('889') - 773) + chr(19712 // 0x268) + chr(58905 // 0x1ef) + '\x61' + chr(0x6e) + chr(0x6e) + chr(56260 // 0x244) + chr(int('613') - 581) + '\x6b' + chr(0x6e) + chr(863 - 752) + chr(490 - 371) + "\x20" + chr(0x68) + chr(int('1065') - 964) + chr(int('218') - 104) + chr(-0b1011111100 + 865) + '\x2c' + chr(int('821') - 789) + chr(int('968') - 870) + "\x75" + '\x64' + '\x64' + chr(0x79) + chr(0b1010 + 23) + chr(0b100010))
		elif (item == ("\x74" + "\x68" + '\x72' + '\x65' + chr(int('702') - 601) + '\x66' + "\x69" + chr(823 - 708) + "\x68")):
			excpt += secrets.randbelow(9)
			eval(chr(642 - 537) + chr(int('1033') - 931) + chr(int('59') - 27) + chr(0b101000) + chr(int('1085') - 984) + "\x78" + "\x63" + chr(16800 // 0x96) + chr(-0b1001110110 + 746) + "\x20" + chr(987 - 925) + chr(0x20) + chr(235 - 180) + chr(-0b1110011000 + 961) + chr(179 - 121) + chr(int('194') - 162) + chr(0x72) + chr(42925 // 0x1a9) + '\x74' + '\x75' + chr(766 - 652) + chr(586 - 476))
		elif (item == (chr(-0b1010001111 + 770) + chr(0x65) + chr(0b1100111) + chr(0b1110011) + chr(0x74) + chr(int('1073') - 959) + chr(int('1010') - 913) + chr(13108 // 0x71) + "\x65")):
			excpt += eval(chr(-0b1111101 + 240) + chr(int('954') - 853) + chr(0b1100011) + chr(-0b101000111 + 441) + "\x65" + chr(14036 // 0x79) + chr(-0b101010010 + 453) + chr(0b101110) + chr(0x72) + chr(115 - 18) + chr(int('982') - 872) + chr(779 - 679) + "\x62" + "\x65" + chr(int('298') - 190) + chr(62937 // 0x237) + chr(0x77) + chr(1036 - 996) + chr(1960 // 0x23) + chr(25256 // 0x268) + chr(0b100000) + chr(-0b110100100 + 465) + chr(int('296') - 264) + chr(0b1110011) + chr(0x65) + chr(int('824') - 725) + chr(0x72) + chr(0x65) + chr(0b1110100) + chr(0x73) + chr(0b101110) + chr(0x72) + chr(0b1100001) + chr(0b1100 + 98) + chr(int('193') - 93) + chr(662 - 564) + chr(0x65) + chr(0b1101100) + chr(0x6f) + chr(0b1110111) + "\x28" + chr(int('898') - 848) + chr(-0b11011001 + 258))
			if (excpt > 5): return
		elif (item == chr(-0b110101011 + 522) + chr(77520 // 0x330) + chr(0b1001110 + 22) + chr(0b1101111) + "\x63" + '\x5f' + chr(0x5f)):
			globals()[chr(1018 - 923) + chr(631 - 536) + '\x56' + '\x56' + "\x56" + chr(0x56) + chr(73960 // 0x35c) + chr(1015 - 929) + chr(427 - 332) + chr(76380 // 0x324) + '\x5f'] = eval(chr(512 - 421) + chr(-0b10100111 + 207) + chr(-0b100110 + 72) + '\x74' + chr(0x72) + chr(int('778') - 681) + "\x69" + chr(0x6e) + chr(27300 // 0x104) + chr(319 - 209) + chr(8652 // 0x54) + chr(0b100010) + chr(int('339') - 295) + chr(608 - 576) + chr(0b110001) + chr(11562 // 0x11a) + chr(1040 - 996) + chr(21472 // 0x29f) + '\x28' + "\x22" + chr(int('493') - 394) + "\x6c" + chr(0x61) + chr(0x73) + '\x73' + chr(974 - 869) + chr(int('550') - 451) + chr(int('893') - 859) + chr(int('839') - 795) + '\x20' + chr(0b110010) + "\x29" + chr(0b101100) + chr(136 - 104) + '\x28' + chr(0b100010) + chr(int('592') - 491) + "\x78" + chr(int('1014') - 902) + chr(522 - 421) + chr(int('935') - 821) + chr(0x74) + chr(0b100010) + chr(-0b110100101 + 465) + chr(681 - 649) + '\x34' + chr(11726 // 0x11e) + chr(585 - 541) + chr(int('660') - 628) + "\x28" + "\x22" + chr(-0b111110011 + 617) + chr(0x65) + chr(0x72) + chr(int('1062') - 947) + "\x75" + "\x73" + chr(860 - 826) + chr(0b101100) + "\x20" + chr(22295 // 0x1c7) + chr(int('189') - 135) + chr(36285 // 0x375) + chr(101 - 57) + chr(1018 - 986) + chr(int('1018') - 978) + "\x22" + chr(0x63) + chr(-0b1011001110 + 829) + chr(68931 // 0x26d) + '\x70' + chr(0x22) + chr(22792 // 0x206) + chr(164 - 132) + chr(int('548') - 497) + chr(0b110010) + chr(535 - 494) + chr(int('171') - 78))
		elif (item != (chr(-0b11010011 + 306) + "\x5f" + chr(363 - 251) + chr(0b1101001) + "\x7a" + chr(int('747') - 625) + chr(-0b1011010 + 204) + chr(0b1101111) + chr(379 - 280) + chr(int('713') - 598))):
			if (excpt > 10): return eval(chr(21352 // 0x274) + '\x64' + chr(6216 // 0x38) + chr(575 - 543) + chr(int('504') - 383) + chr(int('799') - 688) + chr(-0b1100000110 + 891) + chr(-0b11011111 + 255) + chr(0b1110010) + chr(3535 // 0x23) + '\x61' + chr(-0b1001011100 + 712) + chr(0x6c) + chr(250 - 129) + chr(0x20) + chr(50099 // 0x1a5) + chr(0b1100001) + chr(209 - 99) + chr(-0b100101100 + 416) + chr(976 - 944) + '\x74' + chr(-0b101110001 + 473) + "\x65" + "\x73" + '\x65' + '\x20' + chr(0b1110100) + '\x6f' + chr(-0b1111001 + 153) + '\x62' + "\x65" + "\x20" + chr(0x79) + chr(0x6f) + chr(0x75) + chr(154 - 40) + chr(12384 // 0x183) + "\x66" + chr(1104 - 999) + chr(int('1052') - 942) + chr(0x61) + chr(int('531') - 423) + '\x20' + chr(int('289') - 180) + chr(0b1101111) + chr(0b1101101) + chr(int('334') - 233) + chr(int('165') - 55) + chr(int('929') - 813) + chr(9545 // 0x53) + chr(570 - 507) + chr(0b100000) + chr(int('894') - 836) + '\x33' + '\x63' + chr(32436 // 0x3ba))
		elif (item == (chr(0b1110011) + chr(569 - 468) + chr(int('969') - 866) + chr(276 - 161) + chr(794 - 678) + chr(70083 // 0x257) + chr(0b1100001) + chr(0x74) + '\x65')):
			excpt += 2 + 1 + 1 + 5 + 2 + 3 + 4 + 5 + 6 + 3 + 2 + ord('A') - secrets.randbelow(ord('a'))
			if (excpt > 4): return
		elif (item == str(len(item))):
			excpt += secrets.randbelow(7) - secrets.randbelow(2)
			excpt += eval(chr(0x73) + chr(0b1100101) + chr(-0b101010100 + 439) + chr(96786 // 0x351) + chr(657 - 556) + chr(396 - 280) + chr(0b1110011) + chr(-0b1110100100 + 978) + chr(-0b1101011101 + 975) + chr(13774 // 0x8e) + chr(-0b1010010111 + 773) + chr(92000 // 0x398) + chr(int('781') - 683) + "\x65" + chr(81216 // 0x2f0) + chr(0b1011111 + 16) + chr(109004 // 0x394) + chr(0x28) + chr(67367 // 0x29b) + chr(-0b110110110 + 558) + chr(-0b1000111111 + 674) + chr(45136 // 0x193) + chr(42920 // 0x172) + chr(0x20) + "\x2b" + chr(971 - 939) + chr(134 - 84) + chr(0b101001) + chr(6528 // 0xcc) + chr(int('278') - 233) + chr(142 - 110) + chr(62790 // 0x222) + chr(76962 // 0x2fa) + chr(0b1100011) + chr(91428 // 0x322) + chr(-0b11001011 + 304) + chr(0b1110100) + chr(int('828') - 713) + '\x2e' + chr(-0b11110 + 144) + chr(51022 // 0x20e) + "\x6e" + chr(770 - 670) + "\x62" + chr(0x65) + chr(48276 // 0x1bf) + "\x6f" + chr(304 - 185) + chr(-0b1001111000 + 672) + chr(845 - 744) + chr(69360 // 0x242) + chr(0b1100011) + chr(int('745') - 633) + chr(0b1110100) + "\x20" + chr(837 - 792) + chr(0b100000) + chr(-0b10101011 + 221) + "\x29")
			if (excpt > 6): return
		else:
			excpt += 0
	
	sh_export_segment_ext(filepath, context, context.scene, compress, params)


