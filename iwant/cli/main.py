import os, sys
import time_uuid
import ConfigParser
from netifaces import interfaces, ifaddresses, AF_INET
import time_uuid
import argparse
from twisted.python import log
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
#from iwant.core.engine.identity.book import CommonlogBook
from iwant.core.engine.identity import CommonlogBook
from iwant.core.engine.fileindexer import findexer
from twisted.internet import reactor, endpoints, threads
from iwant.core.engine.client import FrontendFactory, Frontend
from iwant.core.config import SERVER_DAEMON_HOST, SERVER_DAEMON_PORT
from iwant.core.constants import SEARCH_REQ, IWANT_PEER_FILE,\
        INIT_FILE_REQ

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
    if sys.platform =='linux2' or sys.platform == 'linux' or sys.platform == 'darwin':
        iwant_directory_path = os.path.join(home_directory_path, '.iwant')
    elif sys.platform == 'win32':
        iwant_directory_path = os.path.join(os.getenv('APPDATA'),'.iwant')

    return iwant_directory_path

def get_paths():
    Config = ConfigParser.ConfigParser()
    conf_path = get_basepath()
    try:
        Config.read(os.path.join(conf_path,'.iwant.conf'))
        CONFIG_PATH = conf_path
        SHARING_FOLDER = Config.get('Paths', 'share')
        DOWNLOAD_FOLDER = Config.get('Paths', 'download')
    except:
        raise MainException(2)

    return (SHARING_FOLDER, DOWNLOAD_FOLDER, CONFIG_PATH)

def main():
    ips = get_ips()
    for count, ip in enumerate(ips):
        print count+1, ip
    ip = input('Enter index of ip addr:')
    timeuuid = generate_id()
    book = CommonlogBook(identity=timeuuid, state=0, ip = ips[ip-1])  # creating shared memory between server and election daemon

    SHARING_FOLDER, DOWNLOAD_FOLDER, CONFIG_PATH = get_paths()
    if not os.path.exists(SHARING_FOLDER) or \
        not os.path.exists(DOWNLOAD_FOLDER) or \
            not os.path.exists(CONFIG_PATH):
        raise MainException(1)

    logfile = os.path.join(CONFIG_PATH, 'iwant.log')
    log.startLogging(open(logfile, 'w'), setStdout=False)

    try:
        reactor.listenMulticast(MCAST_PORT, CommonroomProtocol(book, log), listenMultiple=True)  # spawning election daemon
        endpoints.serverFromString(reactor, 'tcp:{0}'.format(SERVER_DAEMON_PORT)).\
                listen(backendFactory(book, sharing_folder=SHARING_FOLDER,\
                download_folder=DOWNLOAD_FOLDER, config_folder= CONFIG_PATH))  # spawning server daemon

        indexer = findexer.FileHashIndexer(SHARING_FOLDER, CONFIG_PATH, bootstrap=True)  # better would be to add a classmethod rather than setting bootstrap to True
        indexingDeferred = threads.deferToThread(indexer.index)
        indexingDeferred.addCallback(fileindexedCB)

        ScanFolder(SHARING_FOLDER, CONFIG_PATH, filechangeCB)  # spawning filemonitoring daemon and registering callbacks
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























