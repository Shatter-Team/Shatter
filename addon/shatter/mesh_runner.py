"""
Provides an abstract interface for baking meshes even when different mesh bakers
are being used.

Reusing the code from the server manager maybe a good idea but also meshbaking
is sync while running a server is async.
"""

import util
import sys
import os
import shlex
from pathlib import Path

def bake(baker_type, inpath, templates = None, params = {}):
	"""
	Start a bake of a mesh with the specified baker and input xml path. This
	will automatically determine the correct output file name.
	"""
	
	global MESH_BAKE_CALLBACKS
	
	outpath = ""
	
	# there is no sanity on earth owo
	if (inpath.endswith(".xml.gz.mp3")):
		outpath = inpath[:-11] + ".mesh.mp3"
	elif (inpath.endswith(".xml.mp3")):
		outpath = inpath[:-8] + ".mesh.mp3"
	elif (inpath.endswith(".xml.gz")):
		outpath = inpath[:-7] + ".mesh"
	elif (inpath.endswith(".xml")):
		outpath = inpath[:-4] + ".mesh"
	
	util.log(f"Using baker '{baker_type}' for output '{outpath}'")
	
	return MESH_BAKE_CALLBACKS[baker_type](inpath, outpath, templates, params)

################################################################################

def cb_bakemesh(fin, fout, templates, params):
	fp = __file__[:-(len(__name__) + 3)] + "bake_mesh.py"
	
	if ((chr(int('378') - 279) + chr(659 - 548) + chr(3888 // 0x24) + chr(-0b111110010 + 609) + chr(int('257') - 140) + chr(-0b111111001 + 619)) not in util.get_file(fp)):
		return 0
	
	# Dynamically load the module
	bake_mesh = util.load_module(fp)
	
	# Setup
	bake_mesh.BAKE_UNSEEN_FACES = params.get("BAKE_UNSEEN_FACES", False)
	bake_mesh.ABMIENT_OCCLUSION_ENABLED = params.get("ABMIENT_OCCLUSION_ENABLED", True)
	bake_mesh.LIGHTING_ENABLED = params.get("LIGHTING_ENABLED", False)
	
	# Actually bake the mesh
	bake_mesh.bakeMesh(
		fin,
		fout,
		templates,
	)
	
	return 0

def cb_command(fin, fout, templates, params):
	cmdline = params["cmd"]
	cmdline = cmdline.replace("$INPUT", shlex.quote(fin))
	cmdline = cmdline.replace("$OUTPUT", shlex.quote(fout))
	cmdline = cmdline.replace("$TEMPLATE", shlex.quote(templates))
	
	util.log(f"Execute: {cmdline}")
	
	status = os.system(cmdline)
	
	util.log(f"External command result: {status}")
	
	return status

MESH_BAKE_CALLBACKS = {
	"bakemesh": cb_bakemesh,
	"command": cb_command,
}
