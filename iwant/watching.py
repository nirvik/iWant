import time
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from twisted.internet import reactor
from filehashIndex import FHIndex
import sys
import os

class ScanFolder(object):
	def __init__(self, folder, config_folder, callback):
		self.path = folder
		self.callback = callback
 	        self.config_folder = config_folder
		self.event_handler = PatternMatchingEventHandler(patterns=['*'])
		self.event_handler.process = self.process
		self.event_handler.on_any_event = self.on_any_event
		self.observer = Observer()
		self.observer.schedule(self.event_handler, self.path, recursive=True)
		self.observer.start()

	def on_any_event(self, event):
		self.process(event)

	def process(self, event):
		print event.src_path, event.event_type
		if event.event_type in ["created", "modified"]:
			idx = FHIndex.FileHashIndexer(event.src_path, self.config_folder)
			if event.is_directory:
				idx.index()
			else:
				idx.compute_hash_diff_file(event.src_path, singleFile=True)
		else:
			'''If file/directory is moved or deleted If directory is removed , pass the parent directory'''

			if event.is_directory:
				path = os.path.split(os.path.abspath(event.src_path))[0]  # parent directory
			else:
				path = os.path.dirname(event.src_path)
			idx = FHIndex.FileHashIndexer(path, self.config_folder)
			idx.index()
		self.callback(self.config_folder) # informing the server daemon about changes

if __name__ == '__main__':
	args = sys.argv[1]
	idx = FHIndex.FileHashIndexer(args)
	idx.index()
	# eventHandler = MyHandler(print_hi)
	# observer = Observer()
	# observer.schedule(eventHandler,path=args,recursive=True)
	# observer.start()
	x = ScanFolder(args, print_hi)
	try:
		reactor.run()
	except KeyboardInterrupt:
		observer.stop()
		reactor.stop()
