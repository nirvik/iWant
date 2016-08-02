from twisted.internet.protocol import Protocol

class FlashpointProtocol(Protocol):

    def connectionMade(self):
        pass

    def sendLine(self,line):
        self.transport.write(str(line))

    def escape_dollar_sign(self,data):
        return data.replace(self.delimiter,'')

    def hookHandler(self,fn):
        self.special_handler = fn

    def unhookHandler(self):
        self.special_handler = None

    def dataReceived(self,data):
        for char in data:
            self.buff+=char
            if char == self.delimiter:
                request_str = self.escape_dollar_sign(self.buff)
                self.buff = ''
                self.serviceMessage(request_str)
        self.buff = ''

    def serviceMessage(self,message):
        pass
