"""
The Shatter Smash Hit Level Editor Addon for Blender
Copyright (C) 2020 - 2023 Knot126, licenced under a modified MIT licence

====================================================

This is the main file of Shatter. It configures imports, loads the main module
and calls the register and ungregister functions.
"""

bl_info = {
	"name": "Shatter",
	"description": "Blender-based tools for editing, saving and loading Smash Hit segments.",
	"author": "Shatter Team",
	"version": (2024, 3, 14),
	"blender": (3, 0, 0),
	"location": "File > Import/Export and 3D View > Tools",
	"warning": "",
	"doc_url": "https://github.com/Shatter-Team/Shatter/wiki",
	"tracker_url": "https://github.com/Shatter-Team/Shatter/issues",
	"category": "Development",
}

import sys
import pathlib

# Set up import so that it tries to load shit from our directory without
# bitching that it can't find things.
shatter_dir = pathlib.Path(__file__).parent
sys.path.append(str(shatter_dir))

# remove files from older versions that left crap everywhere and would break
# the current version of shatter
import common

if (hasattr(common, "BLENDER_TOOLS_PATH")):
	import shutil
	import os
	
	def delete_path(path):
		"""
		Delete the thing at the path
		"""
		
		try:
			shutil.rmtree(path)
		except:
			try:
				os.remove(path)
			except:
				pass
	
	print("Shatter: Need to delete a lot of old files, Blender might also break when loading addon the first time...")
	
	for f in ["assets", "docs", "requests", "rsa", "thirdparty-info", ".gitignore", "__init__.py", "autogen.py", "bake_mesh.py", "binaryxml.py", "common.py", "CONTRIBUTING.md", "CREDITS.md", "dummy.py", "LICENCE", "misc_shatter_tools.py", "obstacle_db.py", "README.md", "reporting.py", "segment_import.py", "segment_export.py", "segstrate.py", "server.py", "updater.py", "util.py", "shbt-public.key", "todo.txt"]:
		delete_path(common.BLENDER_TOOLS_PATH + "/" + f)
else:
	print("Shatter: Don't need to delete any old files")

import main

def register():
	main.register()

def unregister():
	main.unregister()
