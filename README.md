# iWant
### CLI based decentralized peer to peer file sharing

## __What is this?__  
A commandline tool for searching and downloading files in LAN network, without any central server. 

## Features
* __Decentralized__ : There is no central server hosting files. Therefore, no central point of failure 
* __Easy discovery of files__: As easy as searching for something in Google. 
* __File download from multiple peers__: If the seeder fails/leaves the group, leecher will continue to download from another seeder in the network 
* __Directory download__: Supports downloading directories   
* __Resume download__:  Resume download from where you left off. 
* __Consistent data__: Any changes made to files inside the shared folder will be instantly reflected in the network 
* __Cross Platform__: Works in Linux/Windows/Mac 

## Installation 
```sh
python setup.py install --user
```

## How to run 
1. We need to first configure our __Shared__ folder and the __Download__ folder(where your files/folders get downloaded into). There are two ways to go about it. 
    * Open `~/.iwant/.iwant.conf` and update the __shared__ and __download__ field.  
    * Or you could run  `iwanto share <path>` and `iwanto change download path to <path>` to change your shared and download folder respectively.  
2. Run `iwanto start` (this runs the iwanto service).   


## __Running server__ 
In windows, admin access is required to run the server
```sh
iwanto start
```

## __Search files__  
Type the name of file ;)  (P.S No need of accurate names)
```sh
iwanto search <filename>
```
Example: 
```sh
iwanto search "slicon valey"
```

## __Download files__  
To download the file , just enter the hash of the file you get after searching. 
```sh
iwanto download <hash_of_the_file>
```
Example: 
```sh
iwanto download b8f67e90097c7501cc0a9f1bb59e6443
```
## __Change shared folder__  
Changing shared folder, while the iwant service is still running
```sh
iwanto share <path>
```
Example: 
```sh
iwanto share /home/User/Movies/
```
## __Change downloads folder__  
Changing downloads folder, while the iwant service is still running 
```sh
iwanto change download path to <path>
```
Example: 
```sh
iwanto change download path to /home/User/Downloads
```

## Errors

All logs are present in `~/.iwant/.iwant.log` or `AppData\Roaming\.iwant\.iwant.log`

## Security

## FAQ
