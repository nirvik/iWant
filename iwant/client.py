from twisted.internet import reactor,defer,threads
from twisted.internet.endpoints import TCP4ClientEndpoint,connectProtocol
from twisted.internet.protocol import ClientFactory
from communication.message import P2PMessage
from flashpointProtocol import FlashpointProtocol
import pickle
import json

class HashListFiles(FlashpointProtocol):

    def __init__(self):
        self.events = {
            'handshake' : self.handshake,
            'listAll' : self.listAll
        }
        self.buff = ''
        self.delimiter = '#'

    def connectionMade(self):
        reqMessage = P2PMessage(key='handshake', data=None)
        self.sendLine(reqMessage)

    def serviceMessage(self, data):
        msg = P2PMessage(message=data)
        if msg.key == 'handshake':
            self.events[msg.key]()
        else:
            self.events[msg.key](msg.data)

    def handshake(self):
        req = P2PMessage(key='listAll',data=None)
        self.sendLine(req)

    def listAll(self, data):
        print data
        print 'stopping reactor'
        reactor.stop()

class HashListFilesFactory(ClientFactory):
    protocol = HashListFiles
    def __init__(self):
        self.state = 1
        self.FH = {}


reactor.connectTCP('127.0.0.1',1234,HashListFilesFactory())
try:
    reactor.run()
except KeyboardInterrupt:
    print 'stopping reactor'
    reactor.stop()
