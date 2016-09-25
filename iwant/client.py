from twisted.internet import reactor,defer,threads
from twisted.internet.endpoints import TCP4ClientEndpoint,connectProtocol
from twisted.internet.protocol import ClientFactory
from iwant.communication.message import P2PMessage
from iwant.protocols import BaseProtocol
from iwant.constants.events.server import HANDSHAKE, LIST_ALL_FILES, SEARCH_REQ, SEARCH_RES, LEADER_NOT_READY, IWANT_PEER_FILE, PEER_LOOKUP_RESPONSE, IWANT, INIT_FILE_REQ, FILE_DETAILS_RESP, FILE_TO_BE_DOWNLOADED
import pickle
import json
import tabulate

class Frontend(BaseProtocol):

    def __init__(self, factory):
        self.factory = factory
        self.special_handler = None
        self.events = {
            HANDSHAKE : self.handshake,
            LIST_ALL_FILES : self.listAll,
            SEARCH_RES : self.show_search_results,
            LEADER_NOT_READY : self.leader_not_ready,
            PEER_LOOKUP_RESPONSE : self.ask_for_file_details,
            FILE_DETAILS_RESP : self.download_file,
            FILE_TO_BE_DOWNLOADED : self.show_file_to_be_downloaded
        }
        self.buff = ''
        self.delimiter = '#'

    def connectionMade(self):
        print 'Conecction made\n'
        reqMessage = P2PMessage(key=self.factory.query, data=self.factory.arguments)
        self.sendLine(reqMessage)
        if self.factory.query == IWANT_PEER_FILE:
            pass
            #reactor.stop()

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

    def show_search_results(self, data):
        print tabulate.tabulate(data, headers=["Filename", "Checksum", "Size"])
        reactor.stop()

    def leader_not_ready(self):
        print 'Tracker not available..'
        reactor.stop()

    def ask_for_file_details(self, data):
        print 'Got peers addresses {0}'.format(data)
        host, port = data[0]  # got list of peers
        #self.transport.loseConnection()  # drop connection with local server
        #self.factory.connectPeer(host, port)
        #reactor.connectTCP(host, port, FrontendFactory(INIT_FILE_REQ, data=self.factory.arguments))

    def download_file(self, data):
        print data
        reactor.stop()

    def show_file_to_be_downloaded(self, data):
        #print tabulate.tabulate(data)
        print data
        reactor.stop()

class FrontendFactory(ClientFactory):
    def __init__(self, query, data=None, downloadfolder=None):
        self.state = 1
        self.FH = {}
        self.query  = query
        self.arguments = data
        self.download_folder = downloadfolder

    def startedConnecting(self, connector):
        print 'started connecting'

    def clientConnectionFailed(self, connector, reason):
        print reason
        reactor.stop()

    #def connectPeer(self, host, port):
    #    reactor.connectTCP(host, port, RemotepeerFactory(INIT_FILE_REQ, dump=self.arguments))

    def buildProtocol(self, addr):
        return Frontend(self)


if __name__ == '__main__':
    reactor.connectTCP('127.0.0.1',1234, FrontendFactory())
    try:
        reactor.run()
    except KeyboardInterrupt:
        print 'stopping reactor'
        reactor.stop()
