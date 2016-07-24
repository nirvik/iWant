from twisted.internet import reactor,defer,threads
from twisted.internet.endpoints import TCP4ClientEndpoint,connectProtocol
from twisted.internet.protocol import ClientFactory
from communication.message import FlashMessage
from flashpointProtocol import FlashpointProtocol
import json

class HashListFiles(FlashpointProtocol):
    def connectionMade(self):
        reqMessage = FlashMessage(key=1,data=[])
        self.sendLine(reqMessage)

    def serviceMessage(self,data):
        print data
        if self.factory.state == 1:
            try:
                self.factory.FH = json.loads(data)
                print self.factory.FH
            except:
                raise NotImplementedError

class HashListFilesFactory(ClientFactory):
    protocol = HashListFiles
    def __init__(self):
        self.state = 1
        self.FH = {}
reactor.connectTCP('192.168.1.112',1234,HashListFilesFactory())
reactor.run()
