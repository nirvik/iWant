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
        self._pollClock = None
        self._eCallId = None
        self._alCallId = None
        self._pollId = None
        print ('UUID {0}'.format(self.book.uuid))

    def startProtocol(self):
        wait_for_peers = self.initialDelay
        wait_for_peers = wait_for_peers*self.factor
        self.transport.setTTL(5)
        self.transport.joinGroup(MCAST_ADDR[0])
        self._broadcast_identity()

        def response_from_peers():
            if self._none_alive_ack:
                print 'no response from peers at all'
                self._leader(self.book.uuid)
            self.d = threads.deferToThread(self._poll)

        temp_callID = reactor.callLater(wait_for_peers, response_from_peers)

    def _broadcast_identity(self):
        self.transport.write('0:{0}.{1}#'.format(self.book.uuid, self.book.leader), MCAST_ADDR)

    def _broadcast_leader_dead(self):
        self.transport.write('8:{0}#'.format(self.book.leader), MCAST_ADDR)

    def _send_id_to(self,addr):
        self.transport.write('0:{0}.{1}#'.format(self.book.uuid, self.book.leader), addr)

    def _re_election(self):
        self.transport.write('1:#', MCAST_ADDR)

    def _send_pong_to(self, addr):
        self.transport.write('7:pong#',addr)

    def _broadcast_winner(self):
        '''
            broadcasting winner message
        '''
        self.transport.write('6:{0}#'.format(self.book.leader), MCAST_ADDR)

    def _send_election_msg_to(self, addr):
        self.transport.write('2:#', addr)

    def _ping(self, addr):
        self.transport.write('4:ping#',self.book.peers[self.book.leader])

    def _send_alive_msg_to(self, addr):
        self.transport.write('5:#', addr)

    def _poll(self):
        '''
            Keep polling the server to test if its dead or alive
        '''
        if self._pollClock is None:
            from twisted.internet import reactor
            self._pollClock = reactor

        if self.book.leader != self.book.uuid and not self._election_started and self.book.leader!= '':
            print 'pinging {0}'.format(self.book.leader)
            address = self.book.peers[self.book.leader]
            self._ping(address)

            def ping_callback():
                if not self._ping_ack:
                    self.retries+=1
                    if self.retries >= self.maxRetries:
                        print 'FAILED {0}'.format(self.retries)
                        self._broadcast_leader_dead()
                        self._election()
                else:
                    self.retries = 0
                self._ping_ack = 0  # reset the ping_ack to 0

            self._pollClock.callLater(2, ping_callback)  # wait for 4 seconds to check if the leader replied

        self._pollId = self._pollClock.callLater(3,self._poll)  # ping the server every 3 seconds


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
            self._handle_ping(addr)

        elif key == 5:
            self._alive_handler()

        elif key == 6:
            leader = value
            self._new_leader_callback(leader)

        elif key == 7 :
            self._handle_pong()

        elif key == 8:
            leader = value
            self._remove_leader(leader)


    def _new_peers(self, peers, leader, addr):
        '''
            Add new peers and decide whether to accept them as leaders or bully them
        '''
        if peers != self.book.uuid:
            print 'PEER ADDED {0}'.format(peers)
            self._none_alive_ack = 0

            if peers not in self.book.peers:
                self.book.peers[peers] = addr
                self._send_id_to(addr)
                if leader == '' and self.book.leader=='':
                    self._re_election()
                else:
                    if leader!='' and self.book.leader=='':
                        if self.book.uuid < leader:
                            print ' gonna accept the leader : {0}'.format(leader)
                            self._new_leader_callback(leader)
                        elif self.book.uuid > leader:
                            print ' gonna bully the leader : {0}'.format(leader)
                            self._bully()
                    elif leader!='' and self.book.leader!='':
                        # if nodes have different leaders then have a re-election
                        self.book.leader = ''  # Conflict of leaders , kill it and elect a new leader
                        self._re_election()

    def _handle_ping(self,addr):
        self._send_pong_to(addr)

    def _remove_leader(self,leader):
        if leader == self.book.leader and leader in self.book.peers:
            print 'removing the leader'
            del self.book.peers[leader]
            self.book.leader = ''

    def _handle_pong(self):
        self._ping_ack = 1

    def _election(self):
        '''
            Sending election message to higher peers
            Every time there is an election reset the values of ack
        '''
        print ' Its time for election \n '
        self._election_started = 1
        requested_peers_list = filter(lambda x: x > self.book.uuid, self.book.peers.keys())
        for pid in requested_peers_list:
            self._send_election_msg_to(self.book.peers[pid])

        print requested_peers_list
        self.delay = min(self.maxDelay, self.delay*self.factor)
        print ' GONNA WAIT FOR {0} seconds for election result '.format(self.delay)

        def election_callback(no_response):
            print 'Fuck it , i won '
            self._leader(self.book.uuid)

        if self._eClock is None:
            from twisted.internet import reactor
            self._eClock = reactor

        self._eCallId = self._eClock.callLater(self.delay, election_callback, True)


    def _alive(self, addr):
        '''
            Responding to the election message from lower Peer ID , I am alive.
        '''
        print 'sending alive message to {0}'.format(addr)
        self._send_alive_msg_to(addr)

    def _alive_handler(self):
        '''
            Will be waiting for the winner message now
        '''
        #  rather it makes sense to cancel the election deferred
        if self._eCallId.active():
            self._eCallId.cancel()

        def wait_for_winner(no_response):
            if no_response:
                print 're-election everybody'
                self._re_election()

        alive_deferred = defer.Deferred()
        alive_deferred.addCallback(wait_for_winner)
        self.delay = min(self.maxDelay, self.delay*self.factor)
        print 'GONNA WAIT FOR {0} seconds for "winner msg" '.format(self.delay)
        if self._alClock is None:
            from twisted.internet import reactor
            self._alClock = reactor
        self._alCallId = self._alClock.callLater(self.delay, alive_deferred.callback, True)


    def _new_leader_callback(self, leader):
        '''
            This is a callback once the peers receive their new leader
        '''
        if self._eCallId is not None:
            if self._eCallId.active():
                self._eCallId.cancel()
        if self._alCallId is not None:
            if self._alCallId.active():
                self._alCallId.cancel()
        if leader not in self.book.peers and leader!=self.book.uuid:  # if winner message comes before the introduction message or (if the leader is not present the peers list and leader is not itself)
            self._broadcast_identity()
        else:
            self.book.leader = leader
            self.reset()
            print 'LEADER :{0}'.format(self.book.leader)


    def _leader(self, leader):
        '''
            This method is to assign you the leadership and broadcast everyone
        '''
        print ' Telling everbody that I am the winner '
        self.reset()
        self.book.leader = leader
        self._broadcast_winner()

    def _bully(self):
        '''
            broadcast a re-election event
        '''
        print 'Re Election \n '
        self._re_election()

    def reset(self):
        '''
            This resets all the values
        '''
        self._election_started = 0
        self.delay = self.initialDelay

if __name__ == '__main__':
    import random,os,sys
    try:
        book = CommonlogBook(uid=uuid.uuid1(), state=0)
        # book = CommonlogBook(random.randint(0,19),state=0)
        reactor.listenMulticast(MCAST_ADDR[1], CommonroomProtocol(book), listenMultiple=True)
        reactor.run()
    except KeyboardInterrupt:
        reactor.stop()
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
