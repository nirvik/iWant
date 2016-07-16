import time
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from twisted.internet import reactor
from filehashIndex import FHIndex
import sys
import os
class MyHandler(PatternMatchingEventHandler):
    patterns = ["*"]

    def process(self, event):
        print event.src_path, event.event_type
        if event.event_type in ["created","modified"]:
            idx = FHIndex.FileHashIndexer(event.src_path)
            if event.is_directory:
                idx.index()
            else:
                idx.compute_hash_diff_file(event.src_path, singleFile=True)
        else:
            '''
                If directory is removed , pass the parent directory
            '''
            if event.is_directory:
                print 'is directory'
                path = os.path.split(os.path.abspath(event.src_path))[0]  # parent directory
            else:
                path = os.path.dirname(event.src_path)
            print path
            idx = FHIndex.FileHashIndexer(path)
            idx.index()

    def on_modified(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)

    def on_deleted(self, event):
        self.process(event)

    def on_moved(self, event):
        self.process(event)

if __name__ == '__main__':
    args = sys.argv[1]
    idx = FHIndex.FileHashIndexer(args)
    idx.index()
    observer = Observer()
    observer.schedule(MyHandler(),path=args,recursive=True)
    observer.start()
    try:
        reactor.run()
    except KeyboardInterrupt:
        observer.stop()
        reactor.stop()
