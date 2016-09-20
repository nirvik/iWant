from twisted.internet import reactor, defer, threads, endpoints
from twisted.internet.protocol import Factory
from twisted.protocols.basic import FileSender
from filehashIndex.FHIndex import FileHashIndexer
from communication.message import P2PMessage
from constants.events.server import *
from constants.states.server import READY, NOT_READY
from protocols import BaseProtocol
from config import CLIENT_DAEMON_HOST, CLIENT_DAEMON_PORT, SERVER_DAEMON_PORT, DOWNLOAD_FOLDER
from fuzzywuzzy import fuzz, process
import pickle
import os


class backend(BaseProtocol):
    def __init__(self, factory):
        self.factory = factory
        self.message_codes = {
            HANDSHAKE: self._handshake,
            LIST_ALL_FILES: self._list_file,
            INIT_FILE_REQ: self._load_file,
            START_TRANSFER: self._start_transfer,
            LEADER: self._update_leader,
            FILE_SYS_EVENT: self._filesystem_modified,
            HASH_DUMP: self._dump_data_from_peers,
            SEARCH_REQ: self._leader_send_list,
            LOOKUP: self._leader_lookup,
            SEARCH_RES: self._send_resp_client,
            IWANT_PEER_FILE: self._ask_leader_for_peers,
            SEND_PEER_DETAILS: self._leader_looksup_peer,
            IWANT: self._start_transfer
        }
        self.buff = ''
        self.delimiter = '#'
        self.special_handler = None

    def serviceMessage(self, data):
        req = P2PMessage(message=data)
        print 'GOT {0}'.format(req.key)
        try:
            self.message_codes[req.key]()
        except:
            self.message_codes[req.key](req.data)

    def leaderThere(self):
        if self.factory.leader is not None:
            return True
        else:
            return False

    def _handshake(self):
        resMessage = P2PMessage(key=HANDSHAKE, data=[])
        self.sendLine(resMessage)

    def _list_file(self):
        if self.factory.state == READY:
            resMessage = P2PMessage(key=LIST_ALL_FILES, data=self.factory.indexer.reduced_index())
            self.sendLine(resMessage)
        else:
            resMessage = P2PMessage(key=ERROR_LIST_ALL_FILES, data='File hashing incomplete')
            self.sendLine(resMessage)

    def _load_file(self, data):
        fhash = data
        self.fileObj = self.factory.indexer.getFile(fhash)
        fname, _, fsize = self.factory.indexer.hash_index[fhash]
        print fhash, fname, fsize
        ack_msg = P2PMessage(key=FILE_DETAILS_RESP, data=(fname, fsize))
        self.sendLine(ack_msg)

    def _start_transfer(self, data):
        producer = FileSender()
        consumer = self.transport
        fhash = data
        fileObj = self.factory.indexer.getFile(fhash)
        deferred = producer.beginFileTransfer(fileObj, consumer)
        deferred.addCallbacks(self._success, self._failure)

    def _success(self, data):
        print 'Successfully transfered file'
        self.transport.loseConnection()
        self.unhookHandler()

    def _failure(self, reason):
        print 'Failed {0}'.format(reason)
        self.transport.loseConnection()
        self.unhookHandler()

    def _update_leader(self, leader):
        self.factory.leader = leader
        print 'Updating Leader {0}'.format(self.factory.book.leader)
        if self.factory.state == READY and self.leaderThere():
            self.factory.gather_data_then_notify()

    def _filesystem_modified(self, data):
        print 'file system modified'
        #self.factory.state = READY  # Ready
        if self.factory.state == READY and self.leaderThere():
            self.factory.gather_data_then_notify()

    def _dump_data_from_peers(self, data):
        uuid, dump = data
        print 'UUID {0}'.format(uuid)
        self.factory.data_from_peers[uuid] = dump

    def _leader_send_list(self, data):
        if self.leaderThere():
            print 'asking leader to lookup'
            self.factory._notify_leader(key=LOOKUP, data=data, persist=True, clientConn=self)
        else:
            msg = P2PMessage(key=LEADER_NOT_READY, data=None)
            self.sendLine(msg)
            self.transport.loseConnection()

    def _leader_lookup(self, data):
        uuid, text_search = data
        host, port = self.factory.book.peers[uuid]
        print ' At leader lookup '
        filtered_response = []
        l = []
        for val in self.factory.data_from_peers.values():
            l = pickle.loads(val['hidx'])
            for i in l.values():
                if fuzz.partial_ratio(text_search, i.filename) >= 90:
                    filtered_response.append(i)

        # l =  process.extract(data, map(lambda a: a.filename, x))
        update_msg = P2PMessage(key=SEARCH_RES, data=filtered_response)
        self.sendLine(update_msg)  # this we are sending it back to the server
        self.transport.loseConnection()  # leader will loseConnection with the requesting server

    def _send_resp_client(self, data):
        print 'sending to client'
        update_msg = P2PMessage(key=SEARCH_RES, data=data)
        self.sendLine(update_msg)  # sending this response to the client
        self.transport.loseConnection()  # losing connection with the client

    def _ask_leader_for_peers(self, data):
        if self.leaderThere():
            print 'asking leaders for peers'
            print data
            self.factory._notify_leader(key=SEND_PEER_DETAILS, data=data, persist=True, clientConn=self)
        else:
            msg = P2PMessage(key=LEADER_NOT_READY, data=None)
            self.sendLine(msg)
            self.transport.loseConnection()

    def _leader_looksup_peer(self, data):
        uuids = []
        sending_data = []

        for key, val in self.factory.data_from_peers.iteritems():
            if data in pickle.loads(val['hidx']):
                uuids.append(key)

        for uuid in uuids:
            sending_data.append(self.factory.book.peers[uuid])
        msg = P2PMessage(key=PEER_LOOKUP_RESPONSE, data=sending_data)
        self.sendLine(msg)
        self.transport.loseConnection()


