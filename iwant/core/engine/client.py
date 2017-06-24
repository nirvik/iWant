from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory
from iwant.core.messagebaker import bake, unbake
from iwant.cli.utils import update_config, print_log, CLIENT_LOG_INFO, WARNING_LOG, ERROR_LOG
from iwant.core.constants import SEARCH_REQ, SEARCH_RES, \
    LEADER_NOT_READY, IWANT_PEER_FILE,\
    FILE_TO_BE_DOWNLOADED, CHANGE, SHARE,\
    NEW_SHARED_FOLDER_RES, NEW_DOWNLOAD_FOLDER_RES,\
    HASH_NOT_PRESENT
from iwant.core.protocols import BaseProtocol
import tabulate


class Frontend(BaseProtocol):

    def __init__(self, factory):
        self.factory = factory
        self.special_handler = None
        self.events = {
            SEARCH_RES: self.show_search_results,
            LEADER_NOT_READY: self.display_error,
            HASH_NOT_PRESENT: self.display_error,
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

    def display_error(self, data):
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
        file_structure_response = data['message']
        if file_structure_response['isFile']:
            file_name = file_structure_response['filename']
            file_size = file_structure_response['filesize']
            checksum = file_structure_response['checksum']
            print_log(
                'Filename: {0}\nSize: {1} MB'.format(
                    file_name,
                    file_size
                ),
                CLIENT_LOG_INFO)
        else:
            root_directory = file_structure_response['rootDirectory']
            root_directory_checksum = file_structure_response[
                'rootDirectoryChecksum']
            print_log(
                'Directory: {0}\nDirectory Checksum: {1}'.format(
                    root_directory,
                    root_directory_checksum),
                CLIENT_LOG_INFO)
            files = file_structure_response['files']
            for file_property in files:
                filename, size, checksum = file_property
                print_log(
                    'Filename: {0}\tSize: {1} MB'.format(
                        filename,
                        size),
                    CLIENT_LOG_INFO)
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
        try:
            if self.query == SHARE:
                update_config(shared_folder=self.arguments)
            elif self.query == CHANGE:
                update_config(download_folder=self.arguments)
            else:
                print_log('iwant server is not running', ERROR_LOG)
        finally:
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
