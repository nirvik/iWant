class FlashMessageException(Exception):
    def __init__(self,code,msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Code[{0}]=> {1}'.format(self.code,self.msg)

class FlashMessage(object):
    def __init__(self,key=None,data=None,message=None):
        self.NO_PARAM = [4,7]
        self.DELIMITERS = [0,3,6]
        self.FLOATS = [1,2,5,6]
        if message is not None:
            self.key,self.data = self._parse_message(message)
        else:
            self.key = key
            self.data = data


    def _parse_message(self,message):
        id,msg = message.split(';')
        try:
            key = int(id)
        except:
            raise FlashMessageException(1,'Invalid message code')

        if key in self.NO_PARAM:
            data = None

        elif key in self.DELIMITERS:
            try:
                values = msg.split('$')
                if key in self.FLOATS:
                    data = list(self._clean_message(values))
                else:
                    data = values
            except:
                raise FlashMessageException(3,'delimitter not present')
        else:
            if key in self.FLOATS:
                data = float(msg)
            else:
                data = msg
        return (key,data)

    def _clean_message(self,values):
        for val in values:
            try:
                yield float(val)
            except:
                yield val

    def __str__(self):
        return str(self.key)+';'+'$'.join([str(it) for it in self.data]) + '#'
