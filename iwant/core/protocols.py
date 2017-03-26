from twisted.internet.protocol import Protocol, ClientFactory, DatagramProtocol, Factory
from twisted.internet import defer
from engine.fileindexer.piece import piece_size
from messagebaker import Basemessage
from constants import FILE_SYS_EVENT, FILE_DETAILS_RESP, \
        LEADER, DEAD, FILE_TO_BE_DOWNLOADED, START_TRANSFER, INDEXED,\
        REQ_CHUNK, END_GAME, FILE_CONFIRMATION_MESSAGE, INIT_FILE_REQ,\
        INTERESTED, UNCHOKE
from iwant.core.engine.fileindexer import fileHashUtils
from engine.fileindexer.piece import piece_size
import ConfigParser
import os, sys
import progressbar
import pickle
import math
import hashlib
import random
import time
from struct import pack, unpack, calcsize

class BaseProtocol(Protocol):

    def __init__(self):
        self.special_handler = None

    def connectionMade(self):
        pass

    def sendLine(self, line):
        self.transport.write(str(line))

    def sendRaw(self, buffered):
        #buffered = buffered + r'\r'
        self.transport.write(buffered)

    def escape_dollar_sign(self, data):
        return data.replace(self.delimiter,'')

    def hookHandler(self, fn):
        self.special_handler = fn

    def unhookHandler(self):
        self.special_handler = None

    def dataReceived(self, data):
        if self.special_handler:
            self.special_handler(data)
        else:
            for char in data:
                self.buff+=char
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
        real_updates = self.factory.updates[1:]
        if len(real_updates)!=0:
            updated_msg = Basemessage(key=self.factory.event, data=self.factory.updates)
            self.transport.write(str(updated_msg))
            self.transport.loseConnection()

