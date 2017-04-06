class MainException(Exception):

    def __init__(self, code):
        self.code = code
        self.msg = {
            1: 'shared folder doesn\'t exist',
            2: 'corrupted .iwant.conf file'
        }

    def __str__(self):
        return 'Error [{0}] => {1}'.format(self.code, self.msg[self.code])


class BasemessageException(Exception):

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Code[{0}]=> {1}'.format


class CommonroomMessageException(Exception):

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Code[{0}]=> {1}'.format(self.code, self.msg)


class CommonroomProtocolException(Exception):

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Error [{0}] => {1}'.format(self.code, self.msg)


class ServerException(Exception):

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Error [{0}] => {1}'.format(self.code, self.msg)
