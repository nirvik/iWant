from twisted.internet.protocol import Protocol, ClientFactory, DatagramProtocol, Factory
from iwant.communication.message import P2PMessage
from iwant.constants.events.server import *
from iwant.constants.events.election import *
from iwant.config import DOWNLOAD_FOLDER
import os


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
            #self.buff = ''

    def serviceMessage(self,message):
        pass


class FilemonitorClientProtocol(Protocol):
    def connectionMade(self):
        with open('/var/log/iwant/.hindex') as f:
            dump = f.read()
        pd = pickle.loads(dump)
        updated_msg = P2PMessage(key=FILE_SYS_EVENT, data=pd)
        self.transport.write(str(updated_msg))
        self.transport.loseConnection()


class FilemonitorClientFactory(ClientFactory):
    def buildProtocol(self, addr):
        return FilemonitorClientProtocol()


class PeerdiscoveryProtocol(DatagramProtocol):
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
    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        #print 'connection made'
        update_msg = P2PMessage(key=LEADER, data=(self.factory.leader_host, self.factory.leader_port))
        self.transport.write(str(update_msg))
        self.transport.loseConnection()


class ServerElectionFactory(ClientFactory):
    def __init__(self, leader_host, leader_port):
        self.leader_host = leader_host
        self.leader_port = leader_port

    def buildProtocol(self, addr):
        return ServerElectionProtocol(self)

#class ServerLeaderProtocol(BaseProtocol):
#    def __init__(self, factory):
#        self.buff = ''
#        self.delimiter = '#'
#        self.factory = factory
#
#    def connectionMade(self):
#        update_msg = P2PMessage(key=self.factory.key, data=self.factory.dump)
#        self.transport.write(str(update_msg))
#        if not persist:
#            self.transport.loseConnection()
#        else:
#            print 'persistent connection'
#
#    def serviceMessage(self, data):
#        print 'Sending this to client using the transport object'
#        update_msg = P2PMessage(message=data)
#        update_msg = P2PMessage(key=update_msg.key, data=update_msg.data)
#        clientConn.sendLine(update_msg)
#        clientConn.transport.loseConnection()
#
#class ServerLeaderFactory(ClientFactory):
#    def __init__(self, key, dump):
#        self.key = key
#        self.dump = dump
#
#    def buildProtocol(self, addr):
#        return ServerLeaderProtocol(self)


class RemotepeerProtocol(BaseProtocol):
    def __init__(self, factory):
        self.buff = ''
        self.delimiter = '#'
        self.factory = factory
        self.file_len_recv = 0.0
        self.special_handler = None
        self.events = {
            FILE_DETAILS_RESP: self.start_transfer
        }

    def connectionMade(self):
        update_msg = P2PMessage(key=self.factory.key, data=self.factory.dump)
        self.sendLine(update_msg)

    def serviceMessage(self, data):
        print 'got response from server about file'
        req = P2PMessage(message=data)
        self.events[req.key](req.data)

    def start_transfer(self, data):
        update_msg = P2PMessage(key=FILE_TO_BE_DOWNLOADED, data=data)
        self.factory.file_details['fname'] = data[0]
        self.factory.file_details['size'] = data[1] * 1024.0 * 1024.0
        if not os.path.exists(DOWNLOAD_FOLDER):
            os.mkdir(DOWNLOAD_FOLDER)
        self.factory.file_container = open(DOWNLOAD_FOLDER+os.path.basename(data[0]), 'wb')
        self.factory.clientConn.sendLine(update_msg)
        self.factory.clientConn.transport.loseConnection()
        self.hookHandler(self.write_to_file)
        print 'Start Trasnfer {0}'.format(self.factory.dump)
        update_msg = P2PMessage(key=START_TRANSFER, data=self.factory.dump)
        self.sendLine(update_msg)

    def write_to_file(self, data):
        self.file_len_recv += len(data)
        self.factory.file_container.write(data)
        if self.file_len_recv >= self.factory.file_details['size']:
            self.factory.file_container.close()
            print 'Client : File downloaded'
            self.transport.loseConnection()


class RemotepeerFactory(Factory):

    protocol = RemotepeerProtocol

    def __init__(self, key, checksum, clientConn):
        self.key = key
        self.dump = checksum
        self.clientConn = clientConn
        self.file_details = {'checksum': checksum}
        self.file_container = None

    def startedConnecting(self, connector):
        print 'connecting'

    def clientConnectionLost(self, connector, reason):
        print reason

    def clientConnectionFailed(self, connector, reason):
        print reason.getErrorMessage()

    def buildProtocol(self, addr):
        return RemotepeerProtocol(self)
