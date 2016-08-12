from twisted.internet import reactor,defer,threads,endpoints
from twisted.internet.protocol import Factory
from twisted.protocols.basic import FileSender
from filehashIndex.FHIndex import FileHashIndexer
from communication.message import P2PMessage
from iwant.constants.server_event_constants import *
from iwant.protocols import BaseProtocol
from iwant.config import CLIENT_DAEMON_HOST, CLIENT_DAEMON_PORT
from fuzzywuzzy import fuzz, process
import pickle

class backend(BaseProtocol):
    def __init__(self, factory):
        self.factory = factory
        self.message_codes = {
            HANDSHAKE : self._handshake,
            LIST_ALL_FILES : self._list_file,
            2 : self._load_file,
            3 : self._start_transfer,
            LEADER: self._update_leader,
            FILE_SYS_EVENT: self._filesystem_modified,
            HASH_DUMP : self._dump_data_from_peers,
            SEARCH_REQ : self._leader_send_list,
            LOOKUP : self._leader_lookup,
            SEARCH_RES : self._send_resp_client
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
        resMessage = P2PMessage(key=HANDSHAKE,data=[])
        self.sendLine(resMessage)

    def _list_file(self):
        if self.factory.state==1:
            resMessage = P2PMessage(key=LIST_ALL_FILES, data=self.factory.indexer.reduced_index())
            self.sendLine(resMessage)
        else:
            resMessage = P2PMessage(key=ERROR_LIST_ALL_FILES,data='File hashing incomplete')
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
        self.factory.leader = leader
        print 'Leader {0}'.format(self.factory.book.leader)
        if self.factory.state == 1 and self.factory.leader is not None:
            self.factory.gather_data_then_notify()

    def _filesystem_modified(self, data):
        print 'file system modified'
        self.factory.state = 1  # Ready
        if self.factory.state == 1 and self.factory.leader is not None:
            self.factory.gather_data_then_notify()

    def _dump_data_from_peers(self, data):
        uuid, dump = data
        print 'UUID {0}'.format(uuid)
        self.factory.data_from_peers[uuid] = dump

    def _leader_send_list(self, data):
        if self.factory.leader is not None:
            self.factory._notify_leader(key=LOOKUP, data=data, persist=True, clientConn=self)
        else:
            msg = P2PMessage(key=LEADER_NOT_READY, data=None)
            self.sendLine(msg)
            self.transport.loseConnection()

    def _leader_lookup(self, data):
        uuid, text_search = data
        host, port = self.factory.book.peers[uuid]
        print ' At leader lookup '
        x= []
        l = []
        for val in self.factory.data_from_peers.values():
            l =  pickle.loads(val['hidx'])
            for i in l.values():
                if fuzz.partial_ratio(text_search, i.filename) >= 90:
                    x.append(i)

        #l =  process.extract(data, map(lambda a: a.filename, x))
        update_msg = P2PMessage(key=SEARCH_RES, data=x)
        self.sendLine(update_msg)  # this we are sending it back to the server
        self.transport.loseConnection()  # leader will loseConnection with the requesting server

    def _send_resp_client(self, data):
        print 'sending to client'
        update_msg = P2PMessage(key=SEARCH_RES, data=data)
        self.sendLine(update_msg)  # sending this response to the client
        self.transport.loseConnection() # losing connection with the client

class backendFactory(Factory):
    protocol = backend
    def __init__(self, folder, book):
        self.state = 0
        self.folder = folder
        self.book = book
        self.leader = None
        self.cached_data = None
        self.data_from_peers = {}
        self.file_peer_indexer = {}
        if folder is not None:
            self.indexer = FileHashIndexer(self.folder)
            self.d = threads.deferToThread(self.indexer.index)
            self.d.addCallbacks(self._file_hash_success, self._file_hash_failure)

    def gather_data_then_notify(self):
        self.cached_data = {}
        with open('/var/log/iwant/.hindex') as f:
            hidx = f.read()
        with open('/var/log/iwant/.pindex') as f:
            pidx = f.read()
        self.cached_data['hidx'] = hidx
        self.cached_data['pidx'] = pidx
        self._notify_leader(key=HASH_DUMP, data=None)

    def _notify_leader(self, key=None, data=None, persist=False, clientConn=None):
        from twisted.internet.protocol import Protocol, ClientFactory
        from twisted.internet import reactor

        class ServerLeaderProtocol(BaseProtocol):
            def __init__(self, factory):
                self.buff = ''
                self.delimiter = '#'
                self.factory = factory

            def connectionMade(self):
                update_msg = P2PMessage(key=self.factory.key, data=self.factory.dump)
                self.transport.write(str(update_msg))
                if not persist:
                    self.transport.loseConnection()
                else:
                    print 'persistent connection'

            def serviceMessage(self, data):
                print 'Sending this to client using the transport object'
                update_msg = P2PMessage(message=data)
                update_msg = P2PMessage(key=update_msg.key, data=update_msg.data)
                clientConn.sendLine(update_msg)
                clientConn.transport.loseConnection()

        class ServerLeaderFactory(ClientFactory):
            def __init__(self, key, dump):
                self.key = key
                self.dump = dump

            def buildProtocol(self, addr):
                return ServerLeaderProtocol(self)

        if key == HASH_DUMP:
            factory = ServerLeaderFactory(key=key, dump=(self.book.uuidObj, self.cached_data))
        elif key == LOOKUP:
            factory = ServerLeaderFactory(key=key, dump=(self.book.uuidObj, data))
        print 'state {0} \nleader {1}'.format(self.state, self.leader)
        if self.leader is not None and self.state==1:
            print self.leader[0], self.leader[1]
            host , port = self.leader
            reactor.connectTCP(host, port, factory)

    def _file_hash_success(self, data):
        self.state = 1  # Ready
        self.gather_data_then_notify()

    def _file_hash_failure(self, reason):
        print reason
        raise NotImplementedError

    def buildProtocol(self, addr):
        return backend(self)

    def connectionMade(self):
        print 'connection established'

if __name__ == '__main__':
    #folder = raw_input('Enter absolute path to share :')
    endpoints.serverFromString(reactor,'tcp:1235').listen(backendFactory('/home/nirvik/Pictures'))
    reactor.run()
