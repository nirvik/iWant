from twisted.internet import reactor
from twisted.internet.protocol import Protocol, ClientFactory, DatagramProtocol, Factory
from engine.fileindexer.piece import piece_size
from messagebaker import bake, unbake
from constants import LEADER, PEER_DEAD, FILE_TO_BE_DOWNLOADED,\
    REQ_CHUNK, FILE_CONFIRMATION_MESSAGE, INIT_FILE_REQ,\
    INTERESTED, UNCHOKE, GET_HASH_IDENTITY, HASH_IDENTITY_RESPONSE
from iwant.core.engine.fileindexer import fileHashUtils
import os
import progressbar
import math
import hashlib
import time
from struct import calcsize
from iwant.core.config import SERVER_DAEMON_PORT
from iwant.core.constants import CHUNK_SIZE


class BaseProtocol(Protocol):

    def __init__(self):
        self.special_handler = None

    def connectionMade(self):
        pass

    def sendLine(self, line):
        self.transport.write(str(line))

    def sendRaw(self, buffered):
        self.transport.write(buffered)

    def escape_dollar_sign(self, data):
        return data.replace(self.delimiter, '')

    def hookHandler(self, fn):
        self.special_handler = fn

    def unhookHandler(self):
        self.special_handler = None

    def dataReceived(self, data):
        if self.special_handler:
            self.special_handler(data)
        else:
            for char in data:
                self.buff += char
                if char == self.delimiter:
                    request_str = self.escape_dollar_sign(self.buff)
                    self.buff = ''
                    self.serviceMessage(request_str)

    def serviceMessage(self, message):
        pass


class FilemonitorClientProtocol(Protocol):

    '''
        This protocol updates the server about:
        1. If all the files in the shared folder are indexed or not
        2. Inform the server about the new updated indexed files(the entire dump)
    '''

    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        print '@filemonitor protocol'
        print 'event {0}'.format(self.factory.event)
        updated_msg = bake(
            self.factory.event,
            shared_folder=self.factory.updates['shared_folder'],
            ADD=self.factory.updates['ADD'],
            DEL=self.factory.updates['DEL'])
        self.transport.write(updated_msg)
        self.transport.loseConnection()


class FilemonitorClientFactory(ClientFactory):

    def __init__(self, event, updates):
        '''
            :param config_path : string
            config_path contains the .iwant directory path
        '''
        self.event = event
        self.updates = updates

    def buildProtocol(self, addr):
        return FilemonitorClientProtocol(self)


class PeerdiscoveryProtocol(DatagramProtocol):

    '''
        Used by the election daemon
    '''

    def escape_hash_sign(self, string):
        return string.replace(self.delimiter, '')

    def _process_msg(self, req, addr):
        pass

    def send(self, msgObj, addr):
        self.transport.write(str(msgObj), tuple(addr))

    def datagramReceived(self, datagram, addr):
        for dat in datagram:
            self.buff += dat
            if dat == self.delimiter:
                req_str = self.escape_hash_sign(self.buff)
                self.buff = ''
                self._process_msg(req_str, addr)
        self.buff = ''


class ServerElectionProtocol(Protocol):

    '''
        This protocol is used by the election daemon to communicate with the server about:
            1. New leader
            2. Node is dead (only the leader node passes information about the dead node to its local server. Rest done)
    '''

    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        if self.factory.dead_peer is None:
            update_msg = bake(
                key=LEADER,
                leader=(
                    self.factory.leader_host,
                    self.factory.leader_port))
        else:
            update_msg = bake(PEER_DEAD, dead_uuid=self.factory.dead_peer)
        self.transport.write(str(update_msg))
        self.transport.loseConnection()


class ServerElectionFactory(ClientFactory):

    def __init__(self, leader_host, leader_port, dead_peer=None):
        '''
            :param leader_host : string
            :param leader_port : int
            :param dead_peer : bool
        '''
        self.leader_host = leader_host
        self.leader_port = leader_port
        self.dead_peer = dead_peer

    def buildProtocol(self, addr):
        return ServerElectionProtocol(self)


