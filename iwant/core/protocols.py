from twisted.internet.protocol import Protocol, ClientFactory, DatagramProtocol, Factory
from messagebaker import Basemessage
from constants import FILE_SYS_EVENT, FILE_DETAILS_RESP, \
        LEADER, DEAD, FILE_TO_BE_DOWNLOADED, START_TRANSFER, INDEXED,\
        REQ_CHUNK, END_GAME
from engine.fileindexer.piece import piece_size
import ConfigParser
import os, sys
import progressbar
import pickle
import math
import hashlib
import random

class BaseProtocol(Protocol):

    def __init__(self):
        self.special_handler = None

    def connectionMade(self):
        pass

    def sendLine(self, line):
        self.transport.write(str(line))

    def sendRaw(self, buffered):
        buffered = buffered + r'\r'
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
        if self.factory.config_path:
            path = os.path.join(self.factory.config_path, '.hindex')
            with open(path) as f:
                dump = f.read()
            pd = pickle.loads(dump)
            updated_msg = Basemessage(key=FILE_SYS_EVENT, data=pd)
        else:
            updated_msg = Basemessage(key=INDEXED, data=None)
        self.transport.write(str(updated_msg))
        self.transport.loseConnection()


class FilemonitorClientFactory(ClientFactory):

    def __init__(self, config_path):
        '''
            :param config_path : string
            config_path contains the .iwant directory path
        '''
        self.config_path = config_path

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
        self.file_buffer = ''
        self.events = {
            FILE_DETAILS_RESP: self.start_transfer
        }

    def connectionMade(self):
        update_msg = Basemessage(key=self.factory.key, data=self.factory.file_details['checksum'])
        self.sendLine(update_msg)

    def serviceMessage(self, data):
        req = Basemessage(message=data)
        self.events[req.key](req.data)

    def start_transfer(self, data):

        DOWNLOAD_FOLDER = self.factory.download_folder
        msg_to_client = Basemessage(key=FILE_TO_BE_DOWNLOADED, data=data)
        filename = os.path.basename(data[0])
        print '****** iWanto Download {0} **********'.format(filename)
        print 'Downloading to: {0}'.format(os.path.join(DOWNLOAD_FOLDER\
                ,filename))
        self.factory.clientConn.sendLine(msg_to_client)
        self.factory.clientConn.transport.loseConnection()
        self.hookHandler(self.rawDataReceived)
        self.request_for_pieces()

    def rawDataReceived(self, data):
        # since we are increasing the chunk size , we need to keep buffering till the delimiter is added
        self.file_buffer += data
        if data[-1] == self.file_buffer_delimiter:
            print 'oh yeah'
            stream, _ = self.file_buffer.rsplit(self.file_buffer_delimiter, 1)
            self._process(stream)
            self.file_buffer = ''

    def _process(self, stream):
        start = int(self.requestPieceNumber * self.factory.hash_chunksize)
        end = int(start + self.factory.hash_chunksize)
        verified_hash = self.factory.file_details['pieceHashes'][start:end]
        hasher = hashlib.md5()
        #hasher.update(stream)
        # if verified_hash == hasher.hexdigest()
        self.writeToFile(stream)
        print 'Progress {0}% and #Pieces {1}'.format(self.factory.download_progress * 100.0/ self.factory.file_details['numberOfPieces'], self.factory.file_details['numberOfPieces'])
        if len(self.factory.processed_pieces) == self.factory.file_details['numberOfPieces']:
            self.factory.file_container.close()
            self.stop_requesting_for_pieces()
        else:
            self.request_for_pieces()

    def writeToFile(self, stream):
        seek_position = int(self.requestPieceNumber * self.factory.chunk_size)
        self.factory.file_container.seek(seek_position)
        self.factory.file_container.write(stream)
        self.factory.processed_pieces.append(self.requestPieceNumber)
        self.factory.download_progress += 1

    def request_for_pieces(self):
        try:
            self.requestPieceNumber = self.factory.request_queue.pop()
            request_chunk_msg = Basemessage(key=REQ_CHUNK, data=self.requestPieceNumber)
            self.sendLine(request_chunk_msg)
        except Exception as e:
            print e
            print 'the request queue is empty. handle this later'

    def stop_requesting_for_pieces(self):
        stop_msg = Basemessage(key=END_GAME, data=None)
        self.sendLine(stop_msg)

    def write_to_file(self, data):
        self.file_len_recv += len(data)
        self.factory.bar.update(self.file_len_recv)
        self.factory.file_container.write(data)
        if self.file_len_recv >= self.factory.file_details['file_size']:
            self.factory.bar.finish()
            self.factory.file_container.close()
            print '{0} downloaded'.format(os.path.basename(self.factory.file_details['file_name']))
            self.transport.loseConnection()


class RemotepeerFactory(Factory):

    protocol = RemotepeerProtocol

    def __init__(self, key, clientConn, download_folder, file_details):
        '''
            :param key : string
            :param checksum : string
            :param clientConn : twisted connection object
            :param download_folder : string

        '''
        self.key = key
        self.clientConn = clientConn
        self.download_folder = download_folder
        self.file_details = file_details
        self.hash_chunksize = 32.0  # length of hash is 32
        self.chunk_size = piece_size(self.file_details['file_size'])
        self.file_details['numberOfPieces'] = math.ceil(self.file_details['file_size'] * 1000.0 * 1000.0 / self.chunk_size)
        self.file_details['lastPieceSize'] = (self.file_details['file_size'] * 1000.0 * 1000.0) - (self.chunk_size * (self.file_details['numberOfPieces'] -1))
        self.bar = progressbar.ProgressBar(maxval=self.file_details['file_size'],\
                        widgets=[progressbar.Bar('=', '[', ']'), ' ',progressbar.Percentage()]).start()
        self.path_to_write = os.path.join(download_folder, os.path.basename(self.file_details['file_name']))
        self.file_container = open(self.path_to_write, 'wb')
        self.request_queue = range(int(self.file_details['numberOfPieces']))
        random.shuffle(self.request_queue)
        self.processed_pieces = []
        self.download_progress = 0
        self.initFile()

    def initFile(self):
        self.file_container.seek(self.file_details['file_size'] * 1000.0 * 1000.0)
        self.file_container.write('\0')
        self.file_container.close()
        self.file_container = open(self.path_to_write, 'r+b')

    def startedConnecting(self, connector):
        pass

    def clientConnectionLost(self, connector, reason):
        pass

    def clientConnectionFailed(self, connector, reason):
        print reason.getErrorMessage()

    def buildProtocol(self, addr):
        return RemotepeerProtocol(self)
