from twisted.internet import reactor
#from twisted.internet.endpoints import TCP4ClientEndpoint,connectProtocol
from twisted.internet.protocol import ClientFactory
from ..messagebaker import bake, unbake
from ..constants import SEARCH_REQ, SEARCH_RES, \
        LEADER_NOT_READY, IWANT_PEER_FILE,\
        FILE_TO_BE_DOWNLOADED, CHANGE, SHARE,\
        NEW_SHARED_FOLDER_RES, NEW_DOWNLOAD_FOLDER_RES
from ..protocols import BaseProtocol
import tabulate
import os

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
    def wrapper(metadata):
        print bcolors.OKBLUE + func(metadata) + bcolors.ENDC
    return wrapper

def color_warning(func):
    def wrapper(warning_msg):
        print bcolors.WARNING + func(warning_msg) + bcolors.ENDC
    return wrapper

@color
def print_metadata(data):
    return data

@color_warning
def print_warning(msg):
    return msg

class Frontend(BaseProtocol):

    def __init__(self, factory):
        self.factory = factory
        self.special_handler = None
        self.events = {
            SEARCH_RES : self.show_search_results,
            LEADER_NOT_READY : self.leader_not_ready,
            FILE_TO_BE_DOWNLOADED : self.show_file_to_be_downloaded,
            NEW_SHARED_FOLDER_RES : self.confirm_new_shared_folder,
            NEW_DOWNLOAD_FOLDER_RES: self.confirm_new_download_folder
        }
        self.buff = ''
        self.delimiter = '\r'

    def connectionMade(self):
        print 'Connection Established ... \n'
        #reqMessage = Basemessage(key=self.factory.query, data=self.factory.arguments)
        if self.factory.query == SEARCH_REQ:
            reqMessage = bake(SEARCH_REQ, search_query=self.factory.arguments)
        elif self.factory.query == IWANT_PEER_FILE:
            reqMessage = bake(IWANT_PEER_FILE, filehash=self.factory.arguments)
        elif self.factory.query == SHARE:
            reqMessage = bake(SHARE, shared_folder=self.factory.arguments)
        elif self.factory.query == CHANGE:
            reqMessage = bake(CHANGE, download_folder=self.factory.arguments)
        self.sendLine(reqMessage)

    def serviceMessage(self, data):
        '''
            Incoming messages are processed and appropriate functions are called
        '''
        #req = Basemessage(message=data)
        #try:
        #    self.events[req.key]()
        #except:
        #    self.events[req.key](req.data)
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
        #print 'Tracker not available..'
        print_warning(data['reason'])
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
        print_metadata('Filename: {0}\nSize: {1}\nBasename: {2}\nFiletype: {3}\n'.format(filename_response, filesize_response, file_basename, file_type))
        reactor.stop()

    def confirm_new_shared_folder(self, data):
        print_metadata('SHARED FOLDER => {0}'.format(data['shared_folder_response']))
        reactor.stop()

    def confirm_new_download_folder(self, data):
        print_metadata('DOWNLOAD FOLDER => {0}'.format(data['download_folder_response']))
        reactor.stop()


class FrontendFactory(ClientFactory):
    def __init__(self, query, data=None, downloadfolder=None):
        self.state = 1
        self.FH = {}
        self.query  = query
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
    reactor.connectTCP('127.0.0.1',1234, FrontendFactory())
    try:
        reactor.run()
    except KeyboardInterrupt:
        print 'stopping reactor'
        reactor.stop()
