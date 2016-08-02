from iwant.consensus.beacon import *
from iwant.server import *
from iwant.watching import *
from twisted.internet import reactor
import os, sys
from netifaces import interfaces, ifaddresses, AF_INET
import time_uuid
try:
    def callback():
        from twisted.internet.protocol import Protocol, ClientFactory
        from twisted.internet import reactor
        class SomeClientProtocol(Protocol):
            def connectionMade(self):
                updated_msg = P2PMessage(key='filesys_modified')
                self.transport.write(str(updated_msg))
                self.transport.loseConnection()

        class SomeClientFactory(ClientFactory):
            def buildProtocol(self, addr):
                return SomeClientProtocol()

        factory = SomeClientFactory()
        reactor.connectTCP('127.0.0.1', 1235, factory)

    def ip4_addresses():
        ip_list = []
        for interface in interfaces():
            try:
                for link in ifaddresses(interface)[AF_INET]:
                    ip_list.append(link['addr'])
            except:
                pass
        return ip_list
    ips = ip4_addresses()
    print ips
    ip = input('Enter index of ip addr:')
    folder = '/home/nirvik/Pictures'
    timeuuid = time_uuid.TimeUUID.with_utcnow()
    book = CommonlogBook(identity=timeuuid, state=0, ip = ips[ip-1])
    eventRegister = EventHooker()
    reactor.listenMulticast(MCAST_ADDR[1], CommonroomProtocol(book,eventRegister), listenMultiple=True)
    endpoints.serverFromString(reactor, 'tcp:1235').listen(backendFactory('/home/nirvik/Pictures'))
    ScanFolder(folder, callback)
    reactor.run()
except KeyboardInterrupt:
        observer.stop()
        reactor.stop()
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
