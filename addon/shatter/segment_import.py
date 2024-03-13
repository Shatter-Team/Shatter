"""
Smash Hit Blender Tools segment import
"""

import xml.etree.ElementTree as et
import bpy
import gzip
import util as util
import butil as butil
import common as common

def sh_import_modes(s):
	"""
	Import a mode string
	"""
	
	mask = int(s)
	res = set()
	
	for v in [("training", 1), ("classic", 2), ("expert", 4), ("versus", 16), ("coop", 32)]:
		if ((mask & v[1]) == v[1]):
			res.add(v[0])
	
	return res

# These are here becuase they used to be exclusive to this file
sh_add_box = butil.add_box
sh_add_empty = butil.add_empty

def sh_parse_tile(s):
	"""
	Parse tile strings
	"""
	
	string = s.split()
	final = []
	
	for i in range(len(string)):
		final.append(max(min(int(string[i]), 63), 0))
	
	return final

def sh_parse_tile_size(s):
	"""
	Parse tile strings
	"""
	
	string = s.split()
	final = []
	
	for i in range(len(string)):
		final.append(float(string[i]))
	
	return final

def sh_parse_colour(s):
	"""
	Parse colour strings
	"""
	
	a = s.split()
	
	if (len(a) < 9):
		return [(float(a[0]), float(a[1]), float(a[2]))]
	else:
		return [
			(float(a[0]), float(a[1]), float(a[2])),
			(float(a[3]), float(a[4]), float(a[5])),
			(float(a[6]), float(a[7]), float(a[8]))
		]

def sh_parse_string_array(string, T = float, fallbacks = None):
	"""
	Generic utility to parse a string of type T. It also supports fallback
	values if e.g. something stupid like difficulty=" " appears (e.g.
	city/narrow/16_5)
	"""
	
	string = string.split()
	
	data = []
	
	for item in string:
		data.append(T(item))
	
	# If we don't have enough items, start appending the zero element
	if (fallbacks != None and len(data) < len(fallbacks)):
		for i in range(len(data), len(fallbacks)):
			data.append(fallbacks[i])
	
	return data

show_message = butil.show_message

