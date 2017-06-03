from twisted.internet import reactor, threads, task
import time
import random
import string
from iwant.core.config import SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, MCAST_IP, MCAST_PORT
from iwant.core.constants import NEW_PEER, RE_ELECTION, ALIVE, \
    BCAST_LEDGER, HANDLE_PING, HANDLE_ALIVE, NEW_LEADER,\
    HANDLE_PONG, REMOVE_LEADER, PING, FACE_OFF, \
    SECRET_VAL, WITH_LEADER, WITHOUT_LEADER, DEAD
from iwant.core.messagebaker import bake, unbake
from iwant.core.protocols import ServerElectionFactory, PeerdiscoveryProtocol

MCAST_ADDR = (MCAST_IP, MCAST_PORT)


class EventHooker(object):
    __doc__ = """
            Registering custom event callbacks
    """

    def __init__(self):
        self.events = {}

    def bind(self, event, callback):
        '''
        Registers callbacks to an event
        :param event : string
        :param callback : function
        '''
        self.events[event] = callback

    def unbind(self, event):
        '''
        Detach events from the hooker
        :param event: string
        '''
        if event in self.events:
            del self.events[event]


class CommonroomProtocolException(Exception):

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        return 'Error [{0}] => {1}'.format(self.code, self.msg)


class CommonroomProtocol(PeerdiscoveryProtocol):
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

    def __init__(self, book, log):
        '''
            build the message codes
            :param book: CommonLogBook instance
        '''
        self.book = book
        self.log = log
        self.secret_value = None
        self.eventcontroller = EventHooker()
        self.eventcontroller.bind(NEW_PEER, self._new_peers)
        self.eventcontroller.bind(RE_ELECTION, self._re_election_event)
        self.eventcontroller.bind(ALIVE, self._alive)
        self.eventcontroller.bind(BCAST_LEDGER, self._manage_ledger)
        self.eventcontroller.bind(HANDLE_PING, self._handle_ping)
        self.eventcontroller.bind(HANDLE_ALIVE, self._alive_handler)
        self.eventcontroller.bind(NEW_LEADER, self._new_leader_callback)
        self.eventcontroller.bind(HANDLE_PONG, self._handle_pong)
        self.eventcontroller.bind(REMOVE_LEADER, self._remove_leader)
        self.eventcontroller.bind(FACE_OFF, self._face_off)
        self.eventcontroller.bind(DEAD, self._remove_peer)

        self._none_alive_ack = 1  # when no peers are present
        self._eln_ack = None  # waiting for election ack
        self._ping_ack = 0  # waiting for failure
        self._eClock = None
        self._alClock = None
        self._pollClock = None
        self._reelectionClock = None
        self._npClock = None  # new peer clock
        self._npCallId = None  # new peer call id
        self._eCallId = None
        self._alCallId = None
        self._pollId = None
        self._reelectionCallId = None
        self._eid = None
        self._addr = (self.book.ip, MCAST_PORT)
        self._latest_election_id = None
        self.buff = ''
        self.delimiter = '\r'
        self.log.msg('ID ', self.book.uuid)
        # print 'ID : ' + self.book.uuid
        reactor.addSystemEventTrigger("before", "shutdown", self.logout)

    def cancel_wait_for_peers_callback(self):
        if self._npCallId is not None:
            self.log.msg('Cancelling: wait for peers callback')
            self._npCallId.cancel()

    def cancel_election_callback(self):
        '''
            Donot send any Request for Vote messages to anyone
        '''
        if self._eCallId is not None:
            # print 'wait for I am alive: CANCELLED'
            self.log.msg('wait for I am alive: CANCELLED')
            self._eCallId.cancel()

    def cancel_alive_callback(self):
        if self._alCallId is not None:
            # print 'wait for I am winner: CANCELLED'
            self.log.msg('wait for I am winner: CANCELLED')
            self._alCallId.cancel()

    def cancel_election_commencement_callback(self):
        if self._reelectionCallId is not None:
            # print 'ECommencement message delivery: CANCELLED'
            self.log.msg('ECommencement message delivery: CANCELLED')
            self._reelectionCallId.cancel()

    def cancel_everything(self):
        # print '***** Cancelling the entire election ******'
        self.log.msg('Cancel all election timers')
        self.cancel_wait_for_peers_callback()
        self.cancel_election_callback()
        self.cancel_alive_callback()
        self.cancel_election_commencement_callback()
        self._eid = None
        # print '********************************************'

    @staticmethod
    def generate_election_id():
        return time.time()

    @staticmethod
    def generate_timeout():
        return random.uniform(1, 10)

    @staticmethod
    def generate_delay():
        return random.uniform(3, 6)

    @staticmethod
    def generate_secret(size=10, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    def startProtocol(self):
        """
        Join the multicast group and announce the identity
        and decide to become the leader if there is no response
        """
        self.book.peers[self.book.uuidObj] = self._addr
        # datagrams can traverse more than one router hop
        self.transport.setTTL(5)
        self.transport.joinGroup(MCAST_ADDR[0])
        self._broadcast_identity()
        self.log.msg('joining the multicast group and waiting for response')
        wait_for_response = 3

        def response_from_peers():
            self._eid = self.generate_election_id()
            self.log.msg('Announcing itself as the winner')
            self._leader(leader=self.book.uuidObj, eid=self._eid)

        self._npCallId = task.deferLater(
            reactor,
            wait_for_response,
            response_from_peers)
        self.d = threads.deferToThread(self._poll)

    def _broadcast_identity(self):
        self.log.msg('broadcast identity')
        msg = bake(
            NEW_PEER,
            identity=self.book.uuidObj,
            leader_id=self.book.leader)
        self.send(msg, MCAST_ADDR)

    def _broadcast_leader_dead(self):
        if self.book.leader:
            self.log.msg(
                'broadcast leader is dead: {0}'.format(
                    self.book.leader))
            msg = bake(REMOVE_LEADER, leader_id=self.book.leader)
            if self.book.leader in self.book.peers:
                del self.book.peers[self.book.leader]
            self.book.leader = None
            self.send(msg, MCAST_ADDR)
            # print 'Leader dead: Broadcast re-election'
            self.log.msg('Leader dead: Broadcast re-election')
            self._broadcast_re_election()

    def _broadcast_re_election(self):
        def election_timeout_callback():
            eid = self.generate_election_id()
            self.log.msg('broadcast re-election id {0}'.format(eid))
            msg = bake(RE_ELECTION, election_id=eid)
            self.send(msg, MCAST_ADDR)
        if self._reelectionClock is None:
            self._reelectionClock = reactor
        election_timeout = self.generate_timeout()
        self.log.msg('{0} timeout: ECommencement msg'.format(election_timeout))
        # print '{0} timeout: ECommencement msg'.format(election_timeout)
        # broadcast relection can be called twice if leader announces its death
        # and polling also determines leaders death
        self.cancel_election_commencement_callback()
        self._reelectionCallId = task.deferLater(
            reactor,
            election_timeout,
            election_timeout_callback)

    def _send_id_to(self, addr):
        '''
            Sending peer id to new peer
        '''
        self.log.msg('send id to {0}'.format(addr))
        msg = bake(
            NEW_PEER,
            identity=self.book.uuidObj,
            leader_id=self.book.leader)
        self.send(msg, addr)

    def _send_pong_to(self, addr):
        '''
            Prove that leader is alive
        '''
        # self.log.msg('send pong to {0}'.format(addr))
        msg = bake(HANDLE_PONG, secret_value=self.secret_value)
        self.send(msg, addr)

    def _broadcast_winner(self, eid):
        '''
            broadcasting winner message
        '''
        # # print 'Sending SECRET {0}'.format(self.secret_value)
        self.log.msg('Broadcasting winner for election id: {0} '.format(eid))
        msg = bake(
            NEW_LEADER,
            leader_id=self.book.leader,
            election_id=eid,
            secret_value=self.secret_value)
        self.send(msg, MCAST_ADDR)

    def _send_election_msg_to(self, peer_id, eid):
        self.log.msg('sending election message to {0}'.format(peer_id))
        addr = self.book.peers[peer_id]
        msg = bake(ALIVE, election_id=eid)
        self.send(msg, addr)

    def _ping(self, addr):
        # self.log.msg('sending ping to leader {0}'.format(addr))
        msg = bake(HANDLE_PING, ping=PING)
        self.send(msg, addr)  # might be a problem

    def _send_alive_msg_to(self, addr, eid):
        msg = bake(HANDLE_ALIVE, election_id=eid)
        self.send(msg, addr)

    def _broadcast_ledger(self, add_secret=False, just_sharing=False):
        ledger = self.book.peers
        if add_secret:
            # We add secret when we are sending the ledger to a new peer, so
            # that the peer can ping the leader and expect the secret value
            # print 'THE SECRET VALUE {0}'.format(self.secret_value)
            self.log.msg('Secret value sending:{0}'.format(self.secret_value))
            msg = bake(
                BCAST_LEDGER,
                leader_id=self.book.leader,
                ledger=ledger,
                secret_value=self.secret_value)
            self.send(msg, MCAST_ADDR)
        elif just_sharing is True:
            # This is necessary when the wrong winner is announced for the
            # election. We then just exchange ledger with each other and
            # organize a fresh new re-election
            self.log.msg('Wrong winner announced: Exchange ledger')
            msg = bake(
                BCAST_LEDGER,
                ledger=ledger,
                leader_id=None,
                secret_value=None)
            self.send(msg, MCAST_ADDR)
        else:
            # When split brain occurs, we exchange ledger and perform re-election
            # We cant really let all the peers to announce re-election. Lets
            # make only the leaders of different clusters announce the
            # re-election
            self.log.msg('Split Brain: Leaders only exchange ledger')
            msg = bake(
                BCAST_LEDGER,
                leader_id=self.book.leader,
                ledger=ledger,
                secret_value=None)
            self.send(msg, MCAST_ADDR)

    # def _send_secret_value(self, addr):
    #     '''
    #         Send secret value to addr only when a new peer enters
    #     '''
    #     # TODO: UNUSED
    #     msg = bake(SECRET_VAL, secret_value=self.secret.value)
    #     self.send(msg, addr)
    #     # elf.send(CommonroomMessage(SECRET_VAL, [self.secret.value]), addr)

    def _send_face_off(self, addr, with_leader=False, without_leader=False):
        '''
            Send a face off message: same election id but different winners
        '''
        if with_leader:
            self.log.msg('FACE OFF: WITH LEADER')
            msg = bake(FACE_OFF, with_leader=WITH_LEADER)
            self.send(msg, addr)
        else:
            self.log.msg('FACE OFF: WITHOUT LEADER')
            msg = bake(FACE_OFF, with_leader=WITHOUT_LEADER)
            self.send(msg, addr)

    def _dead(self):
        '''
            Announce dead message
        '''
        self.log.msg('Announce: Dead peer')
        msg = bake(
            DEAD,
            dead_uuid=self.book.uuidObj,
            secret_value=self.secret_value)
        self.send(msg, MCAST_ADDR)

    def isLeader(self):
        '''
            method to check if self is leader
        '''
        if self.book.leader == self.book.uuidObj:
            return True
        else:
            return False

    def leader_present(self):
        '''
           method to check if leader is present
        '''
        if self.book.leader:
            return True
        else:
            return False

    def _poll(self):
        '''
            Keep polling the server to test if its dead or alive
        '''
        if self._pollClock is None:
            from twisted.internet import reactor
            self._pollClock = reactor
        if not self.isLeader() and self.leader_present():
            def ping_callback():
                if not self._ping_ack:
                    self.retries += 1
                    if self.retries >= self.maxRetries:
                        # print 'FAILED {0}'.format(self.retries)
                        self.log.msg(
                            'PING FAILED: RETRIES {0}'.format(
                                self.retries))
                        self._broadcast_leader_dead()
                else:
                    self.retries = 0
                self._ping_ack = 0  # reset the ping_ack to 0

            # when leader is removed and we are present in this block, since
            # the polling process occuring concurrently
            try:
                leader_addr = self.book.peers[self.book.leader]
                self._ping(leader_addr)
                self._pollClock.callLater(
                    2,
                    ping_callback)  # wait for 2 seconds to check if the leader replied
            except Exception as e:
                # print e
                # print '@poll'
                self.log.msg(
                    'Poll: Exception occured: Leader died while polling:{0}'.format(e))
                self._broadcast_leader_dead()
        delay = self.generate_delay()
        self._pollId = self._pollClock.callLater(
            delay, self._poll)  # ping the server every 4 seconds

    # def periodic_reminder_from_leader(self):
    #     '''
    #         TODO: This is a kickass fucntion which will remind the peers about the leader periodicall and supply a new secret value
    #     '''
    #     if self.book.leader == self.book.uuidObj:
    #         self._remind_about_leader()
    #         reactor.callLater(6, self.periodic_reminder_from_leader)

    def _process_msg(self, req, addr):
        '''
            This acts as a router because it dispatches functions based on the event received
        '''
        key, value = unbake(message=req)
        if key in [NEW_PEER, ALIVE, HANDLE_PING, NEW_LEADER]:
            self.eventcontroller.events[key](data=value, addr=addr)
        else:
            self.eventcontroller.events[key](data=value)

    def _new_peers(self, data=None, addr=None):
        '''
            Add new peers and decide whether to accept them as leaders or bully them
            :param data: represents a list containing peer_uuid and leader_uuid
            :param addr: (ip,port) of the new peer
        '''
        if data is not None:
            peer = data['identity']
            leader = data['leader_id']

        if peer != self.book.uuidObj:
            self.cancel_wait_for_peers_callback()
            if peer not in self.book.peers:
                self.book.peers[peer] = addr
                if self.isLeader():
                    self._broadcast_ledger(add_secret=True)
                else:
                    # not self.book.leader:  # there are no leaders whatsoever
                    if not leader and not self.leader_present():
                        self._send_id_to(addr)
                        # print 'No leader: New peer entry: Cancel if any
                        # ongoing election: broadcast re-election'
                        self.log.msg(
                            'No leader: New peer entry: Cancel if any ongoing election: broadcast re-election')
                        self.cancel_everything()
                        self._broadcast_re_election()

    def _manage_ledger(self, data):
        '''
            If there is a newcomer or if there are multiple leaders,
            send them an updated copy of the ledger containing all the peers in the network
        '''
        just_sharing = False
        leader = data['leader_id']
        ledger = data['ledger']
        secret = data['secret_value']

        if leader is None and secret is None:
            just_sharing = True

        self.cancel_wait_for_peers_callback()

        # Ledger updation
        temp_ledger = self.book.peers.copy()
        temp_ledger.update(ledger)
        self.book.peers = temp_ledger

        for key, value in self.book.peers.iteritems():
            self.log.msg('{0} {1}'.format(key, value))

        if just_sharing is True:
            '''
                Exchange ledger to update peers list and then bully due to wrong winner of election
            '''
            pass

        elif not self.leader_present():
            '''
                Informing NEW PEER about leader and secret value
            '''
            # print 'accepting the leader with secret {0}'.format(secret)
            self.log.msg('accepting the leader with secret {0}'.format(secret))
            self.secret_value = secret
            self._new_leader_callback(leader=leader)

        elif self.isLeader() and leader and leader != self.book.leader:
            '''
                Split brain scenario
                If leader value shared is different from the current leader
            '''
            self._new_leader_callback(leader=leader)

    def _handle_ping(self, data, addr=None):
        '''
            Along with pong, also append the secret value
        '''
        self._send_pong_to(addr)

    def _remove_leader(self, data):
        """
            Todo: For removing leader, the announcing peer must also broadcast the previous electionId.
        """
        # if data is not None:
        # eader = data[0]
        leader = data['leader_id']

        if leader == self.book.leader and leader in self.book.peers:
            try:
                del self.book.peers[leader]
                self.book.leader = None
                self.secret_value = None
            except KeyError:
                raise CommonroomProtocolException(
                    3,
                    'Leader not present in the peers list. Invalid KeyError')

    def _remove_peer(self, data):
        if data is not None:
            # ead_peerId, authorized = data
            dead_peerId = data['dead_uuid']
            authorized = data['secret_value']
            if dead_peerId in self.book.peers:
                if authorized == self.secret_value:
                    # print '@election: Removing {0}'.format(dead_peerId)
                    self.log.msg('Removing dead peer: {0}'.format(dead_peerId))
                    del self.book.peers[dead_peerId]
                    if self.isLeader():
                        # the leader will tell the server daemon about the dead
                        # peer so that it can remove its file entries from its
                        # cache
                        self.notify_server(
                            peer_dead=True,
                            dead_peerId=dead_peerId)
                    if self.book.leader == dead_peerId:
                        # print '@removing peer'
                        self.log.msg('Removing Leader: Leader dead')
                        self._broadcast_leader_dead()
            else:
                raise CommonroomProtocolException(
                    2, 'User doesn\'t exist in the peers list')

    def _handle_pong(self, data=None):
        '''
            Here we check if the value sent by the leader is equal to the secret value shared right after winning the election
        '''
        self._ping_ack = 1
        if data is not None:
            # ecret = data[0]
            secret = data['secret_value']
            if secret != self.secret_value:
                # broadcast leader is dead
                # print 'MISMATCH {1} {0}'.format(secret, self.secret_value)
                self.log.msg(
                    'MISMATCH {1} {0}'.format(
                        secret,
                        self.secret_value))
                self._broadcast_leader_dead()

    def _re_election_event(self, data=None, eid=None):
        self.cancel_everything()
        election_id = eid
        if data is not None:
            election_id = data['election_id']

        if self._eid is None:
            # print 'New term: {0}'.format(election_id)
            self.log.msg('New term: {0}'.format(election_id))
            self._eid = election_id
            self._election(election_id)
        else:
            if election_id > self._eid:
                # print 'Cancel term: {0}'.format(self._eid)
                # print 'Updating term: {0}'.format(election_id)
                self.log.msg(
                    'Cancel term: {0}\nUpdating term: {1}'.format(
                        self._eid,
                        election_id))
                self.reset()
                self._eid = election_id
                self._election(election_id)

    def _election(self, eid):
        '''
            Sending election message to higher peers
            Every time there is an election reset the values of ack
        '''
        if self._eid == eid:
            requested_peers_list = filter(
                lambda x: x < self.book.uuidObj,
                self.book.peers.keys())
            # print 'Send Election Messages: INIT'
            self.log.msg('Send Election Messages: INIT')
            for peer in requested_peers_list:
                # print 'Sending Election msg to: {0}'.format(peer)
                self.log.msg('Sending Election msg to: {0}'.format(peer))
                self._send_election_msg_to(peer, eid)
            # print 'Sending Election Messages: Terminated'
            self.log.msg('Sending Election Messages: Terminated')
            self.delay = random.uniform(3, 5)

            def election_callback(election_id):
                # print 'Waited for response: Announcing itself as winner:
                # Waited {0}'.format(self.delay)
                self.log.msg(
                    'Waited for response: Announcing itself as winner: Waited {0}'.format(
                        self.delay))
                self._leader(self.book.uuidObj, election_id)

            self._eCallId = task.deferLater(
                reactor,
                self.delay,
                election_callback,
                eid)

    def _alive(self, data, addr=None):
        '''
            Responding to the election message from lower Peer ID , I am alive.
        '''
        eid = data['election_id']
        if self._eid == eid:
            # print 'Sending Alive Message: Lower peer: {0}'.format(addr)
            self.log.msg('Sending Alive Message: Lower peer: {0}'.format(addr))
            self._send_alive_msg_to(addr, eid)

    def _alive_handler(self, data):
        '''
            Gets an "Alive" message from higher peer.
            Will be waiting for the winner message now
        '''
        eid = data['election_id']
        if self._eid == eid:
            # print 'Got alive message: from higher peer'
            self.log.msg('Got alive message: from higher peer')
            self.cancel_election_callback()

            def wait_for_winner(no_response):
                if no_response:
                    # print '{0}: the alive call id '.format(self._alCallId)
                    # print 'no response, broadcast re-election'
                    self.log.msg(
                        '{0}: the alive call id: No response: Broadcast Re-Election'.format(self._alCallId))
                    self._broadcast_re_election()

            self.delay = random.uniform(8, 10)  # self.generate_delay()
            # print '{0} timeout : no i m winner message: broadcast
            # re-election'.format(self.delay)
            self.log.msg(
                '{0} timeout : no i m winner message: broadcast re-election'.format(self.delay))
            if self._alCallId:
                '''
                    Every higher peer will send an alive message.
                    Lets say that the peer receives 20 alive messages from higher peer.
                    It schedules 20 callbacks for future if we dont cancel them.
                    Hence, we cancel the future callback as soon as we receive multiple alive messages
                '''
                self._alCallId.cancel()
            self._alCallId = task.deferLater(
                reactor,
                self.delay,
                wait_for_winner,
                True)

    def _new_leader_callback(self, data=None, leader=None, addr=None):
        '''
            This is a callback once the peers receive their new leader
            If there is a cluster which gets the result of a wrong election id ,
            then the leader of the cluster must broadcast the ledger.
        '''
        eid = None
        secret = None
        if data is not None:
            leader = data['leader_id']
            eid = data['election_id']
            secret = data['secret_value']

        if eid is None:
            '''
                Post election time
            '''
            if self.book.uuidObj < leader:
                # print 'about to bully {0} {1}'.format(self.book.uuidObj,
                # leader)
                self.log.msg(
                    'about to bully {0} {1}'.format(
                        self.book.uuidObj,
                        leader))
                self._bully()
            elif self.isLeader():
                pass
            else:
                self.book.leader = leader
                # print 'register leader {0}'.format(self.book.leader)
                self.log.msg('register leader {0}'.format(self.book.leader))
                self.notify_server(leader_change=True)

        elif self._eid != eid:
            '''
                Random peer anounces itself as the winner and passes incorrect election ID
                last stage of election

                Therefore, we can assume that there is atleast one leader in the network
            '''
            # print 'WRONG ELEC ID {0} {1}'.format(self._eid, eid)
            self.log.msg('WRONG ELEC ID {0} {1}'.format(self._eid, eid))
            if self.leader_present():
                if self.isLeader():
                    self._send_face_off(addr, with_leader=True)
                    # two diff leaders will bcast their ledger
                    self._broadcast_ledger()
                elif self.retries > 0:
                    # Its possible that the leader is already dead , but the peers think that leader is alive
                    # based on the retries, we can slightly guess that the
                    # leader might not be present [Not a good way]
                    self._broadcast_ledger(just_sharing=True)
                    # request to tell the opposite peer to send its peers list
                    # , i.e , ledger
                    self._send_face_off(addr, without_leader=True)
            else:
                self._broadcast_ledger(just_sharing=True)
                self._send_face_off(addr, without_leader=True)

        elif self._eid == eid:
            '''
                Last stage of election
            '''
            self.book.leader = leader
            self.secret_value = secret
            self.cancel_election_callback()
            self.cancel_alive_callback()
            # print '********* Conclusion **************'
            # print 'LEADER :{0}\t EID : {1}'.format(self.book.leader,
            # self._eid)
            self.log.msg(
                '[Election Conlusion]: Leader {0} \t Election id: {1}'.format(
                    self.book.leader,
                    self._eid))
            if self.book.uuidObj < self.book.leader:
                """
                 The problem arises when a new peer joins and becomes a part of an election without having the peers list.
                 We assume that peers who participate in particular election have the same set of peers list. If they dont, then multiple winners will be announced for that election, because the peer with no peers list will declare itself as the winner and so will the actual leader of the election.
                 Therefore , we can say that the faulty peer will have no peers list whatsoever.
                 We also assume that a new peer can never become a leader unless he is the oldest peer in the network
                """
                self._broadcast_ledger(just_sharing=True)
                # print 'Election Last Stage: New peer annouces itself as the
                # leader: bully: re-election'
                self.log.msg(
                    'Election Last Stage: New peer annouces itself as the leader: bully: re-election')
                self._bully()

            # print 'CLOSING ELECTION: {0}'.format(self._eid)
            self.log.msg('CLOSING ELECTION: {0}'.format(self._eid))
            self._latest_election_id = self._eid
            self._eid = None  # this might create a huge problem
            # print '********** Election Ended **************'
            self.log.msg('Election ended')
            self.notify_server(leader_change=True)

    def _leader(self, leader, eid):
        '''
            This method is to assign you the leadership and broadcast everyone
        '''
        if self._eid == eid:
            self.cancel_wait_for_peers_callback()
            self.book.leader = leader
            size_value = random.randint(6, 10)
            self.secret_value = self.generate_secret(size_value)
            self._broadcast_winner(eid)

    def _bully(self):
        '''
            broadcast a re-election event
        '''
        # print 'bullying then relection'
        self.log.msg('bullying then relection')
        self._broadcast_re_election()

    def _face_off(self, data):
        '''
            Face off message is usually received by an unusual leader
        '''
        # print 'FACE OFF: {0}'.format(data)
        self.log.msg('Face off:{0}'.format(data))
        if data['with_leader'] == WITH_LEADER:
            '''
                Challenge from another leader
            '''
            self._broadcast_ledger()
        else:
            '''
                Challenge from other non leader peers
            '''
            self._broadcast_ledger(just_sharing=True)
            # print 'Face off: without leader: broadcast re-election'
            self.log.msg('Face off: without leader: broadcast re-election')
            self._broadcast_re_election()

    def notify_server(
            self,
            leader_change=False,
            peer_dead=False,
            dead_peerId=None):
        '''
            notifying the server as soon as there is a leader change
        '''
        if self.book.leader in self.book.peers:
            leader_host = self.book.peers[self.book.leader][0]
            leader_port = SERVER_DAEMON_PORT
            if leader_change:
                # print 'norifying the server daemon about the leader
                # {0}'.format(self.book.leader)
                self.log.msg(
                    'notifying the server daemon about the leader {0}'.format(
                        self.book.leader))
                factory = ServerElectionFactory(leader_host, leader_port)
            elif peer_dead:
                # print '@election : telling server {0} is
                # dead'.format(dead_peerId)
                self.log.msg(
                    '@election : telling server {0} is dead'.format(dead_peerId))
                factory = ServerElectionFactory(
                    leader_host,
                    leader_port,
                    dead_peer=dead_peerId)
            reactor.connectTCP(SERVER_DAEMON_HOST, SERVER_DAEMON_PORT, factory)

    def reset(self):
        '''
            This resets all the values
        '''
        # self.delay = self.initialDelay
        pass

    def logout(self):
        # Announce dead with your uuid and the latest election id
        self.log.msg('Announce dead with your uuid and the latest election id')
        self._dead()
        print 'shutting down ... its been an honour serving you!'


# if __name__ == '__main__':
#    import random,os,sys
#    try:
#        from netifaces import interfaces, ifaddresses, AF_INET
#
#        def ip4_addresses():
#            ip_list = []
#            for interface in interfaces():
#                try:
#                    for link in ifaddresses(interface)[AF_INET]:
#                        ip_list.append(link['addr'])
#                except:
#                    pass
#            return ip_list
#        ips = ip4_addresses()
#        # print ips
#        ip = input('Enter index of ip addr:')
#        timeuuid = time_uuid.TimeUUID.with_utcnow()
#        book = CommonlogBook(identity=timeuuid, state=0, ip = ips[ip-1])
#        reactor.listenMulticast(MCAST_ADDR[1], CommonroomProtocol(book), listenMultiple=True)
#        reactor.run()
#    except KeyboardInterrupt:
#        reactor.stop()
#        try:
#            sys.exit(0)
#        except SystemExit:
#            os._exit(0)
