"""
Level test server manager

Manages the level server(s) that are being run in the background.
"""

import util
from pathlib import Path
import os
import sys

class LevelServerManager():
	def __init__(self):
		self.server_type = "none"
		self.server_process = None
		self.params = tuple()
	
	def set_type(self, server_type):
		"""
		Set the server type
		
		NOTE: Server needs to be stopped first!
		"""
		
		self.server_type = server_type
	
	def set_params(self, params):
		"""
		Sets the params that will be given to the server run function.
		"""
		
		self.params = params
	
	def start(self):
		"""
		Starts the server if not already started
		"""
		
		if (not self.server_process and self.server_type != "none"):
			if (self.server_type not in SERVER_CALLBACKS):
				util.log(f"{self.server_type} is not a supported server type")
				return
			
			self.server_process = util.start_async_task(SERVER_CALLBACKS[self.server_type], self.params)
	
	def stop(self):
		"""
		Stop the server
		"""
		
		if (self.server_process):
			self.server_process.terminate()
			self.server_process.join(3)
			self.server_process.close()
		
		self.server_process = None
	
	def restart(self):
		"""
		Restarts the server
		"""
		
		self.stop()
		self.start()


def cb_builtin():
	"""
	Run the builtin level server
	"""
	
	script_path = str(Path(__file__).parent) + "/quick_test.py"
	
	if (not util.check_file_hash(script_path, "c140a45b9f6574f07693442f475d84a6c82ac56dc5124124b6004a1ecd764a74")):
		util.log("Error: quick_test.py file hash does not match expected hash!")
		os._exit(0)
	
	quick_test = util.load_module(script_path)
	quick_test.runServer()

def cb_yorshex(asset_dir, level):
	"""
	Run yorshex's level server
	"""
	
	from subprocess import Popen
	import signal, time
	
	should_exit = False
	python_path = os.path.realpath(sys.executable)
	script_path = str(Path(__file__).parent) + "/asset_server.py"
	
	# Check file hash
	if (not util.check_file_hash(script_path, "515b62fd5f829f6a57405b223b53191d3c55c9f0e52cb64a555ba4b0288466f1")):
		util.log("Error: asset_server.py file hash does not match expected hash!")
		os._exit(0)
	
	# Open the process
	proc = Popen([python_path, script_path, asset_dir, "-l", level, "-o"])
	
	# Set signal to wait for terminate()
	def setshouldexit(_a, _b):
		nonlocal should_exit
		nonlocal proc
		
		proc.terminate()
		should_exit = True
	
	signal.signal(signal.SIGTERM, setshouldexit)
	
	# Busy loop
	while (not should_exit):
		time.sleep(0.1)
	
	os._exit(0)

SERVER_CALLBACKS = {
	"none": None,
	"builtin": cb_builtin,
	"yorshex": cb_yorshex,
}



def main():
	sm = LevelServerManager()
	sm.set_type(sys.argv[1])
	sm.set_params(sys.argv[2:])
	sm.start()
	
	while (True):
		cmd = input(">>> ")
		
		if (cmd == "stop"):
			sm.stop()
		if (cmd.startswith("type")):
			sm.set_type(cmd[5:])
		if (cmd.startswith("params")):
			sm.set_params(cmd[7:].split("#"))
		if (cmd == "start"):
			sm.start()
		if (cmd == "exit"):
			break
	
	sm.stop()

if (__name__ == "__main__"):
	main()
