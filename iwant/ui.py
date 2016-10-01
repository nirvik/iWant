from twisted.internet import reactor
from client import FrontendFactory, Frontend
from config import SERVER_DAEMON_HOST, SERVER_DAEMON_PORT
from constants.events.server import SEARCH_REQ, IWANT_PEER_FILE, INIT_FILE_REQ
import argparse

def main():

    parser = argparse.ArgumentParser(description='iwant')
    parser.add_argument("--search", help="instant fuzzy search", type=str)
    parser.add_argument("--download", help="download file by giving hash", type=str)
    args = parser.parse_args()

    if args.search:
        reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, FrontendFactory(SEARCH_REQ, args.search))

    elif args.download:
        reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, FrontendFactory(IWANT_PEER_FILE, args.download))#, DOWNLOAD_FOLDER))
    reactor.run()

if __name__ == '__main__':
    main()
