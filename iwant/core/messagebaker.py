import pickle
from constants import INDEXED, HANDSHAKE, LEADER_NOT_READY, FILE,\
        LIST_ALL_FILES, ERROR_LIST_ALL_FILES, LEADER,\
        HASH_DUMP, FILE_SYS_EVENT, SEARCH_REQ, SEARCH_RES, \
        LOOKUP, IWANT_PEER_FILE, PEER_LOOKUP_RESPONSE,\
        SEND_PEER_DETAILS, FILE_DETAILS_RESP, INIT_FILE_REQ, \
        IWANT, FILE_TO_BE_DOWNLOADED, START_TRANSFER, DEAD,\
        NEW_PEER, BCAST_LEDGER, NEW_LEADER, REMOVE_LEADER, \
        SECRET_VAL, HANDLE_PONG, FACE_OFF,\
        RE_ELECTION, ALIVE, HANDLE_ALIVE, NEW_LEADER,\
        HANDLE_PING, REQ_CHUNK, END_GAME, FILE_CONFIRMATION_MESSAGE,\
        INTERESTED, UNCHOKE

class BasemessageException(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Code[{0}]=> {1}'.format(self.code, self.msg)


class Basemessage(object):
    def __init__(self, key=None, data=None, message=None):
        self.NO_PARAM = [HANDSHAKE, LEADER_NOT_READY, END_GAME, UNCHOKE]
        self.DELIMITERS_PARAMS = [FILE, LIST_ALL_FILES, ERROR_LIST_ALL_FILES, LEADER, HASH_DUMP, FILE_SYS_EVENT, SEARCH_REQ, SEARCH_RES, LOOKUP, IWANT_PEER_FILE, PEER_LOOKUP_RESPONSE, SEND_PEER_DETAILS, FILE_DETAILS_RESP, INIT_FILE_REQ, IWANT, FILE_TO_BE_DOWNLOADED, START_TRANSFER, DEAD, REQ_CHUNK, INDEXED, FILE_CONFIRMATION_MESSAGE, INTERESTED]
        self._delimiter = ';'
        self._EOL = '\r'

        if message is not None:
            self.key, self.data = self._parse_message(message)
        else:
            self.key = key
            self.data = pickle.dumps(data)

    def _parse_message(self,message):
        id, msg = message.split(self._delimiter, 1)
        key = id
        if key in self.NO_PARAM:
            data = None

        elif key in self.DELIMITERS_PARAMS:
            data = pickle.loads(msg)

        return (key,data)

    def __str__(self):
        return self.key + self._delimiter + self.data + self._EOL


class CommonroomMessageException(Exception):
    def __init__(self,code,msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Code[{0}]=> {1}'.format(self.code,self.msg)

class CommonroomMessage(object):
    def __init__(self,key=None,data=None,message=None):
        self.NO_PARAM = [HANDLE_PING]
        self.DELIMITERS = [NEW_PEER, BCAST_LEDGER, NEW_LEADER, REMOVE_LEADER, SECRET_VAL, HANDLE_PONG, FACE_OFF, DEAD]
        self.FLOATS = [RE_ELECTION, ALIVE, HANDLE_ALIVE, NEW_LEADER]
        self.EOL = '\r'
        self.delimiter = ';'

        if message is not None:
            self.key,self.data = self._parse_message(message)
        else:
            self.key = key
            self.data = pickle.dumps(data)  # data


    def _parse_message(self,message):
        id,msg = message.split(self.delimiter, 1)
        try:
            key = id
        except:
            raise CommonroomMessageException(1,'Invalid message code')

        if key in self.NO_PARAM:
            data = None

        elif key in self.DELIMITERS:
            try:
                values = pickle.loads(msg)
                if key in self.FLOATS:
                    data = list(self._clean_message(values))
                else:
                    data = values
            except:
                raise CommonroomMessageException(3,'delimitter not present')
        else:
            if key in self.FLOATS:
                data = pickle.loads(msg)[0]
        return (key,data)

    def _clean_message(self,values):
        for val in values:
            yield val

    def __str__(self):
        #return str(self.key)+';'+'$'.join([str(it) for it in self.data]) + '#'
        return str(self.key)+ self.delimiter + self.data + self.EOL

