from twisted.internet import reactor,defer,threads,endpoints
from twisted.internet.protocol import Factory
from twisted.protocols.basic import FileSender
from flashpointProtocol import FlashpointProtocol
from filehashIndex.FHIndex import FileHashIndexer
from communication.message import FlashMessage

class backend(FlashpointProtocol):
    def __init__(self):
        self.message_codes = {
            1 : self._list_file,
            2 : self._load_file,
            3 : self._start_transfer
        }

    def serviceMessage(self,data):
        print data
        req = FlashMessage(message=data)
        print req.key,req.data
        try:
            self.message_codes[req.key](req.data)
        except:
            raise NotImplementedError

    def _list_file(self,_discard):
        print self.factory.state
        if self.factory.state==1:
            self.sendLine(self.factory.indexer.reduced_index())
        else:
            self.sendLine('FILE HASHING : STATUS : INCOMPLETE')

    def _load_file(self,data):
        fhash = data[0]
        self.fileObj = self.factory.indexer.getFile(fhash)
        fsize = self.factory.indexer.hash_index[fhash].size
        ack_msg = FlashMessage(key=3,data=[fsize])
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


if __name__ == '__main__':
    folder = raw_input('Enter absolute path to share :')
    endpoints.serverFromString(reactor,'tcp:1234').listen(backendFactory(folder))
    reactor.run()
