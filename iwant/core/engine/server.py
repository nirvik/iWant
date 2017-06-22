from twisted.internet import defer, interfaces
from twisted.internet.protocol import Factory
from zope.interface import implements
from fuzzywuzzy import fuzz
import os
from struct import pack
from fileindexer import fileHashUtils
from fileindexer.piece import piece_size
from iwant.core.messagebaker import bake, unbake
from iwant.core.constants import INIT_FILE_REQ, LEADER, PEER_DEAD, \
    FILE_SYS_EVENT, HASH_DUMP, SEARCH_REQ, LOOKUP, SEARCH_RES,\
    IWANT_PEER_FILE, SEND_PEER_DETAILS, INDEXED,\
    ERROR_LIST_ALL_FILES, READY, NOT_READY, PEER_LOOKUP_RESPONSE, LEADER_NOT_READY,\
    REQ_CHUNK, END_GAME, FILE_CONFIRMATION_MESSAGE, INTERESTED, UNCHOKE, CHANGE, SHARE,\
    NEW_DOWNLOAD_FOLDER_RES, NEW_SHARED_FOLDER_RES, GET_HASH_IDENTITY, HASH_IDENTITY_RESPONSE,\
    CHUNK_SIZE, FILE_RESP_FMT, HASH_NOT_PRESENT
from iwant.cli.utils import WARNING_LOG, ERROR_LOG, print_log
from iwant.core.protocols import BaseProtocol
from iwant.core.config import SERVER_DAEMON_PORT
from iwant.core.engine.monitor.watching import ScanFolder
from iwant.core.engine.monitor.callbacks import filechangeCB
from iwant.core.config import CLIENT_DAEMON_HOST


class ServerException(Exception):

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Error [{0}] => {1}'.format(self.code, self.msg)


class FilePumper(object):
    implements(interfaces.IProducer)
    last_sent = ''
    deferred = None
    FILE_SEND_FMT = FILE_RESP_FMT

    def beginFileTransfer(self, file, consumer, piece_range):
        # print 'this is the piece range {0}'.format(piece_range)
        self.file = file
        self.consumer = consumer
        # (0,16,1780,16)
        first_piece, first_blocks, last_piece, last_blocks = piece_range
        self.file.seek(first_blocks * first_piece * CHUNK_SIZE)
        self.total_file_to_read = (
            last_piece - 1 - first_piece) * (first_blocks) * (CHUNK_SIZE) + (last_blocks * CHUNK_SIZE)
        self.total_read = 0
        self.block_number = 0  # keeps updating with every read of the file
        # keeps updating every time chunk_number completes a cycle
        self.piece_number = first_piece

        self.last_piece_number = last_piece - 1
        self.blocks_per_piece = first_blocks - 1
        self.blocks_per_last_piece = last_blocks - 1
        self.deferred = deferred = defer.Deferred()

        self.consumer.registerProducer(self, False)
        return deferred

    def transform(self, chunk):
        return pack(
            self.FILE_SEND_FMT,
            self.piece_number,
            self.block_number,
            len(chunk)) + chunk

    def resumeProducing(self):
        chunk = ''
        if self.file:
            chunk = self.file.read(CHUNK_SIZE)

        if not chunk or self.total_read >= self.total_file_to_read:
            self.file = None
            self.consumer.unregisterProducer()
            if self.deferred:
                self.deferred.callback(self.last_sent)
                self.deferred = None
            return

        self.total_read += len(chunk)
        chunk = self.transform(chunk)
        self.consumer.write(chunk)
        if self.piece_number < self.last_piece_number:
            if self.block_number < self.blocks_per_piece:
                self.block_number += 1
            else:
                self.block_number = 0
                self.piece_number += 1
        elif self.piece_number == self.last_piece_number:
            if self.block_number < self.blocks_per_last_piece:
                self.block_number += 1
            else:
                self.block_number = 0
                self.piece_number += 1

        self.last_sent = chunk[-1:]

    def pauseProducing(self):
        pass

    def stopProducing(self):
        if self.deferred:
            self.deferred.errback(Exception('Consumer asked us to stop'))
            self.deferred = None