class FileDownloadProtocol(BaseProtocol):

    def __init__(self, factory):
        self.factory = factory
        self.piece_hashes = ''
        self.delimiter = '\r'
        self.special_handler = None
        self.buff = ''
        self.event_handlers = {
            FILE_CONFIRMATION_MESSAGE: self.verify_pieces,
            UNCHOKE: self._start_transfer
        }

    def connectionMade(self):
        initiate_file_transfer_req_msg = bake(
            INTERESTED,
            filehash=self.factory.file_checksum)
        self.sendLine(initiate_file_transfer_req_msg)

    def serviceMessage(self, data):
        key, value = unbake(data)
        self.event_handlers[key](value)

    def verify_pieces(self, data):
        self.piece_hashes = data['piecehashes']
        hasher = hashlib.md5()
        hasher.update(self.piece_hashes)
        if hasher.hexdigest() == self.factory.file_root_hash:
            load_file_msg = bake(
                INIT_FILE_REQ,
                filehash=self.factory.file_checksum)
            self.sendLine(load_file_msg)

    def _start_transfer(self, data):
        if data['unchoke']:
            self.hookHandler(self.rawDataReceived)
            self.request_for_pieces(bootstrap=True)
            self.factory.start_time = time.time()

    def rawDataReceived(self, data):
        piece_number, block_number, file_data = data.split(';', 2)
        self.factory.download_status += len(file_data)
        self.factory.file_handler.seek(piece_number * self.factory.piece_size + block_number * CHUNK_SIZE)
        self.factory.file_handler.write(file_data)
        print 'Completed {0}'.format(self.factory.download_status * 100.0 / (self.factory.file_size * 1000.0 * 1000.0))
        if self.factory.download_status >= self.factory.file_size * \
                1000.0 * 1000.0:
            print 'closing connection'
            self.factory.file_handler.close()
            self.transport.loseConnection()

    def request_for_pieces(self, bootstrap=None):
        piece_range_data = [self.factory.start_piece, self.factory.blocks_per_piece, self.last_piece, self.factory.blocks_per_last_piece]
        request_chunk_msg = bake(REQ_CHUNK, piece_data=piece_range_data)  # have to request for a chunk range
        self.sendLine(request_chunk_msg)


class FileDownloadFactory(ClientFactory):
    protocol = FileDownloadProtocol

    def __init__(self, **kwargs):
        self.peers_list = kwargs['peers_list']
        self.file_handler = kwargs['file_handler']
        self.file_size = kwargs['file_size']
        self.file_checksum = kwargs['file_checksum']
        self.file_root_hash = kwargs['file_root_hash']

        self.piece_size = piece_size(self.file_size)
        self.total_pieces = int(math.ceil(self.file_size * 1000.0 * 1000.0 / self.piece_size))
        self.start_piece = 0
        self.last_piece = self.total_pieces - 1
        self.last_piece_size = int(self.file_size * 1000.0 * 1000.0 - ((self.total_pieces - 1) * self.piece_size))
        self.blocks_per_piece = int(self.piece_size / CHUNK_SIZE)
        self.blocks_per_last_piece = int(math.ceil(self.last_piece_size / CHUNK_SIZE))
        self.download_status = 0.0

    def reconnect(self, connector, reason):
        self.peers_list.remove(connector.host)
        if len(self.peers_list) != 0:
            connector.host = self.peers_list[0]
            connector.connect()
        else:
            print 'out of peers'

    def clientConnectionLost(self, connector, reason):
        # self.reconnect(connector, reason)
        pass

    def clientConnectionFailed(self, connector, reason):
        self.reconnect(connector, reason)

    def buildProtocol(self, addr):
        return FileDownloadProtocol(self)


