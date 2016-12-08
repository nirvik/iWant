from twisted.internet.protocol import Protocol, ClientFactory, DatagramProtocol, Factory
from messagebaker import Basemessage
from constants import FILE_SYS_EVENT, FILE_DETAILS_RESP, \
        LEADER, DEAD, FILE_TO_BE_DOWNLOADED, START_TRANSFER, INDEXED
import ConfigParser
import os, sys
import progressbar
import pickle


class BaseProtocol(Protocol):

    def __init__(self):
        self.special_handler = None

    def connectionMade(self):
        pass

    def sendLine(self,line):
        self.transport.write(str(line))

    def escape_dollar_sign(self,data):
        return data.replace(self.delimiter,'')

    def hookHandler(self,fn):
        self.special_handler = fn

    def unhookHandler(self):
        self.special_handler = None

    def dataReceived(self,data):
        if self.special_handler:
            self.special_handler(data)
        else:
            for char in data:
                self.buff+=char
                if char == self.delimiter:
                    request_str = self.escape_dollar_sign(self.buff)
                    self.buff = ''
                    self.serviceMessage(request_str)

    def serviceMessage(self,message):
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
        self.factory = factory
        self.file_len_recv = 0.0
        self.special_handler = None
        self.events = {
            FILE_DETAILS_RESP: self.start_transfer
        }

    def connectionMade(self):
        update_msg = Basemessage(key=self.factory.key, data=self.factory.dump)
        self.sendLine(update_msg)

    def serviceMessage(self, data):
        # print 'got response from server about file'
        req = Basemessage(message=data)
        self.events[req.key](req.data)

    def start_transfer(self, data):

        DOWNLOAD_FOLDER = self.factory.download_folder
        update_msg = Basemessage(key=FILE_TO_BE_DOWNLOADED, data=data)
        self.factory.file_details['fname'] = data[0]
        self.factory.file_details['size'] = data[1] * 1024.0 * 1024.0

        filename = os.path.basename(data[0])
        print '****** iWanto Download {0} **********'.format(filename)
        self.factory.file_container = open(os.path.join(DOWNLOAD_FOLDER,\
                filename), 'wb')
        print 'Downloading to: {0}'.format(os.path.join(DOWNLOAD_FOLDER\
                , filename))
        self.factory.clientConn.sendLine(update_msg)
        self.factory.clientConn.transport.loseConnection()
        self.hookHandler(self.write_to_file)
        update_msg = Basemessage(key=START_TRANSFER, data=self.factory.dump)
        self.bar = progressbar.ProgressBar(maxval=self.factory.file_details['size'],\
                        widgets=[progressbar.Bar('=', '[', ']'), ' ',progressbar.Percentage()]).start()
        self.sendLine(update_msg)

    def write_to_file(self, data):
        self.file_len_recv += len(data)
        self.bar.update(self.file_len_recv)
        self.factory.file_container.write(data)
        if self.file_len_recv >= self.factory.file_details['size']:
            self.bar.finish()
            self.factory.file_container.close()
            print '{0} downloaded'.format(os.path.basename(self.factory.file_details['fname']))
            self.transport.loseConnection()


class RemotepeerFactory(Factory):

    protocol = RemotepeerProtocol

    def __init__(self, key, checksum, clientConn, download_folder):
        '''
            :param key : string
            :param checksum : string
            :param clientConn : twisted connection object
            :param download_folder : string

        '''
        self.key = key
        self.dump = checksum
        self.clientConn = clientConn
        self.download_folder = download_folder
        self.file_details = {'checksum': checksum}
        self.file_container = None

    def startedConnecting(self, connector):
        print 'connecting'

    def clientConnectionLost(self, connector, reason):
        pass

    def clientConnectionFailed(self, connector, reason):
        print reason.getErrorMessage()

    def buildProtocol(self, addr):
        return RemotepeerProtocol(self)
