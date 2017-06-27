"""iWant.

Usage:
    iwanto start
    iwanto search <name>
    iwanto download <hash>
    iwanto share <path>
    iwanto download to <destination>
    iwanto view config
    iwanto --version

Options:
    -h --help                                   Show this screen.
    --version                                   Show version.
    start                                       This starts the iwant server in your system
    search <name>                               Discovering files in the network. Example: iwanto search batman
    download <hash>                             Downloads the file from the network
    share <path>                                Change your shared folder
    view config                                 View shared and download folder
    download to <destination>                   Change download folder


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
from iwant.cli.utils import get_ips, generate_id, get_paths, check_config_status, show_config_options


def set_text_factory(conn):
    conn.text_factory = str


def main():
    arguments = docopt(__doc__, version='iWant 1.0')

    if arguments['start']:
        if not check_config_status():
            show_config_options()
        timeuuid = generate_id()
        SHARING_FOLDER, DOWNLOAD_FOLDER, CONFIG_PATH = get_paths()
        if not os.path.exists(SHARING_FOLDER) or \
            not os.path.exists(DOWNLOAD_FOLDER) or \
                not os.path.exists(CONFIG_PATH):
            raise MainException(1)
        if SHARING_FOLDER == DOWNLOAD_FOLDER:
            raise MainException(4)
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

        ips = get_ips()
        print 'Network interface available'
        for count, ip in enumerate(ips):
            print '{0}. {1} => {2}'.format(count + 1, ip[1], ip[0])
        ip = input('Enter index of the interface:')
        book = CommonlogBook(identity=timeuuid, state=0, ip=ips[ip - 1][0])

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
        reactor.run()

    elif arguments['share'] and arguments['<path>']:
        check_config_status()
        path = os.path.realpath(arguments['<path>'])
        _, DOWNLOAD_FOLDER, _ = get_paths()
        if DOWNLOAD_FOLDER == path:
            raise MainException(4)
        elif path == '':
            raise MainException(1)
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                SHARE,
                path))
        reactor.run()

    elif arguments['search'] and arguments['<name>']:
        search_string = arguments['<name>']
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                SEARCH_REQ,
                search_string))
        reactor.run()
    elif arguments['download'] and arguments['<hash>']:
        hash_string = arguments['<hash>']
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                IWANT_PEER_FILE,
                hash_string))
        reactor.run()
    elif arguments['download'] and arguments['to'] and arguments['<destination>']:
        check_config_status()
        download_folder = os.path.realpath(arguments['<destination>'])
        SHARING_FOLDER, _, _ = get_paths()
        if SHARING_FOLDER == download_folder:
            raise MainException(4)
        elif download_folder == '':
            raise MainException(1)
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                CHANGE,
                download_folder))
        reactor.run()
    elif arguments['view'] and arguments['config']:
        check_config_status()
        SHARING_FOLDER, DOWNLOAD_FOLDER, _ = get_paths()
        print 'Shared folder:{0}\nDownload folder:{1}'.format(SHARING_FOLDER, DOWNLOAD_FOLDER)


if __name__ == '__main__':
    main()