class backendFactory(Factory):

    protocol = backend

    def __init__(self, folder, book):
        self.state = NOT_READY
        self.folder = folder
        self.book = book
        self.leader = None
        self.cached_data = None
        self.data_from_peers = {}
        self.file_peer_indexer = {}
        if folder is not None:
            self.indexer = FileHashIndexer(self.folder)
            self.d = threads.deferToThread(self.indexer.index)  # starts indexing files in a folder
            self.d.addCallbacks(self._file_hash_success, self._file_hash_failure)

    def clientConnectionLost(self, connector, reason):
        print 'Lost connection'

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
                self.special_handler = None
                self.factory = factory
                self.events = {
                    PEER_LOOKUP_RESPONSE: self.talk_to_peer,
                    SEARCH_RES: self.send_file_search_response
                }

            def connectionMade(self):
                update_msg = P2PMessage(key=self.factory.key, data=self.factory.dump)
                self.transport.write(str(update_msg))
                if not persist:
                    self.transport.loseConnection()

            def serviceMessage(self, data):
                req = P2PMessage(message=data)
                try:
                    self.events[req.key]()
                except:
                    self.events[req.key](req.data)

            def talk_to_peer(self, data):
                from twisted.internet.protocol import Protocol, ClientFactory, Factory
                from twisted.internet import reactor
                self.transport.loseConnection()
                print 'Got peers {0}'.format(data)
                host, port = data[0]
                print 'hash {0}'.format(self.factory.dump)
                #reactor.connectTCP(host, SERVER_DAEMON_PORT, RemotepeerFactory(INIT_FILE_REQ, self.factory.dump))
                from iwant.protocols import RemotepeerFactory, RemotepeerProtocol
                reactor.connectTCP(host, SERVER_DAEMON_PORT, RemotepeerFactory(INIT_FILE_REQ, self.factory.dump, clientConn))

                #class RemotepeerProtocol(BaseProtocol):
                #    def __init__(self, factory):
                #        self.buff = ''
                #        self.delimiter = '#'
                #        self.factory = factory
                #        self.file_len_recv = 0.0
                #        self.special_handler = None
                #        self.events = {
                #            FILE_DETAILS_RESP: self.start_transfer
                #        }

                #    def connectionMade(self):
                #        update_msg = P2PMessage(key=self.factory.key, data=self.factory.dump)
                #        self.sendLine(update_msg)

                #    def serviceMessage(self, data):
                #        print 'got response from server about file'
                #        req = P2PMessage(message=data)
                #        self.events[req.key](req.data)

                #    def start_transfer(self, data):
                #        update_msg = P2PMessage(key=FILE_TO_BE_DOWNLOADED, data=data)
                #        self.factory.file_details['fname'] = data[0]
                #        self.factory.file_details['size'] = data[1] * 1024.0 * 1024.0
                #        if not os.path.exists(DOWNLOAD_FOLDER):
                #            os.mkdir(DOWNLOAD_FOLDER)
                #        self.factory.file_container = open(DOWNLOAD_FOLDER+os.path.basename(data[0]), 'wb')
                #        clientConn.sendLine(update_msg)
                #        clientConn.transport.loseConnection()
                #        self.hookHandler(self.write_to_file)
                #        print 'Start Trasnfer {0}'.format(self.factory.dump)
                #        update_msg = P2PMessage(key=START_TRANSFER, data=self.factory.dump)
                #        self.sendLine(update_msg)

                #    def write_to_file(self, data):
                #        self.file_len_recv += len(data)
                #        self.factory.file_container.write(data)
                #        if self.file_len_recv >= self.factory.file_details['size']:
                #            self.factory.file_container.close()
                #            print 'Client : File downloaded'
                #            self.transport.loseConnection()

                #class RemotepeerFactory(Factory):

                #    protocol = RemotepeerProtocol

                #    def __init__(self, key, checksum):
                #        self.key = key
                #        self.dump = checksum
                #        self.file_details = {'checksum': checksum}
                #        self.file_container = None

                #    def startedConnecting(self, connector):
                #        print 'connecting'

                #    def clientConnectionLost(self, connector, reason):
                #        print reason

                #    def clientConnectionFailed(self, connector, reason):
                #        print reason.getErrorMessage()

                #    def buildProtocol(self, addr):
                #        return RemotepeerProtocol(self)


            def send_file_search_response(self, data):
                update_msg = P2PMessage(key=SEARCH_RES, data=data)
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
        elif key == SEND_PEER_DETAILS:
            factory = ServerLeaderFactory(key=key, dump=data)
        print 'state {0} \nleader {1}'.format(self.state, self.leader)
        if self.leader is not None and self.state == READY:
            print self.leader[0], self.leader[1]
            host, port = self.leader
            print 'connecting to {0}:{1} for {2}'.format(host, port, key)
            reactor.connectTCP(host, port, factory)

    def _file_hash_success(self, data):
        self.state = READY  # Ready
        self.gather_data_then_notify()

    def _file_hash_failure(self, reason):
        print reason
        raise NotImplementedError

    def buildProtocol(self, addr):
        return backend(self)

    def connectionMade(self):
        print 'connection established'

if __name__ == '__main__':
    # folder = raw_input('Enter absolute path to share :')
    endpoints.serverFromString(reactor, 'tcp:1235').listen(backendFactory('/home/nirvik/Pictures'))
    reactor.run()
