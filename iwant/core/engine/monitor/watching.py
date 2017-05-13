from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from twisted.internet import reactor
from iwant.core.engine.fileindexer import fileHashUtils
import os


class ScanFolder(object):

    def __init__(self, folder, callback, dbpool):
        print 'now scanning {0}'.format(folder)
        self.path = folder
        self.callback = callback
        self.dbpool = dbpool
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
            if event.is_directory:
                add_event = fileHashUtils.index_folder(
                    self.path,
                    self.dbpool,
                    modified_folder=event.src_path)
            else:
                modified_folder = os.path.dirname(event.src_path)
                add_event = fileHashUtils.index_folder(
                    self.path,
                    self.dbpool,
                    modified_folder=modified_folder)

            add_event.addCallback(self.callback)
        else:
            '''If file/directory is moved or deleted If directory is removed , pass the parent directory'''

            if event.is_directory:
                remove_event = fileHashUtils.folder_delete_handler(
                    self.path,
                    self.dbpool,
                    modified_folder=event.src_path,
                )
            else:
                modified_folder = os.path.dirname(event.src_path)
                remove_event = fileHashUtils.folder_delete_handler(
                    self.path,
                    self.dbpool,
                    modified_folder=event.src_path
                )
            remove_event.addCallback(self.callback)

if __name__ == '__main__':
    # ScanFolder('/home/nirvik/Music/Maa', hey)
    reactor.run()
