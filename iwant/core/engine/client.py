from twisted.internet import reactor,defer,threads
from twisted.internet.endpoints import TCP4ClientEndpoint,connectProtocol
from twisted.internet.protocol import ClientFactory
from ..messagebaker import Basemessage
from ..constants import HANDSHAKE, LIST_ALL_FILES, SEARCH_REQ,\
        SEARCH_RES, LEADER_NOT_READY, IWANT_PEER_FILE,\
        PEER_LOOKUP_RESPONSE, IWANT, INIT_FILE_REQ, \
        FILE_DETAILS_RESP, FILE_TO_BE_DOWNLOADED
from ..protocols import BaseProtocol
import pickle
import json
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

def color_metadata(func):
    def wrapper(metadata):
        print bcolors.OKBLUE + func(metadata) + bcolors.ENDC
    return wrapper

def color_warning(func):
    def wrapper(warning_msg):
        print bcolors.WARNING + func(warning_msg) + bcolors.ENDC
    return wrapper

@color_metadata
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
            FILE_DETAILS_RESP : self.download_file,
            FILE_TO_BE_DOWNLOADED : self.show_file_to_be_downloaded
        }
        self.buff = ''
        self.delimiter = '\r'

    def connectionMade(self):
        print 'Connection Established ... \n'
        reqMessage = Basemessage(key=self.factory.query, data=self.factory.arguments)
        self.sendLine(reqMessage)

    def serviceMessage(self, data):
        '''
            Incoming messages are processed and appropriate functions are called
        '''
        req = Basemessage(message=data)
        try:
            self.events[req.key]()
        except:
            self.events[req.key](req.data)

    def show_search_results(self, data):
        '''
            callback: displays file search response from the leader(via local server)
            triggered when server replies the file search response from the leader to the client

        '''
        response = []
        for i in data:
            response.append((i.filename, i.checksum, i.size))
        print tabulate.tabulate(response, headers=["Filename", "Checksum", "Size"])
        reactor.stop()

    def leader_not_ready(self):
        '''
            callback: displays leader/tracker not available
            triggered when leader not ready
        '''
        #print 'Tracker not available..'
        print_warning('Tracker not available')
        reactor.stop()

    def download_file(self, data):
        # Unused
        print data
        reactor.stop()

    def show_file_to_be_downloaded(self, data):
        '''
            callback: displays file to be downloaded
            triggered when user downloads a file
        '''
        file_basename = os.path.basename(data[0])
        file_type_split = data[0].rsplit('.')
        if len(file_type_split) == 2:
            file_type = file_type_split[-1]
        else:
            file_type = 'UNKNOWN'
        print_metadata('Filename: {0}\nSize: {1}\nBasename: {2}\nFiletype: {3}\n'.format(data[0], data[1], file_basename, file_type))
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
