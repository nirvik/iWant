class MainException(self, code):
    def __init__(self, code):
        self.code = code
        self.msg = { 1: 'file doesn\'t exist'}

    def __str__(self):
        return 'Error [{0}] => {1}'.format(self.code, self.msg[self.code])
