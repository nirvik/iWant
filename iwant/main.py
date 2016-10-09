import os, sys
from netifaces import interfaces, ifaddresses, AF_INET
import time_uuid
import pickle
import ConfigParser
from watchdog.observers import Observer
from exception import MainException
from constants.events import election, server
from constants.states import server
from communication import message
from communication.election_communication import message
from watching import ScanFolder
from shared.book import CommonlogBook
from config import SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, MCAST_IP, MCAST_PORT
from protocols import FilemonitorClientFactory, FilemonitorClientProtocol
from utils.utils import get_ips
from twisted.internet import reactor, endpoints
from consensus.beacon import CommonroomProtocol
from server import backendFactory

def update_about_file_changes(config_path):
    '''
        This is a callback registered with ScanFolder
    '''
    factory = FilemonitorClientFactory(config_path)
    reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, factory)


def main():
    ips = get_ips()
    for count, ip in enumerate(ips):
        print count, ip
    ip = input('Enter index of ip addr:')
    timeuuid = time_uuid.TimeUUID.with_utcnow()  # generate uuid
    book = CommonlogBook(identity=timeuuid, state=0, ip = ips[ip-1])  # creating shared memory between server and election daemon

    Config = ConfigParser.ConfigParser()
    if sys.platform =='linux2' or sys.platform == 'linux':
        Config.read(os.path.join('/home/'+os.getenv('SUDO_USER'),'.iwant.conf'))
        CONFIG_PATH = '/var/log/iwant/'
    elif sys.platform=='win32':
        Config.read(os.path.join(os.environ['USERPROFILE'] + '\\AppData\\iwant\\','.iwant.conf'))
        CONFIG_PATH = os.environ['USERPROFILE'] + '\\AppData\\iwant\\'
    elif sys.platform == 'darwin':
        Config.read(os.path.join('/Users/'+os.getenv('SUDO_USER'),'.iwant.conf'))
        CONFIG_PATH = '/var/log/iwant/'

    SHARING_FOLDER = Config.get('Paths', 'share')
    DOWNLOAD_FOLDER = Config.get('Paths', 'download')

    print SHARING_FOLDER, DOWNLOAD_FOLDER, CONFIG_PATH
    if not os.path.exists(SHARING_FOLDER) or \
        not os.path.exists(DOWNLOAD_FOLDER) or \
            not os.path.exists(CONFIG_PATH):
        raise MainException(1)

    try:
        reactor.listenMulticast(MCAST_PORT, CommonroomProtocol(book), listenMultiple=True)  # spawning election daemon
        endpoints.serverFromString(reactor, 'tcp:{0}'.format(SERVER_DAEMON_PORT)).\
                listen(backendFactory(book, sharing_folder=SHARING_FOLDER,\
                download_folder=DOWNLOAD_FOLDER, config_folder= CONFIG_PATH))  # spawning server daemon
        ScanFolder(SHARING_FOLDER, CONFIG_PATH, update_about_file_changes)  # spawning filemonitoring daemon
        reactor.run()
    except KeyboardInterrupt:
        observer.stop()
        reactor.stop()
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

if __name__ == '__main__':
    main()