class DownloadManagerProtocol(BaseProtocol):

    def __init__(self, factory):
        self.factory = factory
        self.delimiter = '\r'
        self.special_handler = None
        self.buff = ''
        self.event_handlers = {
            HASH_IDENTITY_RESPONSE: self._build_new_files_folders
        }

    def connectionMade(self):
        get_file_identity_msg = bake(
            GET_HASH_IDENTITY,
            checksum=self.factory.checksum)
        self.sendLine(get_file_identity_msg)

    def serviceMessage(self, data):
        key, value = unbake(message=data)
        self.event_handlers[key](value)

    def bake_client_message(self, msg):
        msg_to_client = bake(
            FILE_TO_BE_DOWNLOADED,
            message=msg)
        self.factory.client_connection.sendLine(msg_to_client)
        self.factory.client_connection.transport.loseConnection()

    def _build_new_files_folders(self, response):
        # self.transport.loseConnection()
        client_response = {}
        meta_info = response['file_structure_response']
        if meta_info['isFile']:
            filesize = meta_info['size']
            # file_root_hash = meta_info['roothash']
            file_checksum = self.factory.checksum
            if meta_info['isWindows']:
                filename = meta_info['filename'].rsplit('\\')[-1]
            else:
                filename = os.path.basename(meta_info['filename'])
            filepath = os.path.join(self.factory.download_folder, filename)
            # compare leader sent root hash and peer sent root hash
            if self.factory.roothash == meta_info['roothash']:
                client_response['isFile'] = True
                client_response['filename'] = filepath
                client_response['filesize'] = filesize
                client_response['checksum'] = file_checksum
                self.bake_client_message(client_response)
                self.init_file(
                    filepath,
                    filesize,
                    file_checksum,
                    self.factory.roothash)
        else:
            seeder_directory_root = meta_info['rootDirectory']
            is_windows = meta_info['isWindows']
            if not is_windows:
                client_directory_root = os.path.join(
                    self.factory.download_folder,
                    os.path.basename(seeder_directory_root))
            else:
                seeder_directory_root_basepath = seeder_directory_root.rsplit(
                    '\\')[-1]
                client_directory_root = os.path.join(
                    self.factory.download_folder,
                    seeder_directory_root_basepath)

            client_directory_root = os.path.realpath(client_directory_root)
            # this list contains (final pathnames of files with respect to
            # client path, size, hash)
            client_files_to_create = []

            if not os.path.isdir(client_directory_root):
                os.mkdir(client_directory_root)

            client_response['isFile'] = False
            client_response['rootDirectory'] = client_directory_root
            client_response['rootDirectoryChecksum'] = self.factory.checksum
            client_response['files'] = []  # [(filename, size, checksum)]

            # contains [( dirpath, filename, size, file_hash, roothash)]
            files_list = meta_info['files']
            for file_property in files_list:
                parent_path, filename, size, file_checksum, file_root_hash = file_property
                client_subdirectories_path = client_directory_root
                relative_subdirectory = parent_path[
                    len(seeder_directory_root):]
                if not is_windows:
                    subdirectories = relative_subdirectory.split(
                        '/')  # add windows support
                else:
                    subdirectories = relative_subdirectory.split(
                        '\\')  # add windows support
                for subdirectory in subdirectories:
                    client_directory_path = os.path.join(
                        client_subdirectories_path,
                        subdirectory)
                    if not os.path.isdir(client_directory_path):
                        os.mkdir(client_directory_path)
                    client_subdirectories_path = client_directory_path
                absolute_file_path = os.path.join(
                    client_subdirectories_path,
                    filename)
                client_files_to_create.append(
                    (absolute_file_path,
                     size,
                     file_checksum,
                     file_root_hash))
                client_response['files'].append(
                    (absolute_file_path, size, file_checksum))

            self.bake_client_message(client_response)

            for file_to_create in client_files_to_create:
                filename, size, file_checksum, file_root_hash = file_to_create
                self.init_file(filename, size, file_checksum, file_root_hash)

    def init_file(self, filepath, filesize, file_checksum, file_root_hash):
        # print 'must create this-> {0}'.format(filepath)
        file_handler = open(filepath, 'wb')
        file_handler.seek(
            (filesize * 1000.0 * 1000.0) - 1)
        file_handler.write('\0')
        file_handler.close()
        file_handler = open(filepath, 'r+b')
        reactor.connectTCP(
            self.factory.peers_list[0],
            SERVER_DAEMON_PORT,
            FileDownloadFactory(
                file_handler=file_handler,
                file_size=filesize,
                file_checksum=file_checksum,
                file_root_hash=file_root_hash,
                peers_list=self.factory.peers_list))


