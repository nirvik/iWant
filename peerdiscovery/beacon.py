from twisted.internet import reactor, defer, threads, task
from twisted.internet.protocol import DatagramProtocol, Protocol
import uuid
import logging

MCAST_ADDR = ('228.0.0.5', 8005)
port_multicast = 8006
port_ping = 8009

class CommonlogBook(object):
    __doc__ = '''
        This is a book which will store all the persistent data,
        for example, peers,leader,state,uuid
    '''
    def __init__(self, uid=None, state=None, peers={}, leader=None):

        self.state = state
        self.peers = peers
        self.leader = ''  # uuid
        self.isLeader = False
        uuid_str = str(uid)
        self.uuid = uuid.UUID(uuid_str).hex

class CommonroomProtocol(DatagramProtocol):
    __doc__ = '''
        Commonroom multicasts the winner
        Commonroom multicasts its ID
    '''
    maxDelay = 3600
    initialDelay = 1.0
    factor = 2.7182818284590451
    delay = initialDelay
    retries = 0
    maxRetries = 3
    _callID = None
    clock = None
    continueTrying = 1

    def __init__(self, book):
        self.book = book
        self.message_codes = {  # Haven't used it properly yet
            0: self._new_peers,
            1: self._election,
            2: self._alive,
            3: self._leader,
            4: self._bully
        }
        self.buff = ''
        self._none_alive_ack = 1  # when no peers are present
        self._eln_ack = None  # waiting for election ack
        self._ping_ack = 0  # waiting for failure
        self._eClock = None
        self._alClock = None
        self._eCallId = None
        self._alCallId = None
        print ('UUID {0}'.format(self.book.uuid))

    def startProtocol(self):
        wait_for_peers = self.initialDelay
        wait_for_peers = wait_for_peers*self.factor
        wait_for_peers = random.normalvariate(wait_for_peers, wait_for_peers*self.jitter)
        self.transport.setTTL(5)
        self.transport.joinGroup(MCAST_ADDR[0])
        self.transport.write('0:{0}.{1}#'.format(self.book.uuid, self.book.leader), MCAST_ADDR)

        def response_from_peers():
            if self._none_alive_ack:
                self._leader(self.book.uuid)
            self.d = threads.deferToThread(self._poll)

        temp_callID = reactor.callLater(wait_for_peers, response_from_peers)

    def _poll(self):
        '''
            Keep polling the server to test if its dead or alive
        '''
        if self.book.leader != self.book.uuid:
            print 'pinging {0}'.format(self.book.leader)
            self.transport.write('4:ping',self.book.peers[self.book.leader])

            def ping_callback():
                if not self._ping_ack:
                    self.retries+=1
                    if self.retries > self.maxRetries:
                        print 'FAILED {0}'.format(self.retries)
                        l.stop()
                        self._election()
                else:
                    self.retries = 0
                self._ping_ack = 0  # reset the ping_ack to 0

            reactor.callLater(4, ping_callback)  # wait for 4 seconds to check if the leader replied

        reactor.callLater(self._poll,20)  # ping the server every 20 seconds

    def escape_hash_sign(self, string):
        return string.replace('#', '')

    def datagramReceived(self, datagram, addr):
        for dat in datagram:
            self.buff += dat
            if dat == '#':
                req_str = self.escape_hash_sign(self.buff)
                self.buff = ''
                self._parse_incoming_request(req_str, addr)
        self.buff = ''

    def _parse_incoming_request(self, req, addr):
        '''
            message parser
        '''
        data = req.split(':')
        key = int(data[0])
        value = data[1]

        if key == 0:
            pid, leader = value.split('.')
            self._new_peers(pid, leader, addr)

        elif key == 1:
            self._election()

        elif key == 2:
            self._alive(addr)

        elif key == 3:
            self.alive_ack = 1
            leader = value
            self.message_codes[key](leader)

        elif key == 4:
            self._handle_ping_ack()

        elif key == 5:
            self._alive_handler()

        elif key == 6:
            leader = value
            self._new_leader_callback(leader)

    def _new_peers(self, peers, leader, addr):
        '''
            Add new peers and decide whether to accept them as leaders or bully them
        '''
        if peers != self.book.uuid:
            self._none_alive_ack = 0

            if peers not in self.book.peers:
                self.book.peers[peers] = addr
                self.transport.write('0:{0}.{1}#'.format(self.book.uuid, self.book.leader), MCAST_ADDR)
                if leader == '' and self.book.leader=='':
                    self._election()
                else:
                    if leader!='' and self.book.leader=='':
                        if self.book.uuid < leader:
                            self._new_leader_callback(leader)
                        elif self.book.uuid > leader:
                            self._bully()
                    # or else they have the same leader

    def _handle_ping_ack(self):
        self._ping_ack = 1

    def _election(self):
        '''
            Sending election message to higher peers
            Every time there is an election reset the values of ack
        '''
        self.reset()
        election_deferred = defer.Deferred()
        election_deferred.addCallback(self._election_callback)
        requested_peers_list = filter(lambda x: x > self.book.uuid, self.book.peers.keys())
        for pid in requested_peers_list:
            self.transport.write('2:#', self.book.peers[pid])

        self.delay = min(self.maxDelay, self.delay*self.factor)
        if self._eClock is None:
            from twisted.internet import reactor
            self._eClock = reactor

        self._eCallId = self._eClock.callLater(self.delay, election_deferred.callback,
                (lambda : self._eln_ack is None)())

    def _election_callback(won):
        if won:
            self._leader(self.book.uuid)

    def _alive(self, addr):
        '''
            Responding to the election message from lower Peer ID , I am alive.
        '''
        print 'sending alive message to {0}'.format(addr)
        self.transport.write('5:#', addr)

    def _alive_handler(self):
        '''
            Will be waiting for the winner message now
        '''
        self._eln_ack = 1  # cannot be leader now
        alive_deferred = defer.Deferred()
        alive_deferred.addCallback(self._wait_for_winner)
        self.delay = min(self.maxDelay, self.delay*self.factor)
        reactor.callLater(self.delay, alive_deferred.callback,True)

    def _wait_for_winner(no_response):
        if no_response:
            self._election()

    def _new_leader_callback(self, leader):
        '''
            This is a callback once the peers receive their new leader
        '''
        self.reset()
        self.book.leader = leader
        print 'LEADER :{0}'.format(self.book.leader)

    def _winner(self):
        '''
            broadcasting winner message
        '''
        self.transport.write('6:{0}#'.format(self.book.leader), MCAST_ADDR)

    def _leader(self, leader):
        '''
            This method is to assign you the leadership and broadcast everyone
        '''
        self.reset()
        self.book.leader = leader
        self._winner()

    def _bully(self):
        '''
            broadcast a re-election event
        '''
        self.transport.write('1:#', MCAST_ADDR)

    def reset(self):
        '''
            This resets all the values
        '''
        self._eln_ack = None
        self.delay = self.initialDelay
        self._eCallId.cancel()
        self._alCallId.cancel()

if __name__ == '__main__':
    import random
    book = CommonlogBook(uid=uuid.uuid1(), state=0)
    # book = CommonlogBook(random.randint(0,19),state=0)
    reactor.listenMulticast(MCAST_ADDR[1], CommonroomProtocol(book), listenMultiple=True)
    reactor.run()
