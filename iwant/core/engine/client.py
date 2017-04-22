from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory
from iwant.core.messagebaker import bake, unbake
from iwant.cli.utils import update_config
from iwant.core.constants import SEARCH_REQ, SEARCH_RES, \
    LEADER_NOT_READY, IWANT_PEER_FILE,\
    FILE_TO_BE_DOWNLOADED, CHANGE, SHARE,\
    NEW_SHARED_FOLDER_RES, NEW_DOWNLOAD_FOLDER_RES
from iwant.core.protocols import BaseProtocol
import tabulate
import os
from functools import wraps

SERVER_LOG_INFO = 'server log'
CLIENT_LOG_INFO = 'client log'
ERROR_LOG = 'error log'
WARNING_LOG = 'warning log'


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def color(func):
    is_windows = True if os.name == 'nt' else False

    @wraps(func)
    def wrapper(message, message_type=None):
        if not is_windows:
            if message_type == WARNING_LOG:
                print bcolors.WARNING + func(message) + bcolors.ENDC
            elif message_type == ERROR_LOG:
                print bcolors.FAIL + func(message) + bcolors.ENDC
            elif message_type == SERVER_LOG_INFO:
                print bcolors.OKGREEN + func(message) + bcolors.ENDC
            elif message_type == CLIENT_LOG_INFO:
                print bcolors.OKBLUE + func(message) + bcolors.ENDC
            else:
                print func(message)
        else:
            print func(message)
    return wrapper


@color
def print_status(data, message_type=None):
    return data


class Frontend(BaseProtocol):

    def __init__(self, factory):
        self.factory = factory
        self.special_handler = None
        self.events = {
            SEARCH_RES: self.show_search_results,
            LEADER_NOT_READY: self.leader_not_ready,
            FILE_TO_BE_DOWNLOADED: self.show_file_to_be_downloaded,
            NEW_SHARED_FOLDER_RES: self.confirm_new_shared_folder,
            NEW_DOWNLOAD_FOLDER_RES: self.confirm_new_download_folder
        }
        self.buff = ''
        self.delimiter = '\r'

    def connectionMade(self):
        print 'Connection Established ... \n'
        if self.factory.query == SEARCH_REQ:
            reqMessage = bake(SEARCH_REQ, search_query=self.factory.arguments)
        elif self.factory.query == IWANT_PEER_FILE:
            reqMessage = bake(IWANT_PEER_FILE, filehash=self.factory.arguments)
        elif self.factory.query == SHARE:
            shared_folder = self.factory.arguments
            update_config(shared_folder=shared_folder)
            reqMessage = bake(SHARE, shared_folder=shared_folder)
        elif self.factory.query == CHANGE:
            download_folder = self.factory.arguments
            update_config(download_folder=download_folder)
            reqMessage = bake(CHANGE, download_folder=self.factory.arguments)
        self.sendLine(reqMessage)

    def serviceMessage(self, data):
        '''
            Incoming messages are processed and appropriate functions are called
        '''
        key, value = unbake(message=data)
        self.events[key](value)

    def show_search_results(self, data):
        '''
            callback: displays file search response from the leader(via local server)
            triggered when server replies the file search response from the leader to the client

        '''
        search_response = data['search_query_response']
        response = []
        for i in search_response:
            response.append(i[:-1])
        print tabulate.tabulate(response, headers=["Filename", "Size", "Checksum", "RootHash"])
        reactor.stop()

    def leader_not_ready(self, data):
        '''
            callback: displays leader/tracker not available
            triggered when leader not ready
        '''
        # print 'Tracker not available..'
        print_status(data['reason'], WARNING_LOG)
        reactor.stop()

    def show_file_to_be_downloaded(self, data):
        '''
            callback: displays file to be downloaded
            triggered when user downloads a file
        '''
        filename_response = data['filename']
        filesize_response = data['filesize']

        file_basename = os.path.basename(filename_response)
        file_type_split = filename_response.rsplit('.')
        if len(file_type_split) == 2:
            file_type = file_type_split[-1]
        else:
            file_type = 'UNKNOWN'
        print_status(
            'Filename: {0}\nSize: {1}\nBasename: {2}\nFiletype: {3}\n'.format(
                filename_response,
                filesize_response,
                file_basename,
                file_type), CLIENT_LOG_INFO)
        reactor.stop()

    def confirm_new_shared_folder(self, data):
        print_status(
            'SHARED FOLDER => {0}'.format(
                data['shared_folder_response']), CLIENT_LOG_INFO)
        reactor.stop()

    def confirm_new_download_folder(self, data):
        print_status(
            'DOWNLOAD FOLDER => {0}'.format(
                data['download_folder_response']), CLIENT_LOG_INFO)
        reactor.stop()


class FrontendFactory(ClientFactory):

    def __init__(self, query, data=None, downloadfolder=None):
        self.state = 1
        self.FH = {}
        self.query = query
        self.arguments = data
        self.download_folder = downloadfolder

    def startedConnecting(self, connector):
        print 'started connecting'

    def clientConnectionFailed(self, connector, reason):
        print reason
        reactor.stop()

    def buildProtocol(self, addr):
        return Frontend(self)


if __name__ == '__main__':
    reactor.connectTCP('127.0.0.1', 1234, FrontendFactory())
    try:
        reactor.run()
    except KeyboardInterrupt:
        print 'stopping reactor'
        reactor.stop()
