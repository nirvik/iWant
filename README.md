# iWant
## CLI based decentralized peer to peer file sharing

### __What is this?__  
A commandline tool for searching and downloading files in LAN network, without any central server. 

### Features
1. __Decentralized__ : No central server is hosting files. Therefore, no central point of failure 
2. __Easy discovery of files__: As easy as searching for something in google. 
3. __File download from multiple peers__: If the seeder fails/leaves the group, leecher will continue to download from another seeder in the network 
4. __Directory download__: Supports downloading directories   
5. __Resume download__:  Resume download from where you left off. 
6. __Consistent data__: Any changes made to files inside the shared folder will be instantly reflected in the network 
7. __Cross Platform__: Works in Linux/Windows/Mac 

### Installation
```sh
python setup.py install --user
```

### How to run 

1. Open `~/.iwant/.iwant.conf` and update your shared/download folder.  
2. Run the `iwanto` service.   


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