class backend(BaseProtocol):

    def __init__(self, factory):
        self.factory = factory
        self.message_codes = {
            INTERESTED: self._handshake,
            INIT_FILE_REQ: self._load_file,
            LEADER: self._update_leader,
            PEER_DEAD: self._remove_dead_entry,
            FILE_SYS_EVENT: self._filesystem_modified,
            HASH_DUMP: self._dump_data_from_peers,
            # comes only from your local iwant client
            SEARCH_REQ: self._leader_send_list,
            LOOKUP: self._leader_lookup,
            # comes only from your local iwant client
            IWANT_PEER_FILE: self._ask_leader_for_peers,
            SEND_PEER_DETAILS: self._leader_looksup_peer,
            INDEXED: self.fileindexing_complete,
            REQ_CHUNK: self._send_chunk_response,
            END_GAME: self._end_game,
            # comes only from your local iwant client
            CHANGE: self._change_download_folder,
            # comes only from your local iwant client
            SHARE: self._share_new_folder,
            GET_HASH_IDENTITY: self._send_folder_structure
        }
        self.buff = ''
        self.delimiter = '\r'
        self.special_handler = None

    def serviceMessage(self, data):
        '''
            Controller which processes the incoming messages and invokes
            the appropriate functions
        '''
        key, value = unbake(message=data)
        if key in [SEARCH_REQ, IWANT_PEER_FILE, CHANGE, SHARE]:
            client_host = self.transport.getHost().host
            # these requests can only from the local iwant client.
            if client_host == CLIENT_DAEMON_HOST:
                self.message_codes[key](value)
            else:
                self.transport.loseConnection()
        else:
            self.message_codes[key](value)

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
        filehash = data['filehash']
        if self.factory.state == READY:
            piece_hashes = yield fileHashUtils.get_piecehashes_of(filehash, self.factory.dbpool)
            ack_msg = bake(FILE_CONFIRMATION_MESSAGE, piecehashes=piece_hashes)
            self.sendLine(ack_msg)
        else:
            print_log('not ready yet', WARNING_LOG)

    @defer.inlineCallbacks
    def _load_file(self, data):
        fhash = data['filehash']
        if self.factory.state == READY:
            self.fileObj = yield fileHashUtils.get_file(fhash, self.factory.dbpool)
            self.chunk_size = piece_size(
                fileHashUtils.get_file_size(
                    self.fileObj.name))
            # unchoke_msg = Basemessage(key=UNCHOKE, data=None)
            unchoke_msg = bake(key=UNCHOKE, unchoke=True)
            self.sendLine(unchoke_msg)
        else:
            print_log(
                'need to handle this part where files are  not indexed yet',
                ERROR_LOG)

    def _send_chunk_response(self, data):
        piece_range = data['piece_data']
        sender = FilePumper()
        d = sender.beginFileTransfer(self.fileObj, self.transport, piece_range)
        d.addCallback(self.transfer_completed)

    def transfer_completed(self, data):
        # print 'no more'
        pass

    def _end_game(self, data):
        if data['end_game']:
            print_log('received end game')
            self.fileObj.close()

    @defer.inlineCallbacks
    def _send_folder_structure(self, data):
        requested_hash = data['checksum']
        file_structure_response = yield fileHashUtils.get_structure(requested_hash, self.factory.dbpool)
        hash_identity_response_msg = bake(
            key=HASH_IDENTITY_RESPONSE,
            file_structure_response=file_structure_response)
        self.sendLine(hash_identity_response_msg)

    @defer.inlineCallbacks
    def _update_leader(self, data):
        self.factory.leader = data['leader']
        print_log('Updating Leader {0}'.format(self.factory.book.leader))
        if self.factory.state == READY and self.leaderThere(
        ) and self.factory.shared_folder is not None:
            file_meta_data = yield fileHashUtils.bootstrap(self.factory.shared_folder, self.factory.dbpool)
            self.fileindexing_complete(file_meta_data)

    def _filesystem_modified(self, data):
        # print 'got updates from watchdog daemon {0}'.format(data)
        if self.factory.state == READY and self.leaderThere():
            self.factory._notify_leader(HASH_DUMP, data)
        else:  # dont think this part is required at all
            if self.factory.state == NOT_READY:
                # resMessage = Basemessage(key=ERROR_LIST_ALL_FILES, data='File hashing incomplete')
                resMessage = bake(
                    key=ERROR_LIST_ALL_FILES,
                    data='File hashing incomplete')
                self.sendLine(resMessage)
            else:
                # msg = Basemessage(key=LEADER_NOT_READY, data=None)
                msg = bake(
                    key=LEADER_NOT_READY,
                    reason='Tracker is not available')
                self.sendLine(msg)
            self.transport.loseConnection()

    def _dump_data_from_peers(self, data):
        uuid = data['identity']
        file_addition_updates = data['operation']['ADD']
        file_removal_updates = data['operation']['DEL']

        for file_properties in file_addition_updates:
            pass
            # print_log(
            #     '[Leader Adding] {0} \t {1}'.format(
            #         file_properties[0],
            #         file_properties[1]))
        for file_properties in file_removal_updates:
            print_log('[Leader Removing] {0}'.format(file_properties[0]))

        if uuid not in self.factory.data_from_peers.keys():
            self.factory.data_from_peers[uuid] = {}
            self.factory.data_from_peers[uuid]['hashes'] = {}
            self.factory.data_from_peers[uuid]['filenames'] = {}

        for fproperty in file_addition_updates:
            file_hash = fproperty[2]
            file_name = fproperty[0]
            if file_name in self.factory.data_from_peers[uuid]['filenames']:
                old_hash_key = self.factory.data_from_peers[
                    uuid]['filenames'][file_name]
                try:
                    del self.factory.data_from_peers[
                        uuid]['hashes'][old_hash_key]
                except Exception as e:
                    print_log(
                        'need to handle this major issue : {0}, for reason {1}'.format(
                            file_name,
                            e),
                        WARNING_LOG)
            if file_hash not in self.factory.data_from_peers[uuid]:
                self.factory.data_from_peers[uuid][
                    'hashes'][file_hash] = fproperty
                self.factory.data_from_peers[uuid][
                    'filenames'][file_name] = file_hash

        for fproperty in file_removal_updates:
            file_name = fproperty[0]
            file_hash = fproperty[2]
            if file_hash in self.factory.data_from_peers[uuid]['hashes']:
                del self.factory.data_from_peers[uuid]['hashes'][file_hash]
                del self.factory.data_from_peers[uuid]['filenames'][file_name]
                print_log(
                    'deleting hash : {0} filename {1}'.format(
                        file_hash,
                        file_name))
            else:
                if file_name in self.factory.data_from_peers[
                        uuid]['filenames']:
                    #  very very stupid hack [ just because of empty files ]
                    del self.factory.data_from_peers[
                        uuid]['filenames'][file_name]
                    print_log(
                        'deleting HACK : {0} filename {1}'.format(
                            file_hash,
                            file_name))

        #  print 'got hash dump from
        #  {0}'.format(self.factory.data_from_peers[uuid]['filenames'])

    def _remove_dead_entry(self, data):
        uuid = data['dead_uuid']
        print_log('removing entry {0}'.format(uuid))
        try:
            del self.factory.data_from_peers[uuid]
        except:
            raise ServerException(
                1,
                '{0} not available in cached data'.format(uuid))

    def _leader_send_list(self, data):
        if self.leaderThere():
            print_log('lookup request sent to leader')
            search_query = data['search_query']
            self.factory._notify_leader(
                key=LOOKUP,
                data=search_query,
                persist=True,
                clientConn=self)
        else:
            # msg = Basemessage(key=LEADER_NOT_READY, data=None)
            msg = bake(key=LEADER_NOT_READY, reason='Tracker is not available')
            self.sendLine(msg)
            self.transport.loseConnection()

    def _leader_lookup(self, data):
        #  TODO: there is absolutely no use of sending uuid of the message initiator
        # uuid, text_search = data
        text_search = data['search_query']
        filtered_response = []
        for uuid in self.factory.data_from_peers.keys():
            for filename in self.factory.data_from_peers[uuid]['filenames']:
                if fuzz.partial_ratio(
                        text_search.lower(),
                        filename.lower()) >= 55:
                    file_hash = self.factory.data_from_peers[
                        uuid]['filenames'][filename]
                    try:
                        filtered_response.append(
                            self.factory.data_from_peers[uuid]['hashes'][file_hash])
                    except Exception as e:
                        print e
                        print_log(
                            'BIGGEST MESS UP {0}'.format(filename),
                            WARNING_LOG)
        if len(self.factory.data_from_peers.keys()) == 0:
            filtered_response = []

        # update_msg = Basemessage(key=SEARCH_RES, data=filtered_response)
        update_msg = bake(SEARCH_RES, search_query_response=filtered_response)
        self.sendLine(update_msg)  # this we are sending it back to the server
        #  leader will loseConnection with the requesting server
        self.transport.loseConnection()

    def _ask_leader_for_peers(self, data):
        if self.leaderThere():
            print_log('asking leaders for peers')
            #print_log( data)
            filehash = data['filehash']
            self.factory._notify_leader(
                key=SEND_PEER_DETAILS,
                data=filehash,
                persist=True,
                clientConn=self)
        else:
            # msg = Basemessage(key=LEADER_NOT_READY, data=None)
            msg = bake(key=LEADER_NOT_READY, reason='Tracker is not available')
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
        sending_data = []
        peers_list = []
        filehash = data['filehash']

        for key, val in self.factory.data_from_peers.iteritems():
            value = val['hashes']
            if filehash in value:
                file_name, file_size, file_hash, file_root_hash = value[
                    filehash]
                uuids.append(key)

        for uuid in uuids:
            sending_data.append(self.factory.book.peers[uuid])
            peers_list.append(self.factory.book.peers[uuid])

        try:
            sending_data.append(file_root_hash)  # appending hash of pieces
            sending_data.append(file_size)  # appending filesize
            sending_data.append(file_name)  # appending filename
            # msg = Basemessage(key=PEER_LOOKUP_RESPONSE, data=sending_data)

            response = {}
            response['peers'] = peers_list
            response['file_root_hash'] = file_root_hash
            response['file_size'] = file_size
            response['file_name'] = file_name
            # response['file_hash'] = filehash
            msg = bake(PEER_LOOKUP_RESPONSE, peer_lookup_response=response)
            self.sendLine(msg)
            self.transport.loseConnection()
        except:
            msg = bake(
                key=HASH_NOT_PRESENT,
                reason='No such file exists')
            self.sendLine(msg)
            self.transport.loseConnection()

    def fileindexing_complete(self, indexing_response):
        # print_log('Files completely indexed')
        # print_log('SHARING {0}'.format(indexing_response['shared_folder']))
        for file_name in indexing_response['ADD']:
            print_log('[Adding] {0} \t {1}'.format(file_name[0], file_name[1]))
        for file_name in indexing_response['DEL']:
            print_log('[Removing] {0}'.format(file_name[0]))

        self.factory.state = READY
        del indexing_response['shared_folder']
        if self.leaderThere():
            self.factory._notify_leader(HASH_DUMP, indexing_response)

    def _change_download_folder(self, data):
        new_download_folder = data['download_folder']
        msg = bake(
            NEW_DOWNLOAD_FOLDER_RES,
            download_folder_response=new_download_folder)
        if not os.path.isdir(new_download_folder):
            msg = bake(
                NEW_DOWNLOAD_FOLDER_RES,
                download_folder_response='Invalid download path provided')
        else:
            print_log(
                'changed download folder to {0}'.format(new_download_folder))
            self.factory.download_folder = new_download_folder
        self.sendLine(msg)
        self.transport.loseConnection()

    @defer.inlineCallbacks
    def _share_new_folder(self, data):
        new_shared_folder = data['shared_folder']
        msg = bake(
            NEW_SHARED_FOLDER_RES,
            shared_folder_response=new_shared_folder)
        if not os.path.isdir(new_shared_folder):
            msg = bake(
                NEW_SHARED_FOLDER_RES,
                shared_folder_response='Invalid shared folder path provided')
        elif new_shared_folder != self.factory.shared_folder:
            self.factory.shared_folder = new_shared_folder
            file_meta_data = yield fileHashUtils.bootstrap(self.factory.shared_folder, self.factory.dbpool)
            ScanFolder(
                self.factory.shared_folder,
                filechangeCB,
                self.factory.dbpool)
            self.fileindexing_complete(file_meta_data)
        self.sendLine(msg)
        self.transport.loseConnection()


