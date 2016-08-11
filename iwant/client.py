from twisted.internet import reactor,defer,threads
from twisted.internet.endpoints import TCP4ClientEndpoint,connectProtocol
from twisted.internet.protocol import ClientFactory
from iwant.communication.message import P2PMessage
from iwant.flashpointProtocol import FlashpointProtocol
from iwant.constants.server_event_constants import HANDSHAKE, LIST_ALL_FILES, SEARCH_REQ, SEARCH_RES
import pickle
import json

class Frontend(FlashpointProtocol):

    def __init__(self, factory):
        self.factory = factory
        self.events = {
            HANDSHAKE : self.handshake,
            LIST_ALL_FILES : self.listAll,
            SEARCH_RES : self.search_results
        }
        self.buff = ''
        self.delimiter = '#'

    def connectionMade(self):
        reqMessage = P2PMessage(key=self.factory.query, data=self.factory.arguments)
        self.sendLine(reqMessage)

    def serviceMessage(self, data):
        req = P2PMessage(message=data)
        try:
            self.events[req.key]()
        except:
            self.events[req.key](req.data)

    def handshake(self):
        req = P2PMessage(key=LIST_ALL_FILES,data=None)
        self.sendLine(req)

    def listAll(self, data):
        print data
        print 'stopping reactor'
        reactor.stop()

    def search_results(self, data):
        for val,score in data:
            print val,score
        reactor.stop()

class FrontendFactory(ClientFactory):
    def __init__(self, query, data):
        self.state = 1
        self.FH = {}
        self.query  = query
        self.arguments = data

    def buildProtocol(self, addr):
        return Frontend(self)


if __name__ == '__main__':
    reactor.connectTCP('127.0.0.1',1234, FrontendFactory())
    try:
        reactor.run()
    except KeyboardInterrupt:
        print 'stopping reactor'
        reactor.stop()
