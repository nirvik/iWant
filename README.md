# iWanto
## CLI based decentralized peer to peer file sharing

__What is this?__ 
Its basically a commandline tool which lets you to look for and download files in the network. 

__So, I just type the name of the file in the terminal and it tells me who has it?__ 
Yep and this service also lets you download them.  

__Whats the big deal ? System is gonna crash when the server is down !__ 
Did I tell you its decentralized ? Even if the main server fails, one of your computers in your network will take up the role of the main server. This will go on until there is no one in the network using this service. 

__Summarization__ 
Its a commandline tool which lets you type the name of the file in the terminal and lets you download the file without any hassle. Also, the main thing , its fault tolerant. As long as there is someone using the service in the network, the system is very much alive.  

__Requirements__ 
After running the setup file , you will find a __iwant.conf__ file in your home directory. You must configure the __share__ and __download__ folder before running the service. 
Only the files present in __share__ will be available to the peers in the network. If you change the value of __share__ in the __iwant.conf__ file , then you will have to restart the service. 

__share__ : This is the folder which will be shared with your peers in the network  
__download__ : This is the folder where your downloaded files will be dumped into using iwanto service.  

###Installation
```sh
sudo python setup.py install
```

###Server

To run the server
```sh
sudo iwanto-start
```

### Client 
want to look for files in your network ? (P.S No need of accurate names, thanks to fuzzywuzzy)
```sh
iwanto --search batman
```

want to download batman ? 
```sh
iwanto --download <hash(batman)>
```
