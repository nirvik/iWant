# iWanto
## CLI based decentralized peer to peer file sharing

__What is this?__ 
It's basically a commandline tool which lets you to look for and download files in the network. 

###Installation
```sh
python setup.py install --user
```

###Server

To run the server
```sh
iwanto-start
```

### Client 
want to look for files in your network? (P.S No need of accurate names, thanks to fuzzywuzzy)
```sh
iwanto --search batman
```

want to download batman? 
```sh
iwanto --download <hash(batman)>
```
