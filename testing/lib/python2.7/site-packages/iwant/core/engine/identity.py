class CommonlogBook(object):
    __doc__ = '''
        This is a book which will store all the persistent data,
        for example, peers,leader,state,uuid
    '''

    def __init__(
            self,
            identity=None,
            state=None,
            peers={},
            leader=None,
            ip=None):
        """
        :param identity: uuid representing the identity of the peer
        :param state: defines the state of the peer
        :param peers: empty peers list which will be updated
        :param ip: ip of the peer
        """
        self.state = state
        self.peers = peers
        self.leader = None  # uuid
        # its better to use this than keep comparing uuid objects
        self.isLeader = False
        self.uuid = identity.hex
        self.ip = ip
        self.uuidObj = identity
