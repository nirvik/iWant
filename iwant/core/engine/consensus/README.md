# Consensus

## How does it work ?  

1. Peer is assigned a uuid based on timestamp. 
2. On joining the network, the peer broadcasts its ID. 
3. If the peer doesn't receive any response, it broadcasts itself as the winner( Winner message ) 
4. If there are other peers in the network, they add the new peer in their peers list. 
    - If there is a leader in the network, the leader sends the entire list of peers along with a secret value to the new peer 
    - Whereas, if there is no leader in the network, every peer will send its identity to the new peer and announce election 
5. If the new peer receives the peers list from the leader, it updates its own peer list and registers the leader id as the leader along with the secret value. 
6. If 5 doesnt happen, then each peer broadcasts a fresh election in a randomized timeout fashion. 
    - Whichever election id gets annouced first will be held and the rest will be cancelled 
7. The election occurs in a [bully algorithm](https://en.wikipedia.org/wiki/Bully_algorithm) style. 
8. When the leader wins, it adds a secret value field to its "winner" announcement message. Reason for the secret message will be mentioned next.
9. The peers will then register their new leader and keep pinging the leader in randomized intervals. 
    - The leader will respond with a pong message along with the secret value. 
    - This scenario might occur where leader crashes/exits and comes back to network again before the peers realize that the leader was dead for sometime. The "leader" will have no idea what secret value to send back to peer's ping request. 
    - When the leader sends the wrong secret value as response in the pong message, the peers again announce re-election in randomized timeout fashion. Since, the leader crashed, it will have no idea about the peers in the network and behave like a new peer in the network.  
10. On registering the leader, we will inform our local server daemon about the new leader. 

## Winning criteria 

The oldest peer (peer ID) will win the election. The peer ID is generated from the system timestamp.


## Split Brain

Split brain is a situation where there are __multiple clusters in the same network but they dont really know about their presence__. But there are situations where clusters can detect their presence. One such situation is broadcasting the winner of the election which reaches a separate cluster. Well, in these kind of situations, one of the leaders will send a __face off message__ to the leader of other cluster and will broadcast its peers list. The leader of the other cluster will respond by broadcasting its own peers list. All the peers in the network then combines the peers list shared by the leaders of different clusters and holds another fair re-election.


## When the leader quits and joins back before the peers even detect that the leader was unavailable for sometime? 
Well, why should the peers be bothered even if the leader died for a second?  
All the metadata regarding files shared by peers is available only with the leader, till its alive. If the leader dies in between and resurrects within a second, the leader has still lost all the data shared by the peers.  
We tend to solve this problem by pinging the leader with a secret value that is shared at the time when leader wins the election. The leader appends a secret value to the the winner message, so that when the peers ping their leader, the leader will reply back with that secret value to prove its authenticity. Its like maintaining a session. When the leader dies and resurrects, it will have no idea about the secret value shared with the peers. This leads to the confirmation
that the leader has resurrected and has no data, therefore there will be a re-election.  This means, when a new peer joins, the leader will send the peer list along with the secret value.  Can we make it more secure ?? Sure, we can set a time interval, where the leader updates the secret value among peers.

##  When should the leader announce the secret value? 
1. When a new peer joins, the leader sends a list of peers along with the secret value to the new peer. 
2. The leader broadcasts the secret value when it wins the election. 

##  When is the secret value invalidated? 
We set the secret value to ``` None ``` when the leader is dead or when the leader pongs back the incorrect secret value.
