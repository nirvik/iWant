from iwant.core.protocols import FilemonitorClientFactory
from iwant.core.config import SERVER_DAEMON_HOST, SERVER_DAEMON_PORT
from twisted.internet import reactor
from iwant.core.constants import INDEXED, FILE_SYS_EVENT


def filechangeCB(updates):
    if len(updates['ADD']) != 0 or len(updates['DEL']) != 0:
        factory = FilemonitorClientFactory(FILE_SYS_EVENT, updates)
        reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, factory)


def fileindexedCB(files):
    factory = FilemonitorClientFactory(INDEXED, files)
    reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, factory)
