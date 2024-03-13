#!/usr/bin/python3
"""
Tool for baking a Smash Hit mesh

Problems:

 - CP2 segments are 100% fucked becuase:
   - tileRot isn't respected correctly
   - shatter does not export tileSize when there is a template
   - tileSize rotation might be wrong as well, hell if I know
"""

import struct
import zlib
import sys
import xml.etree.ElementTree as et
import random
import math
import gzip

# Version of mesh baker
VERSION = (0, 15, 6)

# If the mesh baker version and bake info should be appended to the end of the
# mesh data
INCLUDE_VERSION_AND_INFO = False

# The number of rows and columns in the tiles.mtx.png file. Change this if you
# have overloaded the file with more tiles; note that you will also need to
# rebake other segments with the same row/column setting.
TILE_ROWS = 8
TILE_COLS = 8

# The amount of a tile that should be clipped off the edges. This mostly done to
# hide hard edges between tile textures.
# 
# I don't know why it's this constant by default specifically, but you can
# find 0.00390625 in LitMesh::addBox which is TILE_BITE_ROW / TILE_ROWS (and
# COLS too)
TILE_BITE_ROW = 0.03125
TILE_BITE_COL = 0.03125

# Disable or enable baking unseen and back faces. Note that unseen faces does
# includes back faces, so both must be enabled for those.
BAKE_UNSEEN_FACES = False

# Enable ambient occlusion using delta boxes
ABMIENT_OCCLUSION_ENABLED = True

# Half of the size of the delta box when using the delta-box AO method
ABMIENT_OCCLUSION_DELTA_BOX_SIZE = 0.5

# Enable lighting
LIGHTING_ENABLED = False

################################################################################
### END OF CONFIGURATION #######################################################
################################################################################

def log(msg, newline = True):
	"""
	Log a message to the console
	"""
	
	LOG_PREFIX = "\x1b[1;38;2;219;65;106mBakeMesh: \x1b[0m"
	
	if (type(msg) != str):
		msg = repr(msg)
	
	print(LOG_PREFIX + msg.replace("\n", f"\n{LOG_PREFIX}"))

def removeEverythingEqualTo(array, value):
	"""
	Remove everything in an array equal to a value
	"""
	
	while (True):
		try:
			array.remove(value)
		except ValueError:
			return array

