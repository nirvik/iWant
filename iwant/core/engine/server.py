from twisted.internet import reactor, defer, threads, endpoints
from twisted.internet.protocol import Factory
from twisted.protocols.basic import FileSender
from fuzzywuzzy import fuzz, process
import pickle
import os, sys
from fileindexer.findexer import FileHashIndexer
from fileindexer import fileHashUtils
from fileindexer.piece import piece_size
from ..messagebaker import Basemessage
from ..constants import HANDSHAKE, LIST_ALL_FILES, INIT_FILE_REQ, START_TRANSFER, \
        LEADER, DEAD, FILE_SYS_EVENT, HASH_DUMP, SEARCH_REQ, LOOKUP, SEARCH_RES,\
        IWANT_PEER_FILE, SEND_PEER_DETAILS, IWANT, INDEXED, FILE_DETAILS_RESP, \
        ERROR_LIST_ALL_FILES, READY, NOT_READY, PEER_LOOKUP_RESPONSE, LEADER_NOT_READY,\
        REQ_CHUNK, END_GAME, FILE_CONFIRMATION_MESSAGE, INTERESTED, UNCHOKE
from ..protocols import BaseProtocol
from ..config import CLIENT_DAEMON_HOST, CLIENT_DAEMON_PORT, SERVER_DAEMON_PORT
from struct import pack, unpack, calcsize

