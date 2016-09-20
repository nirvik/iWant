import pickle
#from iwant.constants.events.server import *
from constants.events.server import *

class P2PCommunication(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Code[{0}]=> {1}'.format(self.code, self.msg)


class P2PMessage(object):
    def __init__(self, key=None, data=None, message=None):
        self.NO_PARAM = [HANDSHAKE, LEADER_NOT_READY]
        self.DELIMITERS_PARAMS = [FILE, LIST_ALL_FILES, ERROR_LIST_ALL_FILES, LEADER, HASH_DUMP, FILE_SYS_EVENT, SEARCH_REQ, SEARCH_RES, LOOKUP, IWANT_PEER_FILE, PEER_LOOKUP_RESPONSE, SEND_PEER_DETAILS, FILE_DETAILS_RESP, INIT_FILE_REQ, IWANT, FILE_TO_BE_DOWNLOADED, START_TRANSFER]
        self._delimiter = ';'
        self._EOL = '#'

        if message is not None:
            self.key, self.data = self._parse_message(message)
        else:
            self.key = key
            self.data = pickle.dumps(data)

    def _parse_message(self,message):
        id, msg = message.split(self._delimiter)
        key = id
        if key in self.NO_PARAM:
            data = None

        elif key in self.DELIMITERS_PARAMS:
            data = pickle.loads(msg)

        return (key,data)

    def __str__(self):
        return self.key + self._delimiter + self.data + self._EOL


class LocalMessage(object):
    def __init__(self, key=None, data=None, message=None):
        if message is not None:
            self.key, self.data = self._parse_message(message)
        else:
            self.key = key
            self.data = data

    def _parse_message(self, message):
        id, msg = message.split()
        return (id, msg)