class Vector3:
	"""
	(Hopefully) simple implementation of a Vector3
	"""
	
	def __init__(self, x = 0.0, y = 0.0, z = 0.0, a = 1.0):
		self.x = x
		self.y = y
		self.z = z
		self.a = a
	
	@classmethod
	def fromString(self, string, many = False):
		"""
		Convert a vector or list of vectors from a string to a vector object
		"""
		
		cmpnames = ['x', 'y', 'z', 'a']
		
		array = removeEverythingEqualTo(string.split(" "), "")
		array = [float(array[i]) for i in range(len(array))]
		
		# Handle overloaded string array
		if (many and len(array) >= 6 and (len(array) % 3) == 0):
			vectors = []
			
			for i in range(len(array) // 3):
				vectors.append(Vector3(array[i * 3 + 0], array[i * 3 + 1], array[i * 3 + 2]))
			
			return vectors
		
		vec = Vector3()
		
		for i in range(min(len(array), 4)):
			setattr(vec, cmpnames[i], array[i])
		
		return vec
	
	@classmethod
	def random(self):
		return Vector3(random.random(), random.random(), random.random())
	
	def __neg__(self):
		return Vector3(-self.x, -self.y, -self.z)
	
	def __add__(self, other):
		return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
	
	def __sub__(self, other):
		return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
	
	def __mul__(self, other):
		if (type(other) == Vector3):
			return (self.x * other.x) + (self.y * other.y) + (self.z * other.z)
		else:
			return Vector3(other * self.x, other * self.y, other * self.z)
	
	def __rmul__(self, other):
		return Vector3(other * self.x, other * self.y, other * self.z)
	
	def __truediv__(self, other):
		if (type(other) == Vector3):
			return Vector3(self.x / other.x, self.y / other.y, self.z / other.z)
		else:
			return Vector3(self.x / other, self.y / other, self.z / other)
	
	def __format__(self, _unused):
		return f"{self.x} {self.y} {self.z}"
	
	def __eq__(self, other):
		if (type(self) != type(other)): return False
		v = self - other
		d = 0.001
		return (-d <= v.x <= d) and (-d <= v.y <= d) and (-d <= v.z <= d)
	
	def lengthSquared(self):
		return self.x * self.x + self.y * self.y + self.z * self.z
	
	def length(self):
		return math.sqrt(self.lengthSquared())
	
	def normalise(self):
		length = self.length()
		length = (1 / length) if not length <= 0.0 else 0.0
		return Vector3(self.x * length, self.y * length, self.z * length)
	
	def cross(self, other):
		x = self.y * other.z - self.z * other.y
		y = self.z * other.x - self.x * other.z
		z = self.x * other.y - self.y * other.x
		return Vector3(x, y, z)
	
	def compose(self, other):
		return Vector3(self.x * other.x, self.y * other.y, self.z * other.z)

	def anticompose(self, other):
		return Vector3(self.x / other.x, self.y / other.y, self.z / other.z)
	
	def copy(self):
		return Vector3(self.x, self.y, self.z)
	
	def diff(self, other):
		return (self.x == other.x, self.y == other.y, self.z == other.z)
	
	def withLight(self, light):
		"""
		Return a copy of self with a component set
		"""
		v = self.copy()
		v.a = light
		return v
	
	def asTuple(self):
		return (self.x, self.y, self.z)
	
	def partialOpposite(self, ax, ay, az):
		"""
		Negate part of the vector (only some compnents, those for which aC is True)
		"""
		return Vector3(self.x if not ax else -self.x, self.y if not ay else -self.y, self.z if not az else -self.z)

class BakeProgressInfo():
	"""
	Allows apps to implement progress indication
	"""
	
	def __init__(self, callback):
		self.callback = callback
	
	def update(self, value):
		self.callback(value)

def parseIntTriplet(string):
	"""
	Parse either a single int or three ints in a string to a tuple of three ints
	"""
	
	array = removeEverythingEqualTo(string.split(" "), "")
	array = [int(array[i]) for i in range(len(array))]
	
	if (len(array) < 3):
		c = len(array) - 1
		
		for _ in range(c, 3):
			array.append(array[c])
	
	return (array[0], array[1], array[2])

def parseFloatTriplet(string):
	"""
	Parse either a single float or three float in a string to a tuple of three floats
	"""
	
	array = removeEverythingEqualTo(string.split(" "), "")
	array = [float(array[i]) for i in range(len(array))]
	
	if (len(array) < 3):
		c = len(array) - 1
		
		for _ in range(c, 3):
			array.append(array[c])
	
	return (array[0], array[1], array[2])

class SegmentInfo:
	"""
	Info about the segment and its global information.
	"""
	
	def __init__(self, attribs, templates = None, boxes = None):
		self.template = attribs.get("template", None)
		
		self.front = float(getFromTemplate(attribs, templates, self.template, "lightFront", "1.0"))
		self.back = float(getFromTemplate(attribs, templates, self.template, "lightBack", "1.0"))
		self.left = float(getFromTemplate(attribs, templates, self.template, "lightLeft", "1.0"))
		self.right = float(getFromTemplate(attribs, templates, self.template, "lightRight", "1.0"))
		self.top = float(getFromTemplate(attribs, templates, self.template, "lightTop", "1.0"))
		self.bottom = float(getFromTemplate(attribs, templates, self.template, "lightBottom", "1.0"))
		
		# Ambient lighting (when enabled)
		self.ambient = Vector3.fromString(getFromTemplate(attribs, templates, self.template, "ambient", "0 0 0"))
		
		self.boxes = boxes
	
	def boxcast(self, pos, size):
		"""
		Check for the largest collision (by volume) of a box in a scene in a
		tuple with (accum volume, number intersected)
		"""
		
		total = 0.0
		intersected = 0
		
		for b in self.boxes:
			result = b.testAABB_optimisedBC(pos, size)
			
			if (result):
				volume = (2.0 * result[1].x) * (2.0 * result[1].y) * (2.0 * result[1].z)
				
				intersected += 1
				total += volume
		
		return (total, intersected)

class Quad:
	"""
	Representation of a quadrelaterial (a shape with four sides)
	"""
	
	def __init__(self, p1, p2, p3, p4, colour, tile, tileRot, seg, normal, gradient):
		self.p1 = p1
		self.p2 = p2
		self.p3 = p3
		self.p4 = p4
		self.colour = colour
		self.tile = tile
		self.tileRot = tileRot
		self.seg = seg
		self.normal = normal
		self.gradient = gradient
	
	def __format__(self, _unused):
		return f"{{ {self.p1} {self.p2} {self.p3} {self.p4} }}"
	
	def asData(self, offset = 0):
		"""
		Convert the quad to a mesh, but also computes the index offsets instead of
		just tris. Offset is the current count of verticies in the mesh file.
		
		Returns tuple of (vertex bytes, index bytes, number of vertexes, number of indicies)
		"""
		
		p1, p2, p3, p4, col, gc, normal, gradient = self.p1, self.p2, self.p3, self.p4, self.colour, self.seg, self.normal, self.gradient
		tex = getTextureCoords(TILE_ROWS, TILE_COLS, TILE_BITE_ROW, TILE_BITE_COL, self.tileRot, self.tile)
		
		vertexes = bytearray()
		vertexes += meshPointBytes(p1.x, p1.y, p1.z, tex[0][0], tex[0][1], col.x, col.y, col.z, col.a if hasattr(col, "a") else 1, gc, normal, gradient)
		vertexes += meshPointBytes(p2.x, p2.y, p2.z, tex[1][0], tex[1][1], col.x, col.y, col.z, col.a if hasattr(col, "a") else 1, gc, normal, gradient)
		vertexes += meshPointBytes(p3.x, p3.y, p3.z, tex[2][0], tex[2][1], col.x, col.y, col.z, col.a if hasattr(col, "a") else 1, gc, normal, gradient)
		vertexes += meshPointBytes(p4.x, p4.y, p4.z, tex[3][0], tex[3][1], col.x, col.y, col.z, col.a if hasattr(col, "a") else 1, gc, normal, gradient)
		
		index = [offset + 0, offset + 1, offset + 2, offset + 0, offset + 2, offset + 3]
		
		# Swap winding order in some situations so triangles don't get culled
		if ((p1.x == p3.x and p1.x > 0) or (p1.y == p3.y and p1.y <= 1)):
			index[0], index[2] = index[2], index[0]
			index[3], index[5] = index[5], index[3]
		
		indexes = bytearray()
		indexes += meshIndexBytes(index[0], index[1], index[2])
		indexes += meshIndexBytes(index[3], index[4], index[5])
		
		return (vertexes, indexes, 4, 6)

class Box:
	"""
	Very simple container for box data
	"""
	
	def __init__(self, seg, pos, size, colour = [Vector3(1.0, 1.0, 1.0), Vector3(1.0, 1.0, 1.0), Vector3(1.0, 1.0, 1.0)], tile = (0, 0, 0), tileSize = (1.0, 1.0, 1.0), tileRot = (0, 0, 0), glow = 0.0, gradient = None):
		"""
		seg: global segment context
		pos: position
		size: size of the box
		colour: list or tuple of the face colours of the box
		tile: list or tuple of tiles to use
		tileSize: size of the box tiles
		tileRot: rotation of the boxes
		glow: The power of the light (when using lighting extensions)
		"""
		
		# Expand shorthands for vectors
		if (type(colour) == Vector3):
			colour = [colour]
		
		if (len(colour) == 1):
			colour = [colour[0], colour[0], colour[0]]
		
		# Set attributes
		self.segment_info = seg
		self.pos = pos
		self.size = size
		self.colour = colour
		self.tile = tile
		self.tileSize = tileSize
		self.tileRot = tileRot
		self.glow = glow
		self.gradient = gradient
	
	def bakeGeometry(self):
		"""
		Convert the box to the split geometry. This is also where a lot of
		fixes occur, like setting the tile index per face and fixing tile
		rotation per side.
		"""
		
		# Tip: When reading this section it helps to draw a diagram of what is
		# happening.
		
		# Shorthands
		pos, tileSize, colour, tile, seg, tileRot = self.pos, self.tileSize, self.colour, self.tile, self.segment_info, self.tileRot
		
		# Get the eight points (verticies) of the cube
		p1 = self.size.partialOpposite(False, False, False)
		p2 = self.size.partialOpposite(False, False, True )
		p3 = self.size.partialOpposite(False, True , True )
		p4 = self.size.partialOpposite(False, True , False)
		p5 = self.size.partialOpposite(True , False, False)
		p6 = self.size.partialOpposite(True , False, True )
		p7 = self.size.partialOpposite(True , True , True )
		p8 = self.size.partialOpposite(True , True , False)
		
		# Compute the quads (note the min/max don't matter so long as its a square)
		# Only some are baked based on config settings
		quads = []
		
		# Right
		if (BAKE_UNSEEN_FACES or pos.x < 0.0):
			quads += generateSubdividedFaceGeometry(
				p1, p3,
				tileSize[2], tileSize[2],
				colour[0].withLight(seg.right),
				tile[0],
				(tileRot[0] + 1) % 4,
				seg,
				Vector3(1.0, 0.0, 0.0),
				self.gradient
			)
		
		# Left
		if (BAKE_UNSEEN_FACES or pos.x > 0.0):
			quads += generateSubdividedFaceGeometry(
				p5, p7,
				tileSize[2], tileSize[2],
				colour[0].withLight(seg.left),
				tile[0],
				(tileRot[0] + 1) % 4,
				seg,
				Vector3(-1.0, 0.0, 0.0),
				self.gradient
			)
		
		# Top
		if (BAKE_UNSEEN_FACES or pos.y < 1.0):
			quads += generateSubdividedFaceGeometry(
				p1, p6,
				tileSize[1], tileSize[1],
				colour[1].withLight(seg.top),
				tile[1],
				(tileRot[1] + 2) % 4,
				seg,
				Vector3(0.0, 1.0, 0.0),
				self.gradient
			)
		
		# Bottom
		if (BAKE_UNSEEN_FACES or pos.y > 1.0):
			quads += generateSubdividedFaceGeometry(
				p4, p7,
				tileSize[1], tileSize[1],
				colour[1].withLight(seg.bottom),
				tile[1],
				(tileRot[1] + 2) % 4,
				seg,
				Vector3(0.0, -1.0, 0.0),
				self.gradient
			)
		
		# Front
		quads += generateSubdividedFaceGeometry(
			p1, p8,
			tileSize[0], tileSize[0],
			colour[2].withLight(seg.front),
			tile[2],
			tileRot[2],
			seg, 
			Vector3(0.0, 0.0, 1.0),
			self.gradient
		)
		
		# Back
		if (BAKE_UNSEEN_FACES):
			quads += generateSubdividedFaceGeometry(
				p2, p7,
				tileSize[0], tileSize[0],
				colour[2].withLight(seg.back),
				tile[2],
				tileRot[2],
				seg,
				Vector3(0.0, 0.0, -1.0),
				self.gradient
			)
		
		# Translation transform
		for q in quads:
			q.p1 += self.pos
			q.p2 += self.pos
			q.p3 += self.pos
			q.p4 += self.pos
		
		return quads
	
	def testAABB(self, other_pos, other_size):
		"""
		Intersect self with another AABB and return origin and size of the
		formed aabb
		"""
		
		def test_aabb_axis(a_min, a_max, b_min, b_max):
			"""
			Test a single aabb axis returning the midpoint and half-difference
			of two values
			
			2023-08-30: I forget what the fuck "half-difference" means, I think
			I meant "half of the length of the intersection"
			"""
			
			if (a_min > a_max):
				a_min, a_max = a_max, a_min
			
			if (b_min > b_max):
				b_min, b_max = b_max, b_min
			
			if (a_max >= b_min and b_max >= a_min):
				return (0.5 * (b_max + a_min), 0.5 * (min(a_max, b_max) - max(a_min, b_min)))
			else:
				return None
		
		########################################################################
		
		# 2023-08-30: Did some optimisation by only computing these in a short
		# curcit style. Maybe it would be nice to find which order of these is
		# optimal for most cases.
		x = test_aabb_axis(self.pos.x - self.size.x, self.pos.x + self.size.x, other_pos.x - other_size.x, other_pos.x + other_size.x)
		
		if (x):
			y = test_aabb_axis(self.pos.y - self.size.y, self.pos.y + self.size.y, other_pos.y - other_size.y, other_pos.y + other_size.y)
			
			if (y):
				z = test_aabb_axis(self.pos.z - self.size.z, self.pos.z + self.size.z, other_pos.z - other_size.z, other_pos.z + other_size.z)
				
				if (z):
					#       Origin                     Size
					return (Vector3(x[0], y[0], z[0]), Vector3(x[1], y[1], z[1]))
		
		return None
	
	def testAABB_optimisedBC(self, other_pos, other_size):
		"""
		testAABB but optimised for boxcast
		"""
		
		def test_aabb_axis(a_min, a_max, b_min, b_max):
			"""
			Test a single aabb axis returning the midpoint and half-difference
			of two values
			
			2023-08-30: I forget what the fuck "half-difference" means, I think
			I meant "half of the length of the intersection"
			
			optimised version is regular diff
			"""
			
			if (a_min > a_max):
				a_min, a_max = a_max, a_min
			
			if (b_min > b_max):
				b_min, b_max = b_max, b_min
			
			if (a_max >= b_min and b_max >= a_min):
				return min(a_max, b_max) - max(a_min, b_min)
			else:
				return None
		
		########################################################################
		
		# 2023-08-30: Did some optimisation by only computing these in a short
		# curcit style. Maybe it would be nice to find which order of these is
		# optimal for most cases.
		x = test_aabb_axis(self.pos.x - self.size.x, self.pos.x + self.size.x, other_pos.x - other_size.x, other_pos.x + other_size.x)
		
		if (x != None):
			y = test_aabb_axis(self.pos.y - self.size.y, self.pos.y + self.size.y, other_pos.y - other_size.y, other_pos.y + other_size.y)
			
			if (y != None):
				z = test_aabb_axis(self.pos.z - self.size.z, self.pos.z + self.size.z, other_pos.z - other_size.z, other_pos.z + other_size.z)
				
				if (z != None):
					#       Origin                     Size
					return (None, Vector3(0.5 * x, 0.5 * y, 0.5 * z))
		
		return None

def parseGradient(pos, size, gradient):
	"""
	Parse a gradient to the standard 12 length float list
	"""
	
	if (not gradient):
		return []
	elif (gradient.startswith('A ')):
		return [float(x) for x in gradient[2:].split()]
	else:
		gradient = [float(x) for x in gradient.split()]
		
		# Convert first point to absolute coords
		gradient[0] = pos.x + (size.x * gradient[0])
		gradient[1] = pos.y + (size.y * gradient[1])
		gradient[2] = pos.z + (size.z * gradient[2])
		
		# Convert second point to absolute coords
		gradient[3] = pos.x + (size.x * gradient[3])
		gradient[4] = pos.y + (size.y * gradient[4])
		gradient[5] = pos.z + (size.z * gradient[5])
		
		return gradient

def parseSegmentXML(data, templates = {}):
	"""
	Parse a segment string for its boxes, and resolve any templates if they are
	given.
	"""
	
	root = et.fromstring(data)
	boxes = []
	
	if (root.tag != "segment"):
		return None
	
	seg = SegmentInfo(root.attrib, templates, boxes)
	
	# Create a box for each box in the segment
	for e in root:
		if (e.tag == "box"):
			a = e.attrib
			t = a.get("template", None)
			
			if (getFromTemplate(a, templates, t, "visible", "1") != "0"):
				# Get properties
				
				# Position -- x y z
				pos = Vector3.fromString(getFromTemplate(a, templates, t, "pos", "0 0 0"))
				
				# Size -- x y z
				size = Vector3.fromString(getFromTemplate(a, templates, t, "size", "0 0 0"))
				
				# Colour -- r1 g1 b1   [r2 g2 b2   r3 g3 b3]
				colour = Vector3.fromString(getFromTemplate(a, templates, t, "color", "1 1 1"), True)
				
				# Tile -- tile1 [tile2 tile3]
				tile = parseIntTriplet(getFromTemplate(a, templates, t, "tile", "0"))
				
				# Tile size -- size1 [size2 size3]
				tileSize = parseFloatTriplet(getFromTemplate(a, templates, t, "tileSize", "1"))
				
				# Tile rotation -- rot1 [rot2 rot3]
				tileRot = parseIntTriplet(getFromTemplate(a, templates, t, "tileRot", "0"))
				
				# Lighting: Glow -- intensity
				glow = float(getFromTemplate(a, templates, t, "mb-glow", "") or getFromTemplate(a, templates, t, "glow", "0"))
				
				# Gradient
				gradient = parseGradient(pos, size, getFromTemplate(a, templates, t, "mb-gradient", ""))
				
				boxes.append(Box(seg, pos, size, colour, tile, tileSize, tileRot, glow, gradient))
	
	return seg

def getFromTemplate(boxattr, template_list, template, attr, default):
	"""
	Get an attribute from the template or object
	"""
	
	res = boxattr.get(attr, template_list.get(template, {}).get(attr, default))
	
	return res

def parseTemplatesXml(path):
	"""
	Load templates from a file
	"""
	
	result = {}
	
	try:
		tree = et.parse(path)
		root = tree.getroot()
		
		assert("templates" == root.tag)
		
		# Loop over templates in XML file and load them
		for child in root:
			assert("template" == child.tag)
			
			name = child.attrib["name"]
			attribs = child[0].attrib
			
			result[name] = attribs
		
		return result
	except:
		return result


def generateSubdividedFaceGeometry(minest, maxest, s_size, t_size, colour, tile, tileRot, seg, normal, gradient):
	"""
	Generates subdivided quadrelaterials for any given axis where the min/max
	are not the same. Minest/maxist are the min/max of the quad and ssize and 
	tsize are the size of the subdivisions. Colour and tile are the colour and
	tile. The normal is the normal of the surface.
	"""
	
	minest = minest.copy()
	maxest = maxest.copy()
	
	# Init array for quads
	quads = []
	
	ax_e = "Axis was not properly selected if this value is used." # e for Excluded axis
	ax_s = 's'
	ax_t = 't'
	
	# Find which axes should be used
	for a in ['x', 'y', 'z']:
		if (getattr(minest, a) == getattr(maxest, a)):
			ax_e = a
			axes = ['x', 'y', 'z']
			axes.remove(a)
			ax_s = axes[0]
			ax_t = axes[1]
			break
	else:
		log("Similar axis was not found!!")
		return None
	
	# Swap the axis's directions if not in the expected direction
	# After this, min.s <= max.s and min.t <= max.t so it is safe to just add or
	# subtract from s and t directly.
	if (getattr(minest, ax_s) > getattr(maxest, ax_s)):
		temp = getattr(maxest, ax_s)
		setattr(maxest, ax_s, getattr(minest, ax_s))
		setattr(minest, ax_s, temp)
	
	if (getattr(minest, ax_t) > getattr(maxest, ax_t)):
		temp = getattr(maxest, ax_t)
		setattr(maxest, ax_t, getattr(minest, ax_t))
		setattr(minest, ax_t, temp)
	
	# Create the unit vector for each axis
	s_unit = Vector3(0, 0, 0)
	setattr(s_unit, ax_s, 1.0)
	
	t_unit = Vector3(0, 0, 0)
	setattr(t_unit, ax_t, 1.0)
	
	# And the scaled vector too...
	s_scunit = s_unit * s_size
	t_scunit = t_unit * t_size
	
	# Get the constant component that the e axis should always use
	e_location = getattr(minest, ax_e)
	
	# Generate the major axis (s)
	s_current = getattr(minest, ax_s)
	s_max = getattr(maxest, ax_s)
	
	while (s_current < s_max):
		# Generate the minor axis (t)
		t_current = getattr(minest, ax_t)
		t_max = getattr(maxest, ax_t)
		
		while (t_current < t_max):
			# Set the actual unit to be used
			s_scunitpart = s_scunit.copy()
			t_scunitpart = t_scunit.copy()
			
			# Check that there is enough space, if not, truncate the tile (for s and t axis)
			# How this works:
			#   - check if the next tile location is greater than max
			#   - if so, then compute the length of the box and modulo it with its size (get remainder)
			#   - set that new value as the tile size
			if (s_current + s_size > s_max):
				setattr(s_scunitpart, ax_s, abs(getattr(maxest, ax_s) - getattr(minest, ax_s)) % s_size)
			
			if (t_current + t_size > t_max):
				setattr(t_scunitpart, ax_t, abs(getattr(maxest, ax_t) - getattr(minest, ax_t)) % t_size)
			
			# Create first point (hardest one!)
			p1 = Vector3(0, 0, 0)
			setattr(p1, ax_e, e_location)
			setattr(p1, ax_s, s_current)
			setattr(p1, ax_t, t_current)
			
			# Create other points based on first point (using transformed unit vectors)
			p2 = p1 + s_scunitpart
			p3 = p1 + s_scunitpart + t_scunitpart
			p4 = p1                + t_scunitpart
			
			# Finally make the quad
			quads.append(Quad(p1, p2, p3, p4, colour, tile, tileRot, seg, normal, gradient))
			
			# Add new size to total count (for this major axis)
			t_current += t_size
		
		# Count this row as being generated for major axis
		s_current += s_size
	
	return quads

def meshIndexBytes(i0, i1, i2):
	"""
	Return the bytes for an index in the mesh
	"""
	
	c = bytearray()
	
	c += struct.pack('I', i0)
	c += struct.pack('I', i1)
	c += struct.pack('I', i2)
	
	return c

def rotateList(e, n):
	"""
	Rotate n elements of a list e
	"""
	
	n %= len(e)
	
	for i in range(n):
		e.append(e.pop(0))
	
	return e

def getTextureCoords(rows, cols, bite_row, bite_col, rot, tile):
	"""
	Gets the texture coordinates given the tile number.
	
	The tile bite is a small region of the tile that is clipped off.
	
	Returns ((u1, v1), (u2, v2), (u3, v3), (u4, v4))
	"""
	
	bite_row = (bite_row / rows)
	bite_col = (bite_col / cols)
	u = ((tile % rows) / rows) + bite_row
	v = ((tile // rows) / cols) + bite_col
	w = (1 / rows) - (2 * bite_row)
	h = (1 / cols) - (2 * bite_col)
	
	return rotateList([(u, v), (u, v + h), (u + w, v + h), (u + w, v)], rot)

def doAmbientOcclusion(x, y, z, a, gc, normal):
	"""
	Compute the light at a vertex
	
	The following method is an idea that I had to get percise light information
	about a point very quickly when a scene has only AABBs. Basically, we pick
	a vertex then create a cube of a certian length, width and height around
	that vertex. We then find every intersection with that box and sum the
	volume of the union of those intersections. After this, we take the ratio
	between the volume of half the delta box and the accumulated volume. With
	this, we subtract half of the delta box volume from our accumulated volume,
	max it with 0, divide that by half of the delta box volume and finally cube
	root it which should give us an apprimation of the light that reaches this
	point without preforming many many raycasts.
	
	This has some issues: overlaping boxes can cause the algorithm to overshade
	some point dramatically.
	
	Updated for 0.13: Now it increments the position by normal * deltaboxsize so
	we are closer to just a raycast
	"""
	
	# Find the size and the volume of the delta box
	delta_box_size = Vector3(ABMIENT_OCCLUSION_DELTA_BOX_SIZE, ABMIENT_OCCLUSION_DELTA_BOX_SIZE, ABMIENT_OCCLUSION_DELTA_BOX_SIZE)
	delta_box_volume = (2 * ABMIENT_OCCLUSION_DELTA_BOX_SIZE) ** 3
	
	# Find the box with largest volume intresecting the box around this vertex
	accum, isect = gc.boxcast(Vector3(x, y, z) + (normal * ABMIENT_OCCLUSION_DELTA_BOX_SIZE), delta_box_size)
	
	# Find the light based on the volume taken
	# This is min/max'd to not cause major issues if there is an overlaping box
	shade = min(max(accum, 0), delta_box_volume) / delta_box_volume
	
	return (a ** 2) * (1.0 - 0.47 * shade ** 0.3)

def doLighting(x, y, z, r, g, b, gc):
	"""
	Does a rough approximation of illumination for the current point.
	This is very engineered and very approximate.
	"""
	
	# Get amount of ambient light
	ambient_light = gc.ambient
	
	# Find the intensity of light
	findIntenstity = lambda size, dist : min(max(1 / (((max(dist, size + 0.0001) - size) ** 2)), 0), 1)
	
	# Set a proper vector for the current colour
	old_colour = Vector3(r, g, b)
	
	# Colour that will be added to old colour
	add_colour = Vector3(0.0, 0.0, 0.0)
	
	# Make a proper vector for the current point coordintes
	point = Vector3(x, y, z)
	
	for box in gc.boxes:
		# Break if box is not a light
		if (box.glow == 0.0): continue
		
		# Compute difference from point to box origin
		difference = (box.pos - point)
		distance = difference.length()
		
		# Find the nearest side coordinate index
		facing_side = (0 if ((abs(difference.x) > abs(difference.y)) and (abs(difference.x) > abs(difference.z))) else (1 if (abs(difference.y) > abs(difference.z)) else 2))
		
		# Set box colour
		box_colour = box.colour[facing_side]
		
		# Find the "radius" of the box used to make sure box size is less likely
		# to affect the amount of light cast
		radius = [box.size.x, box.size.y, box.size.z][facing_side]
		
		# Find the new colour of the point based on how much light was added to
		# the point and its intensity.
		add_colour += box_colour.compose(old_colour) * findIntenstity(radius, distance) * box.glow * 0.01
	
	# Get the final colour by adding to base box colour
	r, g, b = (old_colour.compose(ambient_light) + add_colour).asTuple()
	
	return (r, g, b)

def doComputeLinearGradient(x, y, z, r, g, b, gradient):
	# Endpoints of the gradient
	pa = Vector3(gradient[0], gradient[1], gradient[2])
	pb = Vector3(gradient[3], gradient[4], gradient[5])
	
	# Colour values of the gradient at each endpoint
	ca = Vector3(gradient[6], gradient[7], gradient[8])
	cb = Vector3(gradient[9], gradient[10], gradient[11])
	
	# Make points relative to an origin (pa in this case)
	rv = pb - pa
	ra = Vector3(x, y, z) - pa
	
	# Dot product between them to find how far along the vector is when project
	# against the other i fucking hate this shit i dont understand it anymore
	# and im tired as FUCK aaaaaauhghghghghghh FUCK FUCK FUCK
	alongness = ((max(rv * ra, 0.0) * rv) / rv.lengthSquared()).length() / rv.length()
	
	# Now we lerp which is much nicer :3
	r, g, b = (alongness * cb + (1.0 - alongness) * ca).asTuple()
	
	return (r, g, b)

def doVertexColour(x, y, z, r, g, b, a, gc, normal, gradient):
	"""
	Do any final colour correction operations and per-vertex lighting.
	"""
	
	if (gradient):
		r, g, b = doComputeLinearGradient(x, y, z, r, g, b, gradient)
	
	if (ABMIENT_OCCLUSION_ENABLED):
		a = doAmbientOcclusion(x, y, z, a, gc, normal)
	
	if (LIGHTING_ENABLED):
		r, g, b = doLighting(x, y, z, r, g, b, gc)
	
	return r * 0.5, g * 0.5, b * 0.5, a

def meshPointBytes(x, y, z, u, v, r, g, b, a, gc, normal, gradient):
	"""
	Return bytes for the point in the mesh
	
	gc is the segment context that contains the box list for lighting
	"""
	
	r, g, b, a = doVertexColour(x, y, z, r, g, b, a, gc, normal, gradient)
	
	c = bytearray()
	
	c += struct.pack('f', x)
	c += struct.pack('f', y)
	c += struct.pack('f', z)
	c += struct.pack('f', u)
	c += struct.pack('f', v)
	c += struct.pack('B', int(max(min(r, 1.0), 0.0) * 255))
	c += struct.pack('B', int(max(min(g, 1.0), 0.0) * 255))
	c += struct.pack('B', int(max(min(b, 1.0), 0.0) * 255))
	c += struct.pack('B', int(max(min(a, 1.0), 0.0) * 255))
	
	return c

def generateMeshData(data, seg = None, progress = None, extra_data = None):
	"""
	Generates mesh data bytes
	"""
	
	# Vertex and index data arrays
	vertex = bytearray()
	index = bytearray()
	
	vertex_count = 0
	index_count = 0
	
	i = 1
	l = len(data)
	
	# Convert data to bytes
	for d in data:
		r = d.asData(vertex_count)
		
		if (progress):
			progress.update(0.5 + 0.5 * (i / l))
			i += 1
		
		vertex += r[0]
		index += r[1]
		vertex_count += r[2]
		index_count += r[3]
	
	# Write out final data
	outdata = bytearray()
	outdata += struct.pack('I', vertex_count)
	outdata += vertex
	outdata += struct.pack('I', index_count)
	outdata += index
	
	if (extra_data):
		outdata += extra_data.encode('utf-8')
	
	if (INCLUDE_VERSION_AND_INFO):
		outdata += b"MB"
		outdata += struct.pack('!H', VERSION[0])
		outdata += struct.pack('!H', VERSION[1])
		outdata += struct.pack('!H', VERSION[2])
		outdata += struct.pack('!H', (0b1 if BAKE_UNSEEN_FACES else 0) | (0b10 if ABMIENT_OCCLUSION_ENABLED else 0) | (0b100 if LIGHTING_ENABLED else 0))
		outdata += struct.pack('!H', TILE_ROWS)
		outdata += struct.pack('!H', TILE_COLS)
		outdata += struct.pack('!f', TILE_BITE_ROW)
		outdata += struct.pack('!f', TILE_BITE_COL)
		outdata += struct.pack('!f', ABMIENT_OCCLUSION_DELTA_BOX_SIZE)
	
	outdata = zlib.compress(outdata, -1)
	
	return outdata

## =============================================================================
## =============================================================================
## =============================================================================

def bakeMeshFromBytesToBytes(data, templates_path = None, progress = None, extra_data = None):
	"""
	Bake a mesh from Smash Hit segment and return data
	
	data: Mesh data as a string
	templates_path: Path to the templates file
	"""
	
	seg = parseSegmentXML(data, parseTemplatesXml(templates_path) if templates_path else {})
	boxes = seg.boxes
	
	meshData = []
	
	i = 0
	l = len(boxes)
	
	for box in boxes:
		if (progress):
			progress.update(0.5 * (i / l))
			i += 1
		
		meshData += box.bakeGeometry()
	
	return generateMeshData(meshData, seg, progress, extra_data)

def bakeMeshToFile(data, output_file, template_file = None, progress = None, extra_data = None):
	"""
	Given the segment data as a string, bake a mesh file, optionally using the
	templates specififed.
	"""
	
	mesh_data = bakeMeshFromBytesToBytes(data, template_file, progress, extra_data)
	
	f = open(output_file, "wb")
	f.write(mesh_data)
	f.close()

def bakeMesh(input_file, output_file, template_file = None, progress = None):
	"""
	2024-01-18: Needed for mesh runner
	
	Bake a mesh from and input .xml or .xml.gz file.
	"""
	
	compressed = input_file.endswith(".gz.mp3") or input_file.endswith(".gz")
	input_data = None
	
	if (compressed):
		with gzip.open(input_file, "r") as f:
			input_data = f.read()
	else:
		with open(input_file, "rb") as f:
			input_data = f.read()
	
	bakeMeshToFile(input_data, output_file, template_file, progress)

def main():
	if (len(sys.argv) < 3):
		print(f"""
Usage:
{sys.argv[0]} <input> <output> [<templates>]

Bakes a Smash Hit mesh from the file named <input> to the file named <output>,
using templates from <templates> if specified. It is automaticlly inferred if
<input> is compressed by checking if it ends with the strings ".gz.mp3" or
".gz". If not it is assumed to be uncompressed.
""")
	else:
		bakeMesh(
			sys.argv[1],
			sys.argv[2],
			sys.argv[3] if len(sys.argv) >= 4 else None,
		)

if (__name__ == "__main__"):
	main()
else:
	log(f"""BakeMesh v{VERSION[0]}.{VERSION[1]}.{VERSION[2]} is copyright (C) 2021 - 2024 Knot126""")