def sh_import_segment(fp, context, compressed = False):
	"""
	Load a Smash Hit segment into blender
	"""
	
	root = None
	
	if (not compressed):
		with open(fp, "r") as f:
			root = f.read()
	else:
		with gzip.open(fp, "rb") as f:
			root = f.read().decode()
	
	root = et.fromstring(root)
	
	# Validate we have a proper segment (why tf didn't we do this until 2023 :|)
	if (root.tag != "segment"):
		show_message("Import error", "This is not a valid segment file: root tag is not 'segment'.")
		return {"FINISHED"}
	
	scene = context.scene.sh_properties
	segattr = root.attrib
	
	# For keeping track if there were any warnings
	warnings = set()
	
	# Check segment protection and enforce it
	# 
	# These are not designed to stop someone really dedicated from stealing
	# segments, but it should stop someone from casually copying segments.
	drm = segattr.get("drm", None)
	
	if (drm):
		drm = drm.split()
		
		for d in drm:
			if (d == "NoImport" or d == "no_import"):
				show_message("Import error", "The creator of this segment has requested that it not be imported. While you could bypass this, we encourage you to respect this request.")
				return {"FINISHED"}
			
			else:
				warnings.add(f"an unknown type of drm '{d}' is being used")
	
	# Segment length
	seg_size = segattr.get("size", "20 5 20").split()
	scene.sh_len = (float(seg_size[0]), float(seg_size[1]), float(seg_size[2]))
	
	if (scene.sh_len[2] <= 0.0):
		warnings.add("the segment has a Z-size value of 0 or less which may cause problems when exported")
	
	# Default template
	# 
	# NOTE: The decision to keep the current value if it is not set in the
	# importing segment is intentional. This makes it so that if you specify the
	# default template *before* import, the segment will auto-convert to using
	# default templates.
	default_template = segattr.get("shbt-default-template", "")
	scene.sh_default_template = default_template if default_template else scene.sh_default_template
	
	# Segment template
	segment_template = segattr.get("template", "")
	
	# If it is the same as if it were exported with default templates and
	# default is set then we can make it blank
	if (scene.sh_default_template and segment_template == f"{scene.sh_default_template}_s"):
		segment_template = ""
	
	scene.sh_template = segment_template
	
	# Soft shadow
	scene.sh_softshadow = float(segattr.get("softshadow", "0.6"))
	
	# Lights
	scene.sh_light_left = float(segattr.get("lightLeft", "1"))
	scene.sh_light_right = float(segattr.get("lightRight", "1"))
	scene.sh_light_top = float(segattr.get("lightTop", "1"))
	scene.sh_light_bottom = float(segattr.get("lightBottom", "1"))
	scene.sh_light_front = float(segattr.get("lightFront", "1"))
	scene.sh_light_back = float(segattr.get("lightBack", "1"))
	
	# Fog color
	fogcolor = segattr.get("fogcolor", None)
	
	if (fogcolor):
		fog = fogcolor.split()
		
		no_gradient = (len(fog) == 3)
		
		scene.sh_fog_colour_bottom = (
			float(fog[0]),
			float(fog[1]),
			float(fog[2]),
		)
		
		scene.sh_fog_colour_top = (
			float(fog[0]) if no_gradient else float(fog[3]),
			float(fog[1]) if no_gradient else float(fog[4]),
			float(fog[2]) if no_gradient else float(fog[5]),
		)
	
	# ambient, if lighting is enabled
	lighting_ambient = segattr.get("ambient", None)
	
	if (lighting_ambient):
		scene.sh_lighting = True
		scene.sh_lighting_ambient = sh_parse_colour(lighting_ambient)[0]
	else:
		scene.sh_lighting = False
	
	# Check for deprecated segment tags and warn about them
	if (segattr.get("meshbake_lightFactor") or segattr.get("meshbake_disableLight")):
		warnings.add("legacy meshbake tags were detected which means exported segments will look significantly different when exported with the current version of Shatter")
	
	# ##########################################################################
	# Process entities
	box_count = 0
	
	for obj in root:
		kind = obj.tag
		properties = obj.attrib
		
		# Ignore obstacles exported with IMPORT_IGNORE="STONEHACK_IGNORE"
		if (properties.get("IMPORT_IGNORE") or properties.get("shbt-ignore")):
			continue
		
		if (properties.get("type") == "stone"):
			warnings.add("an obstacle was ignored becuase it had a type of 'stone' but it didn't have the 'IMPORT_IGNORE' or 'shbt-ignore' attribute set")
			continue
		
		# Object position
		pos = properties.get("pos", "0 0 0").split()
		pos = (float(pos[2]), float(pos[0]), float(pos[1]))
		
		# Object rotation
		rot = properties.get("rot", "0 0 0").split()
		rot = (float(rot[2]), float(rot[0]), float(rot[1]))
		
		# Boxes
		if (kind == "box"):
			box_count += 1
			
			# Size for boxes
			size = properties.get("size", "0 0 0").split()
			size = (float(size[2]), float(size[0]), float(size[1]))
			
			# Add the box; zero size boxes are treated as points
			b = None
			if (size[0] <= 0.0 and size[1] <= 0.0 and size[2] <= 0.0):
				b = sh_add_empty()
				b.location = pos
			else:
				b = sh_add_box(pos, size)
			
			# Boxes can (and often do) have templates
			b.sh_properties.sh_template = properties.get("template", "")
			
			# Reflective property
			b.sh_properties.sh_reflective = (properties.get("reflection", "0") == "1")
			
			# visible, colour, tile for boxes
			# NOTE: Tile size and rotation are not supported those are not imported yet
			# NOTE: Extra template logic is here because built-in box baking tools will only
			# inherit visible from template when visible is not set at all, and since
			# it is not possible to tell blender tools to explicitly inherit from
			# a template we need to settle with less than ideal but probably the most
			# intuitive behaviour in order to have box templates work: we do not
			# include visible if there is a template and visible is not set.
			b.sh_properties.sh_visible = (properties.get("visible", "1") == "1" and not b.sh_properties.sh_template)
			
			# NOTE: The older format colorX/Y/Z is no longer supported, should it be readded?
			colour = sh_parse_colour(properties.get("color", "1 1 1"))
			
			if (len(colour) == 1):
				b.sh_properties.sh_tint = (colour[0][0], colour[0][1], colour[0][2], 1.0)
			else:
				b.sh_properties.sh_use_multitint = True
				b.sh_properties.sh_tint1 = (colour[0][0], colour[0][1], colour[0][2], 1.0)
				b.sh_properties.sh_tint2 = (colour[1][0], colour[1][1], colour[1][2], 1.0)
				b.sh_properties.sh_tint3 = (colour[2][0], colour[2][1], colour[2][2], 1.0)
			
			# NOTE: The older format tileX/Y/Z is no longer supported, should it be readded?
			tile = sh_parse_tile(properties.get("tile", "0"))
			
			if (len(tile) == 1):
				b.sh_properties.sh_tile = tile[0]
			else:
				b.sh_properties.sh_use_multitile = True
				b.sh_properties.sh_tile1 = tile[0]
				b.sh_properties.sh_tile2 = tile[1]
				b.sh_properties.sh_tile3 = tile[2]
			
			# Tile size
			tileSize = sh_parse_tile_size(properties.get("tileSize", "1"))
			tileSizeLen = len(tileSize)
			
			# Clever trick to parse the tile sizes; for 1 tilesize this applies
			# to all sides, for 3 tilesize this applies each tilesize to their
			# proper demension. (If there are two, they are assigned "X Y" -> X Y Y
			# but that should never happen)
			for i in range(3):
				b.sh_properties.sh_tilesize[i] = tileSize[min(i, tileSizeLen - 1)]
			
			# TODO: I'm not adding sh_parse_tilerot for now...
			tileRot = sh_parse_tile(properties.get("tileRot", "0"))
			tileRotLen = len(tileRot)
			
			for i in range(3):
				b.sh_properties.sh_tilerot[i] = tileRot[min(i, tileRotLen - 1)] % 4 # HACK: ... so I'm doing this :)
			
			# Parse older tile and colour info (e.g. the ones with X/Y/Z at the end)
			# It looks like this: <box size="14.0 0.5 10.0" pos="0.0 -0.5 -10.0" hidden="0" tileY="3" colorY=".9 .9 .9" tileSize="2 2 2"/>
			# These are mostly in the segments/[1-3] folder in 0.8.0
			# It seems like these might still use the normal overloaded tileSize
			# so I'm not having that for now
			for t in "XYZ":
				# TEH TILEZ
				tile = properties.get(f"tile{t}", None)
				
				### tileX/Y/Z ###
				if (tile):
					# Set multitile mode if we have it
					b.sh_properties.sh_use_multitile = True
					
					# Set the respective tile
					n = str(ord(t) - ord("X") + 1)
					
					# We need to split like this becuase ideas/city.xml has a
					# really weird tileY that is the string "43 1". Maybe this
					# happens elsewhere also.
					setattr(b.sh_properties, f"sh_tile{n}", int(tile.split()[0]))
				
				### TEH COLOURZ ###
				color = properties.get(f"color{t}", None)
				
				# colorX/Y/Z
				if (color):
					# Set multitint mode if we have it
					b.sh_properties.sh_use_multitint = True
					
					# Set the respective colour
					n = str(ord(t) - ord("X") + 1)
					
					# Parse the colours into a tuple of (r, g, b, a)
					c = sh_parse_colour(color)[0]
					if (len(c) == 3): c = (c[0], c[1], c[2], 1.0)
					setattr(b.sh_properties, f"sh_tint{n}", c)
			
			# NOTE: Default template logic is here so it doesn't fuck up some
			# other stuff that depends on having the actual template value
			if (scene.sh_default_template and b.sh_properties.sh_template == scene.sh_default_template):
				b.sh_properties.sh_template = ""
			
			# Glow for lighting
			b.sh_properties.sh_glow = float(properties.get("glow", properties.get("mb-glow", "0")))
			
			# Gradient
			gradient = properties.get("mb-gradient", "")
			
			if (gradient):
				# Check if gradient is absolute or relative
				is_absolute = gradient.startswith("A ")
				
				# If it's absolute we need to set that and remove the prefix
				if (is_absolute):
					b.sh_properties.sh_graddir = "absolute"
					gradient = gradient[2:]
				# Otherwise it's just relative
				else:
					b.sh_properties.sh_graddir = "relative"
				
				# Convert to floats
				gradient = [float(x) for x in gradient.split()]
				
				# Set points and colours
				b.sh_properties.sh_gradpoint1 = gradient[0:3]
				b.sh_properties.sh_gradpoint2 = gradient[3:6]
				b.sh_properties.sh_gradcolour1 = gradient[6:9]
				b.sh_properties.sh_gradcolour2 = gradient[9:12]
			
			# Set hidden in editor or not
			b.hide_set(properties.get("hidden", "0") == "1")
		
		# Obstacles
		elif (kind == "obstacle"):
			# Create obstacle and set pos/rot
			o = sh_add_empty()
			o.location = pos
			o.rotation_euler = rot
			
			# Set type and add the attributes
			o.sh_properties.sh_type = "OBS"
			o.sh_properties.sh_obstacle = properties.get("type", "")
			o.sh_properties.sh_template = properties.get("template", "")
			o.sh_properties.sh_mode = sh_import_modes(properties.get("mode", "255"))
			o.sh_properties.sh_difficulty = sh_parse_string_array(properties.get("difficulty", "0 1"), fallbacks = [0, 1])
			o.sh_properties.sh_param0 = properties.get("param0", "")
			o.sh_properties.sh_param1 = properties.get("param1", "")
			o.sh_properties.sh_param2 = properties.get("param2", "")
			o.sh_properties.sh_param3 = properties.get("param3", "")
			o.sh_properties.sh_param4 = properties.get("param4", "")
			o.sh_properties.sh_param5 = properties.get("param5", "")
			o.sh_properties.sh_param6 = properties.get("param6", "")
			o.sh_properties.sh_param7 = properties.get("param7", "")
			o.sh_properties.sh_param8 = properties.get("param8", "")
			o.sh_properties.sh_param9 = properties.get("param9", "")
			o.sh_properties.sh_param10 = properties.get("param10", "")
			o.sh_properties.sh_param11 = properties.get("param11", "")
			o.hide_set(properties.get("hidden", "0") == "1")
			
			# Solve default templates
			if (scene.sh_default_template and 
				(
						(o.sh_properties.sh_obstacle.startswith("score") and o.sh_properties.sh_template == f"{scene.sh_default_template}_st") 
					or
						(not o.sh_properties.sh_obstacle.startswith("score") and o.sh_properties.sh_template == f"{scene.sh_default_template}_glass")
				)
			):
				o.sh_properties.sh_template = ""
		
		# Decals
		elif (kind == "decal"):
			# Create obstacle and set pos/rot
			o = sh_add_empty()
			o.location = pos
			o.rotation_euler = rot
			
			# Set type and tile number
			o.sh_properties.sh_type = "DEC"
			o.sh_properties.sh_decal = int(properties.get("tile", "0"))
			
			# Set the colourisation of the decal
			# TODO This can just be 1 1 1 1 by default and no need for havetint,
			# this is what smash hit does, dont really need to do it like this
			colour = properties.get("color", None)
			if (colour):
				o.sh_properties.sh_havetint = True
				colour = colour.split()
				colour = (float(colour[0]), float(colour[1]), float(colour[2]), float(colour[3]) if len(colour) == 4 else 1.0)
				o.sh_properties.sh_tint = colour
			else:
				o.sh_properties.sh_havetint = False
			
			# Blend mode
			o.sh_properties.sh_blend = float(properties.get("blend", "1"))
			
			# Set the hidden flag
			o.hide_set(properties.get("hidden", "0") == "1")
			
			# Set the difficulty
			o.sh_properties.sh_difficulty = sh_parse_string_array(properties.get("difficulty", "0 1"), fallbacks = [0, 1])
			
			# Size
			o.sh_properties.sh_size = sh_parse_tile_size(properties.get("size", "1 1"))[0:2]
		
		# Power-ups
		elif (kind == "powerup"):
			# Create obstacle and set pos
			o = sh_add_empty()
			o.location = pos
			
			# Set type and powerup kind
			o.sh_properties.sh_type = "POW"
			o.sh_properties.sh_powerup = properties.get("type", "ballfrenzy")
			
			# Set difficulty
			o.sh_properties.sh_difficulty = sh_parse_string_array(properties.get("difficulty", "0 1"), fallbacks = [0, 1])
			
			# Set hidden
			o.hide_set(properties.get("hidden", "0") == "1")
		
		# Water
		elif (kind == "water"):
			# Create obstacle and set pos
			size = properties.get("size", "1 1").split()
			size = (float(size[1]), float(size[0]), 0.0)
			
			o = sh_add_box(pos, size)
			
			# Set the type
			o.sh_properties.sh_type = "WAT"
			
			# Set the resolution
			o.sh_properties.sh_resolution = sh_parse_string_array(properties.get("resolution", "32 32"), fallbacks = [32.0, 32.0])
			
			# Set hidden
			o.hide_set(properties.get("hidden", "0") == "1")
		
		# Anything else
		else:
			warnings.add(f"this segment contains entities of type '{kind}' which cannot be imported")
	
	# Warn about box count issues
	if (box_count == 0):
		warnings.add("the segment does not have any boxes which causes the segment to load improperly")
	
	# Display warnings info message
	if (len(warnings)):
		warnlist = []
		
		for warn in warnings:
			warnlist.append(warn)
		
		warnlist = ", ".join(warnlist)
		
		if (context.preferences.addons["shatter"].preferences.enable_segment_warnings):
			show_message("Import warnings", f"The segment imported successfully, but some possible issues were noticed: {warnlist}.")
	
	return {"FINISHED"}
