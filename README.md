# iWant
## CLI based decentralized peer to peer file sharing

### __What is this?__  
A commandline tool for searching and downloading files in LAN network.  

### Installation
```sh
python setup.py install --user
```
1.  This creates a .iwant folder in the home directory  
2.  Open ~/.iwant/.iwant.conf file  
3.  Update __share__ and __download__ values in the conf file. __share__ key is the absolute path of the folder you wish to share. Similarly __download__ key is the absolute path of the folder where new files will be downloaded to.  
4.  Run the server  
5.  Run the client 
6.  Maintain the order of steps  

## Server

To run the server
```sh
iwanto-start
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
