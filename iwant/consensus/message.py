import pickle

class P2PCommunication(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Code[{0}]=> {1}'.format(self.code, self.msg)


class P2PMessage(object):
    def __init__(self, key=None, data=None, message=None):
        self.NO_PARAM = ['handshake']
        self.DELIMITERS = ['file','listAll','ErrorListingAll','leader']

        if message is not None:
            self.key, self.data = self._parse_message(message)
        else:
            self.key = key
            self.data = pickle.dumps(data)

    def _parse_message(self,message):
        id, msg = message.split(';')
        key = id
        if key in self.NO_PARAM:
            data = None

        elif key in self.DELIMITERS:
            data = pickle.loads(msg)

        return (key,data)

    def __str__(self):
        return self.key + ';' + self.data + '#'


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
