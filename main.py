from iwant.consensus.beacon import *
from iwant.server import *
from iwant.watching import *
from twisted.internet import reactor
import os, sys
from netifaces import interfaces, ifaddresses, AF_INET
import time_uuid
from iwant.config import SERVER_DAEMON_HOST, SERVER_DAEMON_PORT
from iwant.constants.election_constants import MCAST_IP, MCAST_PORT
import pickle

try:
    def callback():
        from twisted.internet.protocol import Protocol, ClientFactory
        from twisted.internet import reactor
        from iwant.constants.server_event_constants import FILE_SYS_EVENT

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

        factory = FilemonitorClientFactory()
        reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, factory)

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
    folder = '/run/media/nirvik/Data/SamuraiJack'
    timeuuid = time_uuid.TimeUUID.with_utcnow()
    book = CommonlogBook(identity=timeuuid, state=0, ip = ips[ip-1])
    reactor.listenMulticast(MCAST_ADDR[1], CommonroomProtocol(book), listenMultiple=True)
    endpoints.serverFromString(reactor, 'tcp:{0}'.format(SERVER_DAEMON_PORT)).listen(backendFactory(folder, book))
    ScanFolder(folder, callback)
    reactor.run()
except KeyboardInterrupt:
        observer.stop()
        reactor.stop()
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
