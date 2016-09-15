# Almighty Consensus

## What's the winning criteria ?

Each peer is assigned an identity. This assignment is based on the time at which the peer joins.  So, the oldest peer will be the one who will win the election. There is no way in hell the new peer can outvote the oldest peer. NO WAY !



I will be listing down scenarios along with the possible solution.

* What happens during a split brain situation ? As in , even if you detect a split brain, what does the consensus do?  
Split brain is a situation where there are multiple clusters in the same network but they dont really know about their presence. But there are situations where clusters can detect their presence. One such situation is broadcasting the winner of the election which reaches a separate cluster. Well, in these kind of situations, one of the leaders will send a face off message to the leader of other cluster and will broadcast its peers list. The leader of the other cluster will respond by broadcasting its own peers list. All the peers in the network then combines the peers list shared by the leaders of different clusters and holds another fair re-election.

* What if the leader is dead when a different leader sends a face off message?  
Havent thought about it yet 

* What happens when the leader quits and joins back before the peers even detect that the leader was unavailable for sometime?  
Well, why should the peers be bothered even if the leader died for less than a second. The answer is, all the data about the files shared by peers is available only with the leader till its alive. If the leader dies in between and resurrects within a second , the leader has still lost all the data shared by the peers.  
We tend to solve this problem by pinging the leader with a secret value that is shared at the time when leader wins the election. The winner appends a secret value with the winner message, so that when the peers ping their leader, the leader will reply back with that secret value to prove its authenticity. Its like maintaining a session. When the leader dies and resurrects, it will have no idea about the secret value shared with the peers. This leads to the confirmation
that the leader has resurrected and has no data, therefore there will be a re-election.  This means, when a new peer joins, the leader will send the peer list along with the secret value.  Can we make it more secure ?? Sure, we can set a time interval, where the leader updates the secret value among peers.

* When should the leader announce the secret value?  
The leader will send the secret value individually when a new peer enters and broadcast the secret value when the peer wins the election.

* So, we also have to invalidate the secret value at some point of time, right?  
Yes , we do. We set the secret value to ```python None ``` when the leader is dead or when the leader pongs back the incorrect secret value.

* According to your consensus, if a new peer joins and the leader is "alive"(i.e the peers think that the leader is alive), the leader is the only one who sends the peers list to the joining peer. Haa, so what happens when the leader is dead and a new peer joins and none of the peers have detected that the leader is actually dead?  
Well yeah ! it can potentially lead to a lot of problems. In fact, it can get a lot worse if the new peer becomes the leader. Lets see how!  
1. Leader just died  
2. New peer joins  
3. Others dont know leader is dead yet  
    * None of them tell the new peer about the leader  
4. Others recieve new peer details and append it to their ledger  
5. They detect leader is dead  
6. New re-election announced with new peer included. Mind it, the new peer still has no idea who is present in the network as it didnt recieve the peers list(ledger) yet.  
7. Now, new peer and the other peers share the same election ID.  
8. The new peer declares itself as the winner as it thinks that nobody is in the network.  
9. BUT , the oldest peer in the network will always win the election and declare itself as the winner.  
10. So WOW! we are having 2 leaders with same election ID but different secret values ? hahaha, thats pretty embarassing for our consensus.  
11. Well, when that happens, the conflicting leaders will brodcast their peers list, that means the new peer will send its empty/half-empty peers list and the old peer will send its peers list.  
12. All the peers will then combine both the peers list from both the potential leaders and then announce a fresh new re-election.  
13. This time a fair election is held with all the peers having a consistent peers list because of which only one LEADER will be selected.  

* What happens when a new peer enters and becomes a part of the election without even having any peers list ? Its possible because, say the leader dies, one of the peers detect that the leader is dead, then new peer enters and then a fresh new election starts! so yeah, this situation is possible!  
Lets go step by step  
1. New peer definitely announces itself as the winner 
2. There will another winner who is the oldest peer
3. Definitely , there will be atleast one peer who will elder to the new peer
4. All the elder peers will broadcast the ledger across the network [ Yes, there will be congestion of repeated data as everyone is sending the same ledger. But this makes sure of data consistency]
5. On updating the ledger , a fresh new re election will happen where only one leader will be elected.

* HOLD ON ! What if, the oldest peer of the last election announces itself as the winner ? What about that ?

Its simple we just ignore that. We always consider the latest election ID . The election ID is basically just timestamp. Anyways, the same peer will win the next election round , as its the oldest peer. So we can ignore this result. Also by the logic of the consensus, when the final leader is chosen, even if its wrong , the election for that election ID is closed permanently. Any winners announced for that election ID later on will be ignored. 
This makes sure that the next round of election includes everyone and its FAIR. 
