import os
import sys
import time_uuid
import ConfigParser
from netifaces import interfaces, ifaddresses, AF_INET
import time_uuid
import argparse
import sqlite3
from twisted.python import log
from twisted.enterprise import adbapi
from watchdog.observers import Observer
from iwant.core.exception import MainException
from iwant.core.engine.consensus.beacon import CommonroomProtocol
from iwant.core.engine.server import backendFactory
from iwant.core.engine.monitor.watching import ScanFolder
from iwant.core.config import SERVER_DAEMON_HOST,\
        SERVER_DAEMON_PORT, MCAST_IP, MCAST_PORT
from iwant.core.protocols import FilemonitorClientFactory,\
        FilemonitorClientProtocol
from iwant.core.engine.monitor.callbacks import filechangeCB,\
        fileindexedCB
# from iwant.core.engine.identity.book import CommonlogBook
from iwant.core.engine.identity import CommonlogBook
from iwant.core.engine.fileindexer.findexer import FileHashIndexer
from iwant.core.engine.fileindexer import fileHashUtils
from twisted.internet import reactor, endpoints, threads
from iwant.core.engine.client import FrontendFactory, Frontend
from iwant.core.config import SERVER_DAEMON_HOST, SERVER_DAEMON_PORT
from iwant.core.constants import SEARCH_REQ, IWANT_PEER_FILE,\
        INIT_FILE_REQ, INDEXED

def get_ips():
    ip_list = []
    for interface in interfaces():
        try:
            for link in ifaddresses(interface)[AF_INET]:
                ip_list.append(link['addr'])
        except:
            pass
    return ip_list

def generate_id():
    timeuuid = time_uuid.TimeUUID.with_utcnow()  # generate uuid
    return timeuuid

def get_basepath():
    home_directory_path = os.path.expanduser('~')
    if sys.platform == 'linux2' or sys.platform == 'linux'\
            or sys.platform == 'darwin':
        iwant_directory_path = os.path.join(home_directory_path, '.iwant')
    elif sys.platform == 'win32':
        iwant_directory_path = os.path.join(os.getenv('APPDATA'), '.iwant')

    return iwant_directory_path

def get_paths():
    Config = ConfigParser.ConfigParser()
    conf_path = get_basepath()
    try:
        Config.read(os.path.join(conf_path, '.iwant.conf'))
        CONFIG_PATH = conf_path
        SHARING_FOLDER = Config.get('Paths', 'share')
        DOWNLOAD_FOLDER = Config.get('Paths', 'download')
    except:
        raise MainException(2)

    return (SHARING_FOLDER, DOWNLOAD_FOLDER, CONFIG_PATH)

def fuckthisshit(data):
    print 'indexing done'
    fileindexedCB(data)

def set_text_factory(conn):
    conn.text_factory = str

def main():
    ips = get_ips()
    for count, ip in enumerate(ips):
        print count+1, ip
    ip = input('Enter index of ip addr:')
    timeuuid = generate_id()
    book = CommonlogBook(identity=timeuuid, state=0, ip=ips[ip-1])

    SHARING_FOLDER, DOWNLOAD_FOLDER, CONFIG_PATH = get_paths()
    SHARING_FOLDER = '/run/media/nirvik/Data/Movies'
    DOWNLOAD_FOLDER = '/run/media/nirvik/Data/iWantDownload'
    CONFIG_PATH = '/home/nirvik/.iwant/'

    if not os.path.exists(SHARING_FOLDER) or \
        not os.path.exists(DOWNLOAD_FOLDER) or \
            not os.path.exists(CONFIG_PATH):
        raise MainException(1)

    logfile = os.path.join(CONFIG_PATH, 'iwant.log')
    log.startLogging(open(logfile, 'w'), setStdout=False)
    filename = os.path.join(CONFIG_PATH, 'iwant.db')
    if not os.path.isfile(filename):
        conn = sqlite3.connect(filename)
        conn.execute('''CREATE TABLE indexer (filename text primary key, share integer, size real, hash text, piecehashes text, roothash text)''')
        conn.execute('''CREATE TABLE resume (filename text primary key, hash text) ''')
        conn.commit()

    dbpool = adbapi.ConnectionPool('sqlite3', filename, check_same_thread=False, cp_openfun = set_text_factory)
    try:
        reactor.listenMulticast(MCAST_PORT, CommonroomProtocol(book, log), listenMultiple=True)  # spawning election daemon
        endpoints.serverFromString(reactor, 'tcp:{0}'.format(SERVER_DAEMON_PORT)).\
                listen(backendFactory(book, dbpool, sharing_folder=SHARING_FOLDER,\
                download_folder=DOWNLOAD_FOLDER, config_folder= CONFIG_PATH))

        indexer = fileHashUtils.bootstrap(SHARING_FOLDER, dbpool)
        #indexer.addCallback(fileindexedCB, None)
        indexer.addCallback(fileindexedCB)
        ScanFolder(SHARING_FOLDER, filechangeCB, dbpool)
        reactor.run()

    except KeyboardInterrupt:
        observer.stop()
        reactor.stop()
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)


def ui():
    parser = argparse.ArgumentParser(description='iwant')
    parser.add_argument("--search", help="instant fuzzy search", type=str)
    parser.add_argument("--download", help="download file by giving hash", type=str)
    args = parser.parse_args()

    if args.search:
        reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, FrontendFactory(SEARCH_REQ, args.search))

    elif args.download:
        reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, FrontendFactory(IWANT_PEER_FILE, args.download))
    reactor.run()

