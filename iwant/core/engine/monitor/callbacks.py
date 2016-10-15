from iwant.core.protocols import  FilemonitorClientFactory
from iwant.core.config import SERVER_DAEMON_HOST, SERVER_DAEMON_PORT
from twisted.internet import reactor

def filechangeCB(config_path):
    factory = FilemonitorClientFactory(config_path)
    reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, factory)

def fileindexedCB():
    factory = FilemonitorClientFactory(None)
    reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, factory)
