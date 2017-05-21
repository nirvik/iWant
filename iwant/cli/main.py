"""iWant.

Usage:
    iwanto start
    iwanto search <name>
    iwanto download <hash> [(to <destination>)]
    iwanto share <path>
    iwanto change download path to <destination>
    iwanto --version

Options:
    -h --help                                   Show this screen.
    --version                                   Show version.
    start                                       This starts the iwant server in your system
    search <name>                               Discovering files in the network. Example: iwanto search batman
    download <hash>                             Downloads the file from the network
    share <path>                                Change your shared folder
    change download path to <destination>       Change download folder


"""
import os
import sys
import sqlite3
from docopt import docopt
from twisted.python import log
from twisted.enterprise import adbapi
from iwant.core.exception import MainException
from iwant.core.engine.consensus.beacon import CommonroomProtocol
from iwant.core.engine.server import backendFactory
from iwant.core.engine.monitor.watching import ScanFolder
from iwant.core.config import SERVER_DAEMON_HOST,\
    SERVER_DAEMON_PORT, MCAST_PORT
from iwant.core.engine.monitor.callbacks import filechangeCB,\
    fileindexedCB
from iwant.core.engine.identity import CommonlogBook
from iwant.core.engine.fileindexer import fileHashUtils
from twisted.internet import reactor, endpoints
from iwant.core.engine.client import FrontendFactory
from iwant.core.constants import SEARCH_REQ, IWANT_PEER_FILE, CHANGE, SHARE
from iwant.cli.utils import get_ips, generate_id, get_paths


def set_text_factory(conn):
    conn.text_factory = str


def main():
    arguments = docopt(__doc__, version='iWant 1.0')

    if arguments['start']:
        ips = get_ips()
        for count, ip in enumerate(ips):
            print count + 1, ip
        ip = input('Enter index of ip addr:')
        timeuuid = generate_id()
        book = CommonlogBook(identity=timeuuid, state=0, ip=ips[ip - 1])
        SHARING_FOLDER, DOWNLOAD_FOLDER, CONFIG_PATH = get_paths()
        if not os.path.exists(SHARING_FOLDER) or \
            not os.path.exists(DOWNLOAD_FOLDER) or \
                not os.path.exists(CONFIG_PATH):
            raise MainException(1)
        logfile = os.path.join(CONFIG_PATH, 'iwant.log')
        log.startLogging(open(logfile, 'w'), setStdout=False)
        filename = os.path.join(CONFIG_PATH, 'iwant.db')
        if not os.path.isfile(filename):
            conn = sqlite3.connect(filename)
            conn.execute(
                '''CREATE TABLE indexer (filename text primary key, share integer, size real, hash text, piecehashes text, roothash text, isdirectory boolean)''')
            conn.execute(
                '''CREATE TABLE resume (filename text) ''')  # hash can correspond to different filenames in the disk.. so let filename be the primary key
            conn.commit()
        dbpool = adbapi.ConnectionPool(
            'sqlite3',
            filename,
            check_same_thread=False,
            cp_openfun=set_text_factory)

        try:
            reactor.listenMulticast(
                MCAST_PORT,
                CommonroomProtocol(
                    book,
                    log),
                listenMultiple=True)  # spawning election daemon
            endpoints.serverFromString(
                reactor,
                'tcp:{0}'.format(SERVER_DAEMON_PORT)). listen(
                backendFactory(
                    book,
                    dbpool=dbpool,
                    download_folder=DOWNLOAD_FOLDER,
                    shared_folder=SHARING_FOLDER))

            indexer = fileHashUtils.bootstrap(SHARING_FOLDER, dbpool)
            indexer.addCallback(fileindexedCB)
            ScanFolder(SHARING_FOLDER, filechangeCB, dbpool)

        except KeyboardInterrupt:
            reactor.stop()
            try:
                sys.exit(0)
            except SystemExit:
                os._exit(0)

    elif arguments['share'] and arguments['<path>']:

        path = arguments['<path>']
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                SHARE,
                path))

    elif arguments['search'] and arguments['<name>']:
        search_string = arguments['<name>']
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                SEARCH_REQ,
                search_string))
    elif arguments['download'] and arguments['<hash>']:
        hash_string = arguments['<hash>']
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                IWANT_PEER_FILE,
                hash_string))
    elif arguments['change'] and arguments['download'] and arguments['path'] and arguments['to']:
        download_folder = arguments['<destination>']
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                CHANGE,
                download_folder))

    reactor.run()

if __name__ == '__main__':
    main()