class DownloadManagerFactory(ClientFactory):
    protocol = DownloadManagerProtocol

    def __init__(
            self,
            clientConn,
            download_folder,
            checksum,
            roothash,
            peers_list,
            dbpool):
        self.client_connection = clientConn
        self.peers_list = peers_list
        self.download_folder = download_folder
        self.checksum = checksum
        self.roothash = roothash
        self.dbpool = dbpool

    def startedConnecting(self, connector):
        pass

    def clientConnectionFailed(self, connector, reason):
        self.peers_list.remove(connector.host)
        if len(self.peers_list) != 0:
            print 'Failed connecting to:{0} for the reason: {1}'.format(connector.host, reason)
            peer = self.peers_list[0]
            connector.host = peer  # maybe you have to do self.connector
            connector.connect()
        else:
            print 'Failed completely and reason: {0}'.format(reason)

    def clientConnectionLost(self, connector, reason):
        print reason

    def buildProtocol(self, addr):
        return DownloadManagerProtocol(self)

# class RemotepeerProtocol(BaseProtocol):
#
#     '''
#         Used for peer to peer download
#     '''
#
#     def __init__(self, factory):
#         self.buff = ''
#         self.delimiter = '\r'
#         self.file_buffer_delimiter = r'\r'
#         self.factory = factory
#         self.file_len_recv = 0.0
#         self.special_handler = None
#         self.requestPieceNumber = 0
#         self._file_buffer = b""
#         self._unprocessed = b""
#         self.send_format = "!I"
#         self.receive_format = "!II"
#         self.prefixLength = calcsize(self.receive_format)
#         self.chunk_number = None
#         self.length = None
#         self._complete_chunk_received = True
#         self.events = {
#             FILE_CONFIRMATION_MESSAGE: self.verify_pieces,
#             UNCHOKE: self.start_transfer
#         }
#         self.size_received = 0
#
#     def connectionMade(self):
#         update_msg = bake(
#             INTERESTED,
#             filehash=self.factory.file_details['checksum'])
#         self.sendLine(update_msg)
#
#     def serviceMessage(self, data):
#         key, value = unbake(message=data)
#         self.events[key](value)
#
#     def verify_pieces(self, data):
#         print '@initiate request {0}'.format(data)
#         piecehashes = data['piecehashes']
#         hasher = hashlib.md5()
#         hasher.update(piecehashes)
#         if hasher.hexdigest() == self.factory.file_details['file_root_hash']:
#             self.factory.file_details['pieceHashes'] = piecehashes
#             load_file_msg = bake(
#                 INIT_FILE_REQ,
#                 filehash=self.factory.file_details['checksum'])
#             self.sendLine(load_file_msg)
#
#     def start_transfer(self, data):
#         if data['unchoke']:
#             filename = os.path.basename(self.factory.file_details['file_name'])
#             filesize = self.factory.file_details['file_size']
#             msg_to_client = bake(
#                 FILE_TO_BE_DOWNLOADED,
#                 filename=filename,
#                 filesize=filesize)
#             print '****** iWanto Download {0} **********'.format(filename)
#             print 'Downloading to: {0}'.format(self.factory.path_to_write)
#             self.factory.clientConn.sendLine(msg_to_client)
#             self.factory.clientConn.transport.loseConnection()
#             self.hookHandler(self.rawDataReceived)
#             self.request_for_pieces(bootstrap=True)
#             self.factory.start_time = time.time()
#
#     def rawDataReceived(self, stream):
#         # all_data = self._unprocessed + stream
#         # currentOffset = 0
#         # prefixLength = self.prefixLength
#         # self._unprocessed = stream
#         hasher = hashlib.md5()
#         hasher.update(stream)
#         self.factory.file_container.write(stream)
#         self.size_received = self.size_received + len(stream)
#         self.factory.download_progress += 1
#         self.factory.bar.update(self.factory.download_progress)
#         print 'file size is {0} \n size received is {1}'.format(self.factory.file_details['file_size'] * 1000000, self.size_received)
#         if self.size_received >= self.factory.file_details[
#                 'file_size'] * 1000.0 * 1000.0:
#             print 'shit is done bro'
#             self.factory.file_container.close()
#
#     def request_for_pieces(self, bootstrap=False, endgame=False):
#         print 'requesting for pieces'
#         request_chunk_msg = bake(REQ_CHUNK, piece_data=1)
#         self.sendLine(request_chunk_msg)
#
#
# class RemotepeerFactory(Factory):
#
#     protocol = RemotepeerProtocol
#
#     def __init__(self, key, clientConn, download_folder, file_details, dbpool):
#         '''
#             :param key : string
#             :param checksum : string
#             :param clientConn : twisted connection object
#             :param download_folder : string
#
#         '''
#         self.dbpool = dbpool
#         self.number_of_peers = 0
#         self.download_progress = 0
#         self.clientConn = clientConn
#         self.download_folder = download_folder
#         self.file_details = file_details
#         self.hash_chunksize = 32
#         self.chunk_size = piece_size(self.file_details['file_size'])
#         self.number_of_pieces = int(
#             math.ceil(
#                 self.file_details['file_size'] *
#                 1000.0 *
#                 1000.0 /
#                 self.chunk_size))
#         self.bar = progressbar.ProgressBar(
#             maxval=self.number_of_pieces,
#             widgets=[
#                 progressbar.Bar(
#                     '=',
#                     '[',
#                     ']'),
#                 ' ',
#                 progressbar.Percentage(),
#                 ' ',
#                 progressbar.Timer()]).start()
#         self.path_to_write = os.path.join(
#             download_folder,
#             os.path.basename(
#                 self.file_details['file_name']))
#         self.request_queue = set(range(self.number_of_pieces))
#         self.super_set = set(range(self.number_of_pieces))
#         self.end_game_queue = set()
#         self.processed_queue = set()
#         self._is_new_file = False
#         x = fileHashUtils.check_hash_present_in_resume(
#             self.file_details['checksum'],
#             self.dbpool)
#         x.addCallback(self.initFile)
#
#     # @defer.inlineCallbacks
#     def initFile(self, resume=False):
#         print 'came to initFile and resume is set to {0}'.format(resume)
#         self.file_container = open(self.path_to_write, 'wb')
#         self.file_container.seek(
#             (self.file_details['file_size'] * 1000.0 * 1000.0) - 1)
#         self.file_container.write('\0')
#         self.file_container.close()
#         self.file_container = open(self.path_to_write, 'r+b')
#         self._is_new_file = True
#         # if not resume:
#         #     self.file_container = open(self.path_to_write, 'wb')
#         #     self.file_container.seek(
#         #         (self.file_details['file_size'] * 1000.0 * 1000.0) - 1)
#         #     self.file_container.write('\0')
#         #     self.file_container.close()
#         #     self.file_container = open(self.path_to_write, 'r+b')
#         #     self._is_new_file = True
#         # else:
#         #     piece_hashes = yield fileHashUtils.get_piecehashes_of(self.file_details['checksum'], self.dbpool)
#         #     with open(self.path_to_write, 'rb') as f:
#         #         for i, chunk in enumerate(
#         #             iter(
#         #                 lambda: f.read(
#         #                     self.chunk_size), b"")):
#         #             acha = hashlib.md5()
#         #             acha.update(chunk)
#         #             if acha.hexdigest() == piece_hashes[i * 32: (i * 32) + 32]:
#         #                 self.request_queue.remove(i)
#         #                 self.processed_queue.add(i)
#         #                 self.download_progress += 1
#         #     self.file_container = open(self.path_to_write, 'r+b')
#         #     self._is_new_file = False
#
#     def startedConnecting(self, connector):
#         pass
#
#     def clientConnectionLost(self, connector, reason):
#         self.number_of_peers -= 1
#         print 'Client lost connection coz of {0}'.format(reason)
#         if self.number_of_peers <= 0:
#             self.file_container.close()
#             print 'lost all the connections.. safely closing the file'
#
#     def clientConnectionFailed(self, connector, reason):
#         print reason.getErrorMessage()
#
#     def buildProtocol(self, addr):
#         self.number_of_peers += 1
#         return RemotepeerProtocol(self)
#
