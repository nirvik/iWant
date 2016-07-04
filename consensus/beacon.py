from twisted.internet import reactor, defer, threads, task
from twisted.internet.protocol import DatagramProtocol, Protocol
import uuid
import logging
import netifaces as ni
import time
import ast
from communication.message import *
MCAST_ADDR = ('228.0.0.5', 8005)

class CommonlogBook(object):
    __doc__ = '''
        This is a book which will store all the persistent data,
        for example, peers,leader,state,uuid
    '''
    def __init__(self, identity=None, state=None, peers={}, leader=None, ip=None):

        self.state = state
        self.peers = peers
        self.leader = ''  # uuid
        self.isLeader = False
        self.uuid = identity.hex
        self.ip = ip

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
        '''
            build the message codes
        '''
        self.message_codes = {  # Haven't used it properly yet
            0: self._new_peers,
            1: self._re_election_event,
            2: self._alive,
            3: self._manage_ledger,
            4: self._handle_ping,
            5: self._alive_handler,
            6: self._new_leader_callback,
            7: self._handle_pong,
            8: self._remove_leader
        }
        self.buff = ''
        self._none_alive_ack = 1  # when no peers are present
        self._eln_ack = None  # waiting for election ack
        self._ping_ack = 0  # waiting for failure
        self._eClock = None
        self._alClock = None
        self._pollClock = None
        self._npClock = None  # new peer clock
        self._npCallId = None  # new peer call id
        self._eCallId = None
        self._alCallId = None
        self._pollId = None
        self._eid = 0.0
        self._addr = (self.book.ip, 8005)
        print ('UUID {0}'.format(self.book.uuid))
        print self._addr

    def startProtocol(self):
        self.book.peers[self.book.uuid] = self._addr
        wait_for_peers = self.initialDelay
        wait_for_peers = wait_for_peers*self.factor
        self.transport.setTTL(5)
        self.transport.joinGroup(MCAST_ADDR[0])
        self._broadcast_identity()

        def response_from_peers():
            self._eid = time.time()
            self._leader(leader=self.book.uuid, eid=self._eid)

        if self._npClock is None:
            from twisted.internet import reactor
            self._npClock = reactor
        self._npCallId = self._npClock.callLater(wait_for_peers, response_from_peers)
        self.d = threads.deferToThread(self._poll)

    def _broadcast_identity(self):
        self.send(FlashMessage(0,[self.book.uuid,self.book.leader]),MCAST_ADDR)

    def _broadcast_leader_dead(self):
        self.send(FlashMessage(8,[self.book.leader]),MCAST_ADDR)

    def _broadcast_re_election(self):
        eid = repr(time.time())
        self.send(FlashMessage(1,[eid]),MCAST_ADDR)

    def _send_id_to(self,addr):
        self.send(FlashMessage(0,[self.book.uuid,self.book.leader]),addr)

    def _send_pong_to(self, addr):
        self.send(FlashMessage(7,['pong']),addr)

    def _broadcast_winner(self,eid):
        '''
            broadcasting winner message
        '''
        self.send(FlashMessage(6,[self.book.leader,repr(eid)]),MCAST_ADDR)

    def _send_election_msg_to(self,pid):
        eid = repr(self._eid)
        addr = self.book.peers[pid]
        self.send(FlashMessage(2,[eid]),addr)

    def _ping(self, addr):
        self.send(FlashMessage(4,['ping']),addr) # might be a problem

    def _send_alive_msg_to(self, addr):
        eid = repr(self._eid)
        self.send(FlashMessage(5,[eid]),addr)

    def _broadcast_ledger(self):
        ledger = str(self.book.peers)
        self.send(FlashMessage(3,[self.book.leader,ledger]),MCAST_ADDR)

    def send(self,msgObj,addr):
        self.transport.write(str(msgObj),addr)

    def _poll(self):
        '''
            Keep polling the server to test if its dead or alive
        '''
        if self._pollClock is None:
            from twisted.internet import reactor
            self._pollClock = reactor

        if self.book.leader != self.book.uuid and self.book.leader!= '':
            print 'pinging leader : {0}'.format(self.book.leader)
            address = self.book.peers[self.book.leader]
            self._ping(address)

            def ping_callback():
                if not self._ping_ack:
                    self.retries+=1
                    if self.retries >= self.maxRetries:
                        print 'FAILED {0}'.format(self.retries)
                        self._broadcast_leader_dead()
                        self._broadcast_re_election()
                else:
                    self.retries = 0
                self._ping_ack = 0  # reset the ping_ack to 0

            self._pollClock.callLater(2, ping_callback)  # wait for 4 seconds to check if the leader replied

        self._pollId = self._pollClock.callLater(4,self._poll)  # ping the server every 3 seconds


    def escape_hash_sign(self, string):
        return string.replace('#', '')

    def datagramReceived(self, datagram, addr):
        for dat in datagram:
            self.buff += dat
            if dat == '#':
                req_str = self.escape_hash_sign(self.buff)
                self.buff = ''
                #self._parse_incoming_request(req_str, addr)
                self._process_msg(req_str,addr)
        self.buff = ''

    def _process_msg(self,req,addr):
        msg = FlashMessage(message=req)
        if msg.key in [0,2,4,6]:
            self.message_codes[msg.key](data=msg.data,addr=addr)
        else:
            self.message_codes[msg.key](data=msg.data)

    def _new_peers(self,data=None, peer=None, leader=None, addr=None):
        '''
            Add new peers and decide whether to accept them as leaders or bully them
        '''
        if data is not None:
            peer , leader = data

        if peer != self.book.uuid:
            #print 'PEER ADDED {0}'.format(peer)
            if self._npCallId is not None:
                if self._npCallId.active():
                    self._npCallId.cancel()

            if peer not in self.book.peers:
                self.book.peers[peer] = addr
                if self.book.leader != '':
                    if self.book.leader == self.book.uuid:  # if leader , send the ledger
                        self._broadcast_ledger()
                else:
                    if leader == '':  # there are no leaders whatsoever
                        self._send_id_to(addr)
                        self._broadcast_re_election()

    def _manage_ledger(self,data=None, ledger=None, leader=None):
        '''
            If there is a newcomer or if there are multiple leaders,
            send them an updated copy of the ledger containing all the peers in the network
        '''
        if data is not None:
            ledger , leader = data
        if self._npCallId is not None:
            if self._npCallId.active():
                self._npCallId.cancel()

        ledger = ast.literal_eval(ledger)
        temp_ledger = self.book.peers.copy()
        temp_ledger.update(ledger)
        self.book.peers = temp_ledger
        print '#########################'
        for key,value in self.book.peers.iteritems():
            print  key , value
        print '#########################'

        if self.book.leader == '' or (self.book.leader == self.book.uuid and leader!=''):
            self._new_leader_callback(leader=leader)

    def _handle_ping(self, data=None, addr=None):
        self._send_pong_to(addr)

    def _remove_leader(self, data=None, leader=None):
        if data is not None:
            leader = data[0]
        if leader == self.book.leader and leader in self.book.peers:
            print 'REMOVING LEADER: {0}'.format(leader)
            del self.book.peers[leader]
            self.book.leader = ''

    def _handle_pong(self, data=None):
        self._ping_ack = 1

    def _re_election_event(self,data=None, eid=None):
        if data is not None:
            eid = data[0]
        if self._eid is None:
            print 'NEW ELECTION COMMENCEMENT : {0}'.format(eid)
            self._eid = eid
            self._election(eid)
        else:
            if eid > self._eid:
                print 'CANCEL ELECTION {0}'.format(self._eid)
                self._eid = eid
                self.delay = 1
                if self._eCallId is not None:
                    if self._eCallId.active():
                        self._eCallId.cancel()

                if self._alCallId is not None:
                    if self._alCallId.active():
                        self._alCallId.cancel()

                self._election(eid)

    def _election(self,eid):
        '''
            Sending election message to higher peers
            Every time there is an election reset the values of ack
        '''
        eid = data[0]
        if self._eid == eid:
            requested_peers_list = filter(lambda x: x > self.book.uuid, self.book.peers.keys())
            for peer in requested_peers_list:
                self._send_election_msg_to(peer)

            self.delay = min(self.maxDelay, self.delay*self.factor)

            def election_callback(election_id):
                self._leader(self.book.uuid,election_id)

            if self._eClock is None:
                from twisted.internet import reactor
                self._eClock = reactor
            self._eCallId = self._eClock.callLater(self.delay, election_callback, eid)


    def _alive(self, data=None, eid=None, addr=None):
        '''
            Responding to the election message from lower Peer ID , I am alive.
        '''
        if data is not None:
            eid , addr = data
        if self._eid == eid:
            self._send_alive_msg_to(addr)

    def _alive_handler(self, data=None, eid=None):
        '''
            Will be waiting for the winner message now
        '''
        if data is not None:
            eid = data[0]
        if self._eid == eid:
            if self._eCallId.active():
                self._eCallId.cancel()

            def wait_for_winner(no_response):
                if no_response:
                    self._broadcast_re_election()

            alive_deferred = defer.Deferred()
            alive_deferred.addCallback(wait_for_winner)
            self.delay = min(self.maxDelay, self.delay*self.factor)
            if self._alClock is None:
                from twisted.internet import reactor
                self._alClock = reactor
            self._alCallId = self._alClock.callLater(self.delay, alive_deferred.callback, True)

    def _new_leader_callback(self, data=None, leader=None, eid=None, addr=None):
        '''
            This is a callback once the peers receive their new leader
            If there is a cluster which gets the result of a wrong election id ,
            then the leader of the cluster must broadcast the ledger.
        '''
        if data is not None:
            leader, eid = data

        if eid == None:
            if self.book.uuid > leader:
                self._bully()
            else:
                self.book.leader = leader

        elif self._eid != eid:
            print 'WRONG ELEC ID {0}'.format(self._eid,eid)
            self._broadcast_ledger()  # two diff leaders will bcast their ledger

        elif self._eid == eid:
            self.book.leader = leader
            if self._eCallId is not None:
                if self._eCallId.active():
                    self._eCallId.cancel()
            if self._alCallId is not None:
                if self._alCallId.active():
                    self._alCallId.cancel()
            if self.book.uuid > self.book.leader:
                # the new peer has a higher id than leader but doesn't know anyone
                # therefore , he will broadcast his id , get the ledger and contest election
                self._broadcast_identity()
            print 'LEADER :{0}\t EID : {1}'.format(self.book.leader,self._eid)
            print 'CLOSING ELECTION: {0}'.format(self._eid)
            self._eid = None


    def _leader(self, leader, eid):
        '''
            This method is to assign you the leadership and broadcast everyone
        '''
        if self._eid == eid:
            self.book.leader = leader
            self._broadcast_winner(eid)

    def _bully(self):
        '''
            broadcast a re-election event
        '''
        self._broadcast_re_election()

    def reset(self):
        '''
            This resets all the values
        '''
        self.delay = self.initialDelay



if __name__ == '__main__':
    import random,os,sys
    try:
        from netifaces import interfaces, ifaddresses, AF_INET

        def ip4_addresses():
            ip_list = []
            for interface in interfaces():
                try:
                    for link in ifaddresses(interface)[AF_INET]:
                        ip_list.append(link['addr'])
                except:
                    pass
            return ip_list
        ips = ip4_addresses()
        print ips
        ip = input('Enter index of ip addr:')
        book = CommonlogBook(identity=uuid.uuid1(), state=0, ip = ips[ip-1])
        reactor.listenMulticast(MCAST_ADDR[1], CommonroomProtocol(book), listenMultiple=True)
        reactor.run()
    except KeyboardInterrupt:
        reactor.stop()
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
