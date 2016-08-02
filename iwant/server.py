from twisted.internet import reactor,defer,threads,endpoints
from twisted.internet.protocol import Factory
from twisted.protocols.basic import FileSender
from flashpointProtocol import FlashpointProtocol
from filehashIndex.FHIndex import FileHashIndexer
from communication.message import P2PMessage

class backend(FlashpointProtocol):
    def __init__(self):
        self.message_codes = {
            'handshake' : self._handshake,
            'listAll' : self._list_file,
            2 : self._load_file,
            3 : self._start_transfer,
            'leader': self._update_leader,
            'filesys_modified': self._filesystem_modified
        }
        self.buff = ''
        self.delimiter = '#'

    def serviceMessage(self, data):
        req = P2PMessage(message=data)
        print 'GOT {0}'.format(req.key)
        try:
            self.message_codes[req.key]()
        except:
            self.message_codes[req.key](req.data)

    def _handshake(self):
        resMessage = P2PMessage(key='handshake',data=[])
        self.sendLine(resMessage)

    def _list_file(self):
        if self.factory.state==1:
            resMessage = P2PMessage(key='listAll', data=self.factory.indexer.reduced_index())
            self.sendLine(resMessage)
        else:
            resMessage = P2PMessage(key='ErrorListingAll',data='File hashing incomplete')
            self.sendLine(resMessage)

    def _load_file(self,data):
        fhash = data[0]
        self.fileObj = self.factory.indexer.getFile(fhash)
        fsize = self.factory.indexer.hash_index[fhash].size
        ack_msg = P2PMessage(key=3,data=[fsize])
        self.sendLine(ack_msg)

    def _start_transfer(self):
        producer = FileSender()
        consumer = self.transport
        deferred = producer.beginFileTransfer(self.fileObj,consumer)
        deferred.addCallback(self._success,self._failure)

    def _success(self,data):
        print 'Successfully transfered file'

    def _failure(self,reason):
        print 'Failed {0}'.format(reason)

    def _update_leader(self, leader):
        print 'Leader {0}'.format(leader)

    def _filesystem_modified(self):
        print 'file system modified'

class backendFactory(Factory):
    protocol = backend
    def __init__(self,folder):
        self.state = 1
        self.folder = folder
        self.indexer = FileHashIndexer(folder)
        self.d = threads.deferToThread(self.indexer.index)
        self.d.addCallbacks(self._success,self._failure)

    def _success(self,data):
        self.state = 1

    def _failure(self,reason):
        raise NotImplementedError

    def connectionMade(self):
        print 'connection established'

if __name__ == '__main__':
    #folder = raw_input('Enter absolute path to share :')
    endpoints.serverFromString(reactor,'tcp:1235').listen(backendFactory('/home/nirvik/Pictures'))
    reactor.run()
