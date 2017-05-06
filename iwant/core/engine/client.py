from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory
from iwant.core.messagebaker import bake, unbake
from iwant.cli.utils import update_config, print_log, CLIENT_LOG_INFO, ERROR_LOG, WARNING_LOG
from iwant.core.constants import SEARCH_REQ, SEARCH_RES, \
    LEADER_NOT_READY, IWANT_PEER_FILE,\
    FILE_TO_BE_DOWNLOADED, CHANGE, SHARE,\
    NEW_SHARED_FOLDER_RES, NEW_DOWNLOAD_FOLDER_RES
from iwant.core.protocols import BaseProtocol
import tabulate
import os


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
        # print 'Connection Established ... \n'
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
        print_log(
            tabulate.tabulate(
                response,
                headers=[
                    "Filename",
                    "Size",
                    "Checksum",
                    "RootHash"]),
            CLIENT_LOG_INFO)
        reactor.stop()

    def leader_not_ready(self, data):
        '''
            callback: displays leader/tracker not available
            triggered when leader not ready
        '''
        # print 'Tracker not available..'
        print_log(data['reason'], WARNING_LOG)
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
        print_log(
            'Filename: {0}\nSize: {1}\nBasename: {2}\nFiletype: {3}\n'.format(
                filename_response,
                filesize_response,
                file_basename,
                file_type), CLIENT_LOG_INFO)
        reactor.stop()

    def confirm_new_shared_folder(self, data):
        print_log(
            'Shared Folder: {0}'.format(
                data['shared_folder_response']), CLIENT_LOG_INFO)
        reactor.stop()

    def confirm_new_download_folder(self, data):
        print_log(
            'Download Folder: {0}'.format(
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
        # print 'started connecting'
        pass

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
