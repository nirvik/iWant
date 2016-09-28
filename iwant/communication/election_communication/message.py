import pickle
from iwant.constants.events.election import NEW_PEER, RE_ELECTION, ALIVE, BCAST_LEDGER, HANDLE_PING, HANDLE_ALIVE, NEW_LEADER, HANDLE_PONG, REMOVE_LEADER, PING, PONG, SECRET_VAL, FACE_OFF, DEAD


class FlashMessageException(Exception):
    def __init__(self,code,msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Code[{0}]=> {1}'.format(self.code,self.msg)

class FlashMessage(object):
    def __init__(self,key=None,data=None,message=None):
        self.NO_PARAM = [HANDLE_PING]
        self.DELIMITERS = [NEW_PEER, BCAST_LEDGER, NEW_LEADER, REMOVE_LEADER, SECRET_VAL, HANDLE_PONG, FACE_OFF, DEAD]
        self.FLOATS = [RE_ELECTION, ALIVE, HANDLE_ALIVE, NEW_LEADER]

        if message is not None:
            self.key,self.data = self._parse_message(message)
        else:
            self.key = key
            self.data = pickle.dumps(data)  # data


    def _parse_message(self,message):
        id,msg = message.split(';')
        try:
            key = id
        except:
            raise FlashMessageException(1,'Invalid message code')

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
                raise FlashMessageException(3,'delimitter not present')
        else:
            if key in self.FLOATS:
                data = pickle.loads(msg)[0]
        return (key,data)

    def _clean_message(self,values):
        for val in values:
            yield val

    def __str__(self):
        #return str(self.key)+';'+'$'.join([str(it) for it in self.data]) + '#'
        return str(self.key)+';'+self.data+'#'