class backendFactory(Factory):

    protocol = backend

    def __init__(self, book, **kwargs):
        self.state = NOT_READY  # file indexing state
        self.book = book  # book contains all the peer addresses
        self.leader = None
        self.cached_data = None
        self.data_from_peers = {}
        self.indexer = None
        self.dbpool = kwargs['dbpool']
        self.download_folder = kwargs['download_folder']
        self.shared_folder = kwargs['shared_folder']

    def clientConnectionLost(self, connector, reason):
        pass

    def _notify_leader(
            self,
            key=None,
            data=None,
            persist=False,
            clientConn=None):
        from twisted.internet.protocol import ClientFactory
        from twisted.internet import reactor

        class ServerLeaderProtocol(BaseProtocol):

            def __init__(self, factory):
                self.buff = ''
                self.delimiter = '\r'
                self.special_handler = None
                self.factory = factory
                self.events = {
                    PEER_LOOKUP_RESPONSE: self.talk_to_peer,
                    SEARCH_RES: self.send_file_search_response,
                    HASH_NOT_PRESENT: self.invalid_file_response
                }

            def connectionMade(self):
                if self.factory.key == LOOKUP:
                    update_msg = bake(LOOKUP, search_query=self.factory.dump)
                elif self.factory.key == HASH_DUMP:
                    update_msg = bake(
                        HASH_DUMP,
                        identity=self.factory.identity,
                        operation=self.factory.dump)
                elif self.factory.key == SEND_PEER_DETAILS:
                    update_msg = bake(
                        SEND_PEER_DETAILS,
                        filehash=self.factory.dump)
                # self.transport.write(str(update_msg))
                self.sendLine(update_msg)
                if not persist:
                    self.transport.loseConnection()

            def serviceMessage(self, data):
                key, value = unbake(message=data)
                self.events[key](value)

            def invalid_file_response(self, data):
                reason = data['reason']
                msg = bake(HASH_NOT_PRESENT, reason=reason)
                clientConn.sendLine(msg)
                clientConn.transport.loseConnection()

            def talk_to_peer(self, data):
                from twisted.internet import reactor
                self.transport.loseConnection()
                if len(data) == 0:
                    print_log(
                        'Tell the client that peer lookup response is 0. Have to handle this',
                        WARNING_LOG)
                    # update_msg = Basemessage(key=SEARCH_RES, data=data)
                else:
                    from iwant.core.protocols import DownloadManagerFactory
                    response = data['peer_lookup_response']
                    file_root_hash = response['file_root_hash']
                    peers = map(lambda host: host[0], response['peers'])
                    checksum = self.factory.dump
                    reactor.connectTCP(
                        peers[0],
                        SERVER_DAEMON_PORT,
                        DownloadManagerFactory(
                            clientConn,
                            self.factory.download_folder,
                            checksum,
                            file_root_hash,
                            peers,
                            self.factory.dbpool))

            def send_file_search_response(self, data):
                update_msg = bake(
                    SEARCH_RES,
                    search_query_response=data['search_query_response'])
                clientConn.sendLine(update_msg)
                clientConn.transport.loseConnection()

        class ServerLeaderFactory(ClientFactory):

            def __init__(self, key, dump, **kwargs):
                self.key = key
                self.dump = dump
                self.download_folder = kwargs['download_folder']
                self.dbpool = kwargs['dbpool']
                self.identity = kwargs['identity']

            def clientConnectionLost(self, connector, reason):
                # print 'connection with leader dropped'
                pass

            def clientConnectionFailed(self, connector, reason):
                # print 'connection with leader dropped'
                pass

            def buildProtocol(self, addr):
                return ServerLeaderProtocol(self)

        if key == HASH_DUMP:
            factory = ServerLeaderFactory(
                key=key,
                dump=data,
                identity=self.book.uuidObj,
                dbpool=None,
                download_folder=None)
        elif key == LOOKUP:
            factory = ServerLeaderFactory(
                key=key,
                dump=data,
                identity=None,
                dbpool=None,
                download_folder=None)
        elif key == SEND_PEER_DETAILS:
            factory = ServerLeaderFactory(
                key=key,
                dump=data,
                identity=None,
                download_folder=self.download_folder,
                dbpool=self.dbpool)

        if key == SEND_PEER_DETAILS or key == LOOKUP:
            if self.leader is not None:
                host, port = self.leader[0], self.leader[1]
                print_log(
                    'connecting to {0}:{1} for {2}'.format(
                        host,
                        port,
                        key))
                reactor.connectTCP(host, port, factory)
        elif key == HASH_DUMP:
            if self.leader is not None and self.state == READY:
                host, port = self.leader[0], self.leader[1]
                print_log(
                    'connecting to {0}:{1} for {2}'.format(
                        host,
                        port,
                        key))
                reactor.connectTCP(host, port, factory)

    def buildProtocol(self, addr):
        return backend(self)

    def connectionMade(self):
        pass