class FilemonitorClientFactory(ClientFactory):

    def __init__(self, event, updates):
        '''
            :param config_path : string
            config_path contains the .iwant directory path
        '''
        #self.config_path = config_path
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
        self.transport.write(str(msgObj), addr)

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
            update_msg = Basemessage(key=LEADER, data=(self.factory.leader_host, self.factory.leader_port))
        else:
            update_msg = Basemessage(key=DEAD, data=self.factory.dead_peer)
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
            #FILE_DETAILS_RESP: self.start_transfer,
            FILE_CONFIRMATION_MESSAGE : self.verify_pieces,
            UNCHOKE : self.start_transfer
        }


    def connectionMade(self):
        update_msg = Basemessage(key=INTERESTED, data=self.factory.file_details['checksum'])
        self.sendLine(update_msg)

    def serviceMessage(self, data):
        req = Basemessage(message=data)
        self.events[req.key](req.data)

    def verify_pieces(self, data):
        print '@initiate request {0}'.format(data)
        hasher = hashlib.md5()
        hasher.update(data)
        if hasher.hexdigest() == self.factory.file_details['file_root_hash']:
            if self.factory._is_new_file:
                self.factory.file_details['pieceHashes'] = data
                print 'the filename entered to resume is {0}'.format(self.factory.path_to_write)
                fileHashUtils.add_new_file_entry_resume((
                        self.factory.path_to_write,
                        0,
                        self.factory.file_details['file_size'],
                        self.factory.file_details['checksum'],
                        self.factory.file_details['pieceHashes'],
                        self.factory.file_details['file_root_hash']
                    ), self.factory.dbpool
                )
                self.factory._is_new_file = False
            self.factory.file_details['pieceHashes'] = data
            load_file_msg = Basemessage(key=INIT_FILE_REQ, data=self.factory.file_details['checksum'])
            self.sendLine(load_file_msg)

    def start_transfer(self, data):

        DOWNLOAD_FOLDER = self.factory.download_folder
        filename = os.path.basename(self.factory.file_details['file_name'])
        filesize = self.factory.file_details['file_size']
        msg_to_client = Basemessage(key=FILE_TO_BE_DOWNLOADED, data=(filename, filesize))
        print '****** iWanto Download {0} **********'.format(filename)
        print 'Downloading to: {0}'.format(self.factory.path_to_write)
        self.factory.clientConn.sendLine(msg_to_client)
        self.factory.clientConn.transport.loseConnection()
        self.hookHandler(self.rawDataReceived)
        self.request_for_pieces(bootstrap=True)
        self.factory.start_time = time.time()

    def rawDataReceived(self, data):
        all_data = self._unprocessed + data
        currentOffset = 0
        prefixLength = self.prefixLength
        self._unprocessed = all_data
        receive_format = self.receive_format

        while len(all_data) >= (currentOffset + prefixLength):
            messageStart = currentOffset + prefixLength
            if self._complete_chunk_received:
                self.length, self.chunk_number = unpack(receive_format, all_data[currentOffset: messageStart])
                messageEnd = messageStart + self.length
                currentOffset = messageEnd
                self._file_buffer = all_data[messageStart: messageEnd]
                if len(self._file_buffer) == self.length:
                    self.verify_and_write(self._file_buffer, self.chunk_number)
                else:
                    self._complete_chunk_received = False
            else:
                old_length = len(self._file_buffer)
                self._file_buffer += all_data[currentOffset : (self.length - old_length)]
                currentOffset = self.length - old_length
                if len(self._file_buffer) == self.length:
                    self.verify_and_write(self._file_buffer, self.chunk_number)
                    self._file_buffer = b""
                    self._complete_chunk_received = True
        self._unprocessed = all_data[currentOffset:]

    def verify_and_write(self, stream, chunk_number):
        if chunk_number not in self.factory.processed_queue:
            start = chunk_number * self.factory.hash_chunksize
            end = start + self.factory.hash_chunksize
            #verified_hash = self.factory.file_details['pieceHashes'][start: end]
            #hasher = hashlib.md5()
            #hasher.update(stream)
            #if hasher.hexdigest() == verified_hash:
            self.writeToFile(stream, chunk_number)
            #else:
            #    print 'we are fucked while receiving pieces {0} and \
            #            size is {1} and chunk size should be {2}'.format(chunk_number, len(stream),\
            #            self.factory.chunk_size)

            if len(self.factory.request_queue) > 0:
                self.request_for_pieces()
            else:
                if self.factory.super_set - self.factory.processed_queue:
                    remaining_pieces = self.factory.super_set - self.factory.processed_queue
                    #self.factory.request_queue.update(remaining_pieces)
                    self.factory.end_game_queue.update(remaining_pieces)
                    self.request_for_pieces(endgame=True)
                else:
                    self.factory.file_container.close()
                    self.factory.end_time = time.time()
                    self.stop_requesting_for_pieces()
                    print 'file written'
                    fileHashUtils.remove_resume_entry(self.factory.file_details['checksum'], self.factory.dbpool)

    def writeToFile(self, stream, chunk_number):
        seek_position = chunk_number * self.factory.chunk_size
        self.factory.file_container.seek(seek_position)
        self.factory.file_container.write(stream)
        self.factory.processed_queue.add(chunk_number)
        self.factory.download_progress += 1
        self.factory.bar.update(self.factory.download_progress)

    def request_for_pieces(self, bootstrap=False, endgame=False):
        #try:
        #    self.requestPieceNumber = self.factory.request_queue.pop()  # ask for 5 pieces in flight
        #    request_chunk_msg = Basemessage(key=REQ_CHUNK, data=(self.requestPieceNumber, self.factory.chunk_size))
        #    self.sendLine(request_chunk_msg)
        #except Exception as e:
        #    print 'file is already written'
        #    self.factory.file_container.close()
        #    self.transport.loseConnection()
        request_piece_numbers = self.generate_pieces(bootstrap, endgame)
        for i in request_piece_numbers:
            request_chunk_msg = Basemessage(key=REQ_CHUNK, data=pack(self.send_format, i))
            self.sendLine(request_chunk_msg)

    def generate_pieces(self, bootstrap=False, endgame=False):
        piece_list = []
        if bootstrap:
            number_of_pieces = 1
        else:
            number_of_pieces = 1
        for count in range(number_of_pieces):
            try:
                if not endgame:
                    piece_number = self.factory.request_queue.pop()
                else:
                    piece_number = self.factory.end_game_queue.pop()
                piece_list.append(piece_number)
            except:
                pass
        return piece_list

    def stop_requesting_for_pieces(self):
        stop_msg = Basemessage(key=END_GAME, data=None)
        self.sendLine(stop_msg)


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
        self.key = key
        self.clientConn = clientConn
        self.download_folder = download_folder
        self.file_details = file_details
        self.hash_chunksize = 32
        self.chunk_size = piece_size(self.file_details['file_size'])
        self.number_of_pieces = int(math.ceil(self.file_details['file_size'] * 1000.0 * 1000.0 / self.chunk_size))
        self.bar = progressbar.ProgressBar(maxval=self.number_of_pieces,\
                        widgets=[progressbar.Bar('=', '[', ']'), ' ',progressbar.Percentage(), ' ', progressbar.Timer()]).start()
        self.path_to_write = os.path.join(download_folder, os.path.basename(self.file_details['file_name']))
        self.request_queue = set(range(self.number_of_pieces))
        self.super_set = set(range(self.number_of_pieces))
        self.end_game_queue = set()
        self.processed_queue = set()
        self._is_new_file = False
        x = fileHashUtils.check_hash_present(self.file_details['checksum'], self.dbpool)
        x.addCallback(self.initFile)
        #self.initFile()

    @defer.inlineCallbacks
    def initFile(self, resume=False):
        print 'came to initFile and resume is set to {0}'.format(resume)
        if not resume:
            self.file_container = open(self.path_to_write, 'wb')
            self.file_container.seek((self.file_details['file_size'] * 1000.0 * 1000.0) - 1)
            self.file_container.write('\0')
            self.file_container.close()
            self.file_container = open(self.path_to_write, 'r+b')
            self._is_new_file = True
        else:
            piece_hashes = yield fileHashUtils.get_piecehashes_of(self.file_details['checksum'], self.dbpool)
            with open(self.path_to_write, 'rb') as f:
                for i, chunk in enumerate(iter(lambda : f.read(self.chunk_size), b"")):
                    acha = hashlib.md5()
                    acha.update(chunk)
                    if acha.hexdigest() == piece_hashes[i*32: (i*32)+32]:
                        self.request_queue.remove(i)
                        self.processed_queue.add(i)
                        self.download_progress+=1
            self.file_container = open(self.path_to_write, 'r+b')
            self._is_new_file = False

    def startedConnecting(self, connector):
        pass

    def clientConnectionLost(self, connector, reason):
        self.number_of_peers -= 1
        if self.number_of_peers <= 0:
            self.file_container.close()
            print 'lost all the connections.. safely closing the file'

    def clientConnectionFailed(self, connector, reason):
        print reason.getErrorMessage()

    def buildProtocol(self, addr):
        self.number_of_peers += 1
        return RemotepeerProtocol(self)
