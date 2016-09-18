# iWant
## CLI based decentralized peer to peer file sharing


###Server
__Run the server to spawn 3 daemon process__
 1. __Server daemon__ : Interacts with filemonitoring daemon, client and Election daemon. 
 2. __Election daemon__ : Election daemon is the heart of consensus among peers and  updates the server as soon as there is a leader change. 
 3. __Filemonitor daemon__ : Filemonitor daemon looks for any changes in the folder you are sharing and informs the server daemon. The server daemon in turn updates the changes to the main Leader. 

Then run client in another shell

__IMP: Open iwant/config.py and change your Download folder and the folder you are sharing directory name.__

To run server
```sh
sudo python main.py
```

### Client 
To run instant search on filenames in the network
```sh
python ui.py --search avengers
```

To download files 
```sh
python ui.py --download <hash value of avengers>
```
