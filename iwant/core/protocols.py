from twisted.internet.protocol import Protocol, ClientFactory, DatagramProtocol, Factory
from twisted.internet import defer
from engine.fileindexer.piece import piece_size
from messagebaker import bake, unbake
from constants import LEADER, PEER_DEAD, FILE_TO_BE_DOWNLOADED,\
    REQ_CHUNK, END_GAME, FILE_CONFIRMATION_MESSAGE, INIT_FILE_REQ,\
    INTERESTED, UNCHOKE
from iwant.core.engine.fileindexer import fileHashUtils
import os
import progressbar
import math
import hashlib
import time
from struct import calcsize


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
        print self.factory.updates['ADD']
        print self.factory.updates['DEL']
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


class RemotepeerProtocol(BaseProtocol):

    '''
        Used for peer to peer download
    '''

    def __init__(self, factory):
        self.buff = ''
        self.delimiter = '\r'
        self.file_buffer_delimiter = r'\r'
        self.factory = factory
        self.file_len_recv = 0.0
        self.special_handler = None
        self.requestPieceNumber = 0
        self._file_buffer = b""
        self._unprocessed = b""
        self.send_format = "!I"
        self.receive_format = "!II"
        self.prefixLength = calcsize(self.receive_format)
        self.chunk_number = None
        self.length = None
        self._complete_chunk_received = True
        self.events = {
            FILE_CONFIRMATION_MESSAGE: self.verify_pieces,
            UNCHOKE: self.start_transfer
        }
        self.size_received = 0

    def connectionMade(self):
        update_msg = bake(
            INTERESTED,
            filehash=self.factory.file_details['checksum'])
        self.sendLine(update_msg)

    def serviceMessage(self, data):
        key, value = unbake(message=data)
        self.events[key](value)

    def verify_pieces(self, data):
        print '@initiate request {0}'.format(data)
        piecehashes = data['piecehashes']
        hasher = hashlib.md5()
        hasher.update(piecehashes)
        if hasher.hexdigest() == self.factory.file_details['file_root_hash']:
            self.factory.file_details['pieceHashes'] = piecehashes
            load_file_msg = bake(
                INIT_FILE_REQ,
                filehash=self.factory.file_details['checksum'])
            self.sendLine(load_file_msg)

    def start_transfer(self, data):
        if data['unchoke']:
            filename = os.path.basename(self.factory.file_details['file_name'])
            filesize = self.factory.file_details['file_size']
            msg_to_client = bake(
                FILE_TO_BE_DOWNLOADED,
                filename=filename,
                filesize=filesize)
            print '****** iWanto Download {0} **********'.format(filename)
            print 'Downloading to: {0}'.format(self.factory.path_to_write)
            self.factory.clientConn.sendLine(msg_to_client)
            self.factory.clientConn.transport.loseConnection()
            self.hookHandler(self.rawDataReceived)
            self.request_for_pieces(bootstrap=True)
            self.factory.start_time = time.time()

    def rawDataReceived(self, stream):
        # all_data = self._unprocessed + stream
        # currentOffset = 0
        # prefixLength = self.prefixLength
        # self._unprocessed = stream
        hasher = hashlib.md5()
        hasher.update(stream)
        self.factory.file_container.write(stream)
        self.size_received = self.size_received + len(stream)
        self.factory.download_progress += 1
        self.factory.bar.update(self.factory.download_progress)
        print 'file size is {0} \n size received is {1}'.format(self.factory.file_details['file_size'] * 1000000, self.size_received)
        if self.size_received >= self.factory.file_details['file_size'] * 1000.0 * 1000.0:
            print 'shit is done bro'
            self.factory.file_container.close()


    def request_for_pieces(self, bootstrap=False, endgame=False):
        print 'requesting for pieces'
        request_chunk_msg = bake(REQ_CHUNK, piece_data=1)
        self.sendLine(request_chunk_msg)

class RemotepeerFactory(Factory):

    protocol = RemotepeerProtocol

    def __init__(self, key, clientConn, download_folder, file_details, dbpool):
        '''
            :param key : string
            :param checksum : string
            :param clientConn : twisted connection object
            :param download_folder : string

        '''
        self.dbpool = dbpool
        self.number_of_peers = 0
        self.download_progress = 0
        self.clientConn = clientConn
        self.download_folder = download_folder
        self.file_details = file_details
        self.hash_chunksize = 32
        self.chunk_size = piece_size(self.file_details['file_size'])
        self.number_of_pieces = int(
            math.ceil(
                self.file_details['file_size'] *
                1000.0 *
                1000.0 /
                self.chunk_size))
        self.bar = progressbar.ProgressBar(
            maxval=self.number_of_pieces,
            widgets=[
                progressbar.Bar(
                    '=',
                    '[',
                    ']'),
                ' ',
                progressbar.Percentage(),
                ' ',
                progressbar.Timer()]).start()
        self.path_to_write = os.path.join(
            download_folder,
            os.path.basename(
                self.file_details['file_name']))
        self.request_queue = set(range(self.number_of_pieces))
        self.super_set = set(range(self.number_of_pieces))
        self.end_game_queue = set()
        self.processed_queue = set()
        self._is_new_file = False
        x = fileHashUtils.check_hash_present_in_resume(
            self.file_details['checksum'],
            self.dbpool)
        x.addCallback(self.initFile)

    # @defer.inlineCallbacks
    def initFile(self, resume=False):
        print 'came to initFile and resume is set to {0}'.format(resume)
        self.file_container = open(self.path_to_write, 'wb')
        self.file_container.seek(
            (self.file_details['file_size'] * 1000.0 * 1000.0) - 1)
        self.file_container.write('\0')
        self.file_container.close()
        self.file_container = open(self.path_to_write, 'r+b')
        self._is_new_file = True
        # if not resume:
        #     self.file_container = open(self.path_to_write, 'wb')
        #     self.file_container.seek(
        #         (self.file_details['file_size'] * 1000.0 * 1000.0) - 1)
        #     self.file_container.write('\0')
        #     self.file_container.close()
        #     self.file_container = open(self.path_to_write, 'r+b')
        #     self._is_new_file = True
        # else:
        #     piece_hashes = yield fileHashUtils.get_piecehashes_of(self.file_details['checksum'], self.dbpool)
        #     with open(self.path_to_write, 'rb') as f:
        #         for i, chunk in enumerate(
        #             iter(
        #                 lambda: f.read(
        #                     self.chunk_size), b"")):
        #             acha = hashlib.md5()
        #             acha.update(chunk)
        #             if acha.hexdigest() == piece_hashes[i * 32: (i * 32) + 32]:
        #                 self.request_queue.remove(i)
        #                 self.processed_queue.add(i)
        #                 self.download_progress += 1
        #     self.file_container = open(self.path_to_write, 'r+b')
        #     self._is_new_file = False

    def startedConnecting(self, connector):
        pass

    def clientConnectionLost(self, connector, reason):
        self.number_of_peers -= 1
        print 'Client lost connection coz of {0}'.format(reason)
        if self.number_of_peers <= 0:
            self.file_container.close()
            print 'lost all the connections.. safely closing the file'

    def clientConnectionFailed(self, connector, reason):
        print reason.getErrorMessage()

    def buildProtocol(self, addr):
        self.number_of_peers += 1
        return RemotepeerProtocol(self)
