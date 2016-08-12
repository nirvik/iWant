from twisted.internet.protocol import Protocol, ClientFactory, DatagramProtocol
from iwant.communication.message import P2PMessage
from iwant.constants.server_event_constants import FILE_SYS_EVENT

class BaseProtocol(Protocol):

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
        for char in data:
            self.buff+=char
            if char == self.delimiter:
                request_str = self.escape_dollar_sign(self.buff)
                self.buff = ''
                self.serviceMessage(request_str)
        self.buff = ''

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
