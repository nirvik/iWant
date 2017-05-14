# iWant
## CLI based decentralized peer to peer file sharing

### __What is this?__  
A commandline tool for searching and downloading files in LAN network, without any central server. 

### Features
* __Decentralized__ : There is no central server hosting files. Therefore, no central point of failure 
* __Easy discovery of files__: As easy as searching for something in google. 
* __File download from multiple peers__: If the seeder fails/leaves the group, leecher will continue to download from another seeder in the network 
* __Directory download__: Supports downloading directories   
* __Resume download__:  Resume download from where you left off. 
* __Consistent data__: Any changes made to files inside the shared folder will be instantly reflected in the network 
* __Cross Platform__: Works in Linux/Windows/Mac 

### Installation
```sh
python setup.py install --user
```

### How to run 

1. Open `~/.iwant/.iwant.conf` and update your shared/download folder.  
2. Run the `iwanto` service.   


## Server

__Running server__
```sh
iwanto start
```

## Client 
__Search files__: Type the name of file ;)  (P.S No need of accurate names)
```sh
iwanto search <filename>
```
Or
```sh
iwanto search "silicon valey"
```

__Download files__: To download the file , just enter the hash of the file you get after searching. 
```sh
iwanto download <hash_of_the_file>
```
__Change shared folder__: Changing shared folder, while the iwant service is still running
```sh
iwanto share <path>
```
__Change downloads folder__: Changing downloads folder, while the iwant service is still running 
```sh
iwanto change download path to <path>
```

## Security

## FAQ
