# iWant
## CLI based decentralized peer to peer file sharing

### __What is this?__  
A commandline tool for searching and downloading files in LAN network, without any central server. 

### Installation
```sh
python setup.py install --user
```

### How to run 

1. Open ~/.iwant/.iwant.conf and update your shared/download folder.  
2. Run the iwant service.   


## Server

To run the server
```sh
iwanto start
```
![Alt text](/images/server_start_downloading.png?raw=true "iwant local server downloading Silicon Valley Season 1 Episode 6")

## Client 
To look for files in the network, just type the name of file ;)  (P.S No need of accurate names, thanks to fuzzywuzzy)
```sh
iwanto search Siliconvalley
```
![Alt text](/images/client_search.png?raw=true "Searching for silicon valley episodes")
To download the file , just enter the hash of the file. 
```sh
iwanto download <siliconvalley_episode_hash>
```
![Alt text](/images/client_download.png?raw=true "Requesting to download season 1 episode 6")

## Security

## FAQ