class ServerException(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Error [{0}] => {1}'.format(self.code, self.msg)

class backend(BaseProtocol):
    def __init__(self, factory):
        self.factory = factory
        self.message_codes = {
            INTERESTED : self._handshake,
            INIT_FILE_REQ: self._load_file,
            LEADER: self._update_leader,
            DEAD  : self._remove_dead_entry,
            FILE_SYS_EVENT: self._filesystem_modified,
            HASH_DUMP: self._dump_data_from_peers,
            SEARCH_REQ: self._leader_send_list,
            LOOKUP: self._leader_lookup,
            IWANT_PEER_FILE: self._ask_leader_for_peers,
            SEND_PEER_DETAILS: self._leader_looksup_peer,
            INDEXED : self.fileindexing_complete,
            REQ_CHUNK: self._send_chunk_response,
            END_GAME: self._end_game
        }
        self.buff = ''
        self.delimiter = '\r'
        self.special_handler = None

    def serviceMessage(self, data):
        '''
            Controller which processes the incoming messages and invokes the appropriate functions
        '''
        req = Basemessage(message=data)
        try:
            self.message_codes[req.key]()
        except:
            self.message_codes[req.key](req.data)

    def leaderThere(self):
        '''
            Tells if leader is present in the network or not
        '''
        if self.factory.leader is not None:
            return True
        else:
            return False

    @defer.inlineCallbacks
    def _handshake(self, data):
        if self.factory.state == READY:
            piece_hashes = yield fileHashUtils.get_piecehashes_of(data, self.factory.dbpool)
            ack_msg = Basemessage(key=FILE_CONFIRMATION_MESSAGE, data=piece_hashes)
            self.sendLine(ack_msg)
        else:
            print 'not ready yet'

    @defer.inlineCallbacks
    def _load_file(self, data):
        fhash = data
        if self.factory.state == READY:
            self.fileObj = yield fileHashUtils.get_file(fhash, self.factory.dbpool)
            self.chunk_size = piece_size(fileHashUtils.get_file_size(self.fileObj.name))
            unchoke_msg = Basemessage(key=UNCHOKE, data=None)
            self.sendLine(unchoke_msg)
        else:
            print 'need to handle this part where files are  not indexed yet'

    def _send_chunk_response(self, piece_data):
        #piece_number, chunk_size = piece_data
        receive_format = "!I"
        piece_number, = unpack(receive_format, piece_data)
        self.fileObj.seek(int(piece_number) * self.chunk_size)  # need a global variable for piece size
        #buffered = self.fileObj.read(chunk_size)
        file_buffer = self.fileObj.read(self.chunk_size)
        len_of_file = len(file_buffer)
        file_chunk_response = pack("!II", len_of_file, piece_number) + file_buffer
        self.sendRaw(file_chunk_response)

    def _end_game(self):
        print 'received end game'
        self.fileObj.close()

    @defer.inlineCallbacks
    def _update_leader(self, leader):
        self.factory.leader = leader
        print 'Updating Leader {0}'.format(self.factory.book.leader)
        if self.factory.state == READY and self.leaderThere():
            file_meta_data = yield fileHashUtils.bootstrap(self.factory.folder, self.factory.dbpool)
            self.factory._notify_leader(HASH_DUMP, file_meta_data)

    def _filesystem_modified(self, data):
        print 'got updates from watchdog daemon {0}'.format(data)
        if self.factory.state == READY and self.leaderThere():
            self.factory._notify_leader(HASH_DUMP, data)
        else:  # dont think this part is required at all
            if self.factory.state == NOT_READY:
                resMessage = Basemessage(key=ERROR_LIST_ALL_FILES, data='File hashing incomplete')
                self.sendLine(resMessage)
            else:
                msg = Basemessage(key=LEADER_NOT_READY, data=None)
                self.sendLine(msg)
            self.transport.loseConnection()

    def _dump_data_from_peers(self, data):
        uuid, dump = data
        operation = dump[0]
        file_properties = dump[1:]
        if uuid not in self.factory.data_from_peers.keys():
            self.factory.data_from_peers[uuid] = {}
            self.factory.data_from_peers[uuid]['hashes'] = {}
            self.factory.data_from_peers[uuid]['filenames'] = {}

        if operation == 'ADD':
            for fproperty in file_properties:
                file_hash = fproperty[2]
                file_name = fproperty[0]
                if file_name in self.factory.data_from_peers[uuid]['filenames']:
                    old_hash_key = self.factory.data_from_peers[uuid]['filenames'][file_name]
                    del self.factory.data_from_peers[uuid]['hashes'][old_hash_key]
                if file_hash not in self.factory.data_from_peers[uuid]:
                    self.factory.data_from_peers[uuid]['hashes'][file_hash] = fproperty
                    self.factory.data_from_peers[uuid]['filenames'][file_name] = file_hash

        elif operation == 'DEL':
            for fproperty in file_properties:
                file_name = fproperty[0]
                file_hash = fproperty[2]
                if file_hash in self.factory.data_from_peers[uuid]['hashes']:
                    del self.factory.data_from_peers[uuid]['hashes'][file_hash]
                    del self.factory.data_from_peers[uuid]['filenames'][file_name]

        print 'got hash dump from {0}'.format(self.factory.data_from_peers[uuid]['filenames'])

    def _remove_dead_entry(self, data):
        uuid = data
        print '@server: removing entry {0}'.format(uuid)
        try:
            del self.factory.data_from_peers[uuid]
        except:
            raise ServerException(1, '{0} not available in cached data'.format(uuid))

    def _leader_send_list(self, data):
        if self.leaderThere():
            print 'lookup request sent to leader'
            self.factory._notify_leader(key=LOOKUP, data=data, persist=True, clientConn=self)
        else:
            msg = Basemessage(key=LEADER_NOT_READY, data=None)
            self.sendLine(msg)
            self.transport.loseConnection()

    def _leader_lookup(self, data):
        uuid, text_search = data
        filtered_response = []
        l = []
        #print ' the length of data_from_peers : {0}'.format(len(self.factory.data_from_peers.values()))
        for uuid in self.factory.data_from_peers.keys():
            for filename in self.factory.data_from_peers[uuid]['filenames']:
                print fuzz.partial_ratio(text_search.lower(), filename.lower())
                if fuzz.partial_ratio(text_search.lower(), filename.lower()) >= 55:
                    file_hash = self.factory.data_from_peers[uuid]['filenames'][filename]
                    filtered_response.append(self.factory.data_from_peers[uuid]['hashes'][file_hash])
        if len(self.factory.data_from_peers.keys()) == 0:
            filtered_response = []

        update_msg = Basemessage(key=SEARCH_RES, data=filtered_response)
        self.sendLine(update_msg)  # this we are sending it back to the server
        self.transport.loseConnection()  # leader will loseConnection with the requesting server

    def _ask_leader_for_peers(self, data):
        if self.leaderThere():
            print 'asking leaders for peers'
            print data
            self.factory._notify_leader(key=SEND_PEER_DETAILS, data=data, persist=True, clientConn=self)
        else:
            msg = Basemessage(key=LEADER_NOT_READY, data=None)
            self.sendLine(msg)
            self.transport.loseConnection()

    def _leader_looksup_peer(self, data):
        '''
            The leader looks up the peer who has the file
            The leader sends a list of peers with the following data
             1.piece hashes of the file
             2.file size
             3.file name
        '''
        uuids = []
        hash_string = ''
        sending_data = []

        for key, val in self.factory.data_from_peers.iteritems():
            value = val['hashes']
            if data in value:
                file_name, file_size, file_hash, file_root_hash = value[data]
                uuids.append(key)

        for uuid in uuids:
            sending_data.append(self.factory.book.peers[uuid])
        sending_data.append(file_root_hash)  # appending hash of pieces
        sending_data.append(file_size)  # appending filesize
        sending_data.append(file_name)  # appending filename
        msg = Basemessage(key=PEER_LOOKUP_RESPONSE, data=sending_data)
        self.sendLine(msg)
        self.transport.loseConnection()

    def fileindexing_complete(self, indexing_response):
        print 'server, indexing complete'
        print 'got the updates as {0}'.format(indexing_response)
        self.factory.state = READY
        old_sharing_folder = None
        if self.factory.sharing_folder is not None:
            old_sharing_folder = self.factory.sharing_folder
        new_folder_indexed_response, old_folder_indexed_response = indexing_response
        self.factory.sharing_folder = indexing_response[1]
        new_folder_request_payload = new_folder_indexed_response[0:1] + new_folder_indexed_response[2:]
        self.factory._notify_leader(HASH_DUMP, new_folder_request_payload)
        if old_sharing_folder != self.factory.sharing_folder and old_sharing_folder is not None:
            self.factory._notify_leader(HASH_DUMP, old_folder_request_payload)


class backendFactory(Factory):

    protocol = backend

    def __init__(self, book, dbpool):
        self.state = NOT_READY  # file indexing state
        self.sharing_folder = None
        self.book = book  # book contains all the peer addresses
        self.leader = None
        self.cached_data = None
        self.data_from_peers = {}
        self.indexer = None
        self.dbpool = dbpool

    def clientConnectionLost(self, connector, reason):
        print 'Lost connection'

    def _notify_leader(self, key=None, data=None, persist=False, clientConn=None):
        from twisted.internet.protocol import Protocol, ClientFactory
        from twisted.internet import reactor

        class ServerLeaderProtocol(BaseProtocol):
            def __init__(self, factory):
                self.buff = ''
                self.delimiter = '\r'
                self.special_handler = None
                self.factory = factory
                self.events = {
                    PEER_LOOKUP_RESPONSE: self.talk_to_peer,
                    SEARCH_RES: self.send_file_search_response
                }

            def connectionMade(self):
                update_msg = Basemessage(key=self.factory.key, data=self.factory.dump)
                self.transport.write(str(update_msg))
                if not persist:
                    self.transport.loseConnection()

            def serviceMessage(self, data):
                req = Basemessage(message=data)
                try:
                    self.events[req.key]()
                except:
                    self.events[req.key](req.data)

            def talk_to_peer(self, data):
                from twisted.internet.protocol import Protocol, ClientFactory, Factory
                from twisted.internet import reactor
                self.transport.loseConnection()
                #print 'Got peers {0}'.format(data)
                if len(data) == 0:
                    print 'Tell the client that peer lookup response is 0. Have to handle this'
                    #update_msg = Basemessage(key=SEARCH_RES, data=data)
                else:
                    from ..protocols import RemotepeerFactory, RemotepeerProtocol
                    file_details = {
                        'file_name' : data[-1],
                        'file_size' : data[-2],
                        'file_root_hash' : data[-3],
                        'checksum' : self.factory.dump
                    }
                    download_folder = self.factory.dump_folder
                    peers = data[:-3]
                    peers = peers * 4
                    print 'the following data is received from the leader \n{0}\n{1}'.format(file_details, peers)
                    P2PFactory = RemotepeerFactory(INIT_FILE_REQ, clientConn, download_folder, file_details, self.factory.dbpool)
                    map(lambda host: reactor.connectTCP(host,SERVER_DAEMON_PORT, P2PFactory),
                            map(lambda host: host[0], peers))

            def send_file_search_response(self, data):
                update_msg = Basemessage(key=SEARCH_RES, data=data)
                clientConn.sendLine(update_msg)
                clientConn.transport.loseConnection()

        class ServerLeaderFactory(ClientFactory):
            def __init__(self, key, dump, dump_folder=None, dbpool=None):
                self.key = key
                self.dump = dump
                if dump_folder is not None:
                    self.dump_folder = dump_folder
                if dbpool is not None:
                    self.dbpool = dbpool

            def buildProtocol(self, addr):
                return ServerLeaderProtocol(self)

        if key == HASH_DUMP:
            factory = ServerLeaderFactory(key=key, dump=(self.book.uuidObj, data))
        elif key == LOOKUP:
            factory = ServerLeaderFactory(key=key, dump=(self.book.uuidObj, data))
        elif key == SEND_PEER_DETAILS:
            factory = ServerLeaderFactory(key=key, dump=data, \
                    dump_folder='', dbpool=self.dbpool)
            #factory = ServerLeaderFactory(key=key, dump=data, \
            #        dump_folder=self.download_folder, dbpool=self.dbpool)

        if key == SEND_PEER_DETAILS or key == LOOKUP:
            if self.leader is not None:
                host, port = self.leader[0] , self.leader[1]
                print 'connecting to {0}:{1} for {2}'.format(host, port, key)
                reactor.connectTCP(host, port, factory)
        elif key == HASH_DUMP:
            if self.leader is not None and self.state == READY:
                host, port = self.leader[0] , self.leader[1]
                print 'connecting to {0}:{1} for {2}'.format(host, port, key)
                reactor.connectTCP(host, port, factory)

    def buildProtocol(self, addr):
        return backend(self)

    def connectionMade(self):
        print 'connection established'
