from twisted.internet.protocol import Protocol

class FlashpointProtocol(Protocol):
    def __init__(self):
        self.buff = ''
        self.special_handler = None

    def connectionMade(self):
        pass

    def sendLine(self,line):
        self.transport.write(str(line)+'$')

    def escape_dollar_sign(self,data):
        return data.replace('$','').replace('\n','')

    def hookHandler(self,fn):
        self.special_handler = fn

    def unhookHandler(self):
        self.special_handler = None

    def dataReceived(self,data):
        buff = ''
        for char in data:
            buff+=char
            if char =='$':
                request_str = self.escape_dollar_sign(buff)
                buff = ''
                self.serviceMessage(request_str)

    def serviceMessage(self,message):
        pass
