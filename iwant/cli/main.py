import os
import sys
import argparse
import sqlite3
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


def fuckthisshit(data):
    print 'indexing done'
    fileindexedCB(data)


def set_text_factory(conn):
    conn.text_factory = str


def main():
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
            '''CREATE TABLE indexer (filename text primary key, share integer, size real, hash text, piecehashes text, roothash text)''')
        conn.execute(
            '''CREATE TABLE resume (filename text primary key, hash text) ''')
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
        reactor.run()

    except KeyboardInterrupt:
        reactor.stop()
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)


def ui():
    parser = argparse.ArgumentParser(description='iwant')
    parser.add_argument("--search", help="instant fuzzy search", type=str)
    parser.add_argument(
        "--download",
        help="download file by giving hash",
        type=str)
    parser.add_argument(
        "--share",
        help="change the share folder directory",
        type=str)
    parser.add_argument(
        "--change_download_path",
        help="change the download path directory",
        type=str)
    args = parser.parse_args()

    if args.search:
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                SEARCH_REQ,
                args.search))

    elif args.download:
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                IWANT_PEER_FILE,
                args.download))

    elif args.share:
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                SHARE,
                args.share))

    elif args.change_download_path:
        reactor.connectTCP(
            SERVER_DAEMON_HOST,
            SERVER_DAEMON_PORT,
            FrontendFactory(
                CHANGE,
                args.change_download_path))

    reactor.run()

if __name__ == '__main__':
    main()
