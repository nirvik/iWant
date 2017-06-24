# iWant
### CLI based decentralized peer to peer file sharing

## What is it?  
A commandline tool for searching and downloading files in LAN network, without any central server. 

## Features
* __Decentralized__ : There is no central server hosting files. Therefore, no central point of failure 
* __Easy discovery of files__: As easy as searching for something in Google. 
* __File download from multiple peers__: If the seeder fails/leaves the group, leecher will continue to download from another seeder in the network 
* __Directory download__: Supports downloading directories   
* __Resume download__:  Resume download from where you left off. 
* __Consistent data__: Any changes made to files inside the shared folder will be instantly reflected in the network 
* __Cross Platform__: Works in Linux/Windows/Mac. More testing needs to be done in Mac 

## Why I built this ? 

* I like the idea of typing some filename in the terminal and download it if people around me have it.
* No third party registration. 
* No crazy configuration. 
* Wanted it to be cross platform. 
* Zero downtime. 
* No browser.. just terminal
* For fun ¯\\_(ツ)_/¯

## Installation 
```sh
python setup.py install --user
```

## System Dependencies 
Make sure, you have the following system dependencies installed:
* libffi-dev 
* libssl-dev 

## Usage
```
iWant.

Usage:
    iwanto start
    iwanto search <name>
    iwanto download <hash>
    iwanto share <path>
    iwanto download to <destination>
    iwanto view config
    iwanto --version

Options:
    -h --help                                   Show this screen.
    --version                                   Show version.
    start                                       This starts the iwant server in your system
    search <name>                               Discovering files in the network. Example: iwanto search batman
    download <hash>                             Downloads the file from the network
    share <path>                                Change your shared folder
    view config                                 View shared and download folder
    download to <destination>                   Change download folder

```

__Note: Shared and Download folder cannot be the same__

## How to run 
Run `iwanto start` (this runs the iwant service).   

## Running client
To run services like, search, download, view config and change config, open up another terminal and make sure that iwant server is running.

## Running server   
In windows, admin access is required to run the server
```sh
iwanto start
```
![alt text](docs/starting.gif)

## Search files    
Type the name of file ;)  (P.S No need of accurate names)
```sh
iwanto search <filename>
```
Example: 
```sh
iwanto search "slicon valey"
```
![alt text](docs/searching.gif)

## Download files  
To download the file , just enter the hash of the file you get after searching. 
```sh
iwanto download <hash of the file>
```
Example: 
```sh
iwanto download b8f67e90097c7501cc0a9f1bb59e6443
```
![alt text](docs/downloading.gif)

## Change shared folder  
Change shared folder anytime (Even when iwant service is running)  
```sh
iwanto share <path>
```
Example: 
```sh
iwanto share /home/User/Movies/
```
In windows, give quotes:
```sh
iwanto share "C:\Users\xyz\books\"
```
![alt text](docs/shareNewFolder.gif)

## Change downloads folder  
Change download folder anytime 
```sh
iwanto download to <path>
```
Example: 
```sh
iwanto download to /home/User/Downloads
```
In windows, give quotes:
```sh
iwanto download to "C:\User\Downloads"
```

## View shared/donwload folder  
```sh
iwanto view config
```

## How does it work ? 

As soon as the program starts, it spawns the __election daemon__, __folder monitoring daemon__ and __server daemon__. 
1. The __election daemon__ takes care of the following activities  
    * Manages the consensus. 
    * Notifies the __server daemon__ as soon as there is a leader change. 
    * It coordinates with other peers in the network regarding contesting elections, leader unavailability, network failure, split brain situation etc. 
    * It uses __multicast__ for peer discovery. The consensus description is mentioned [here](iwant/core/engine/consensus/README.md) 

2. When the __folder monitoring daemon__ starts, it performs the following steps 
    * Indexes all the files in the shared folder 
    * Updates the entries in the database 
    * Informs the server about the indexed files and folders.
    * Any changes made in the shared folder will trigger the __folder monitoring daemon__ to index the modified files, update the database and then inform the server about the changes 
3. The __iwant client__ talks to the __server daemon__ when the user wishes to:  
    * search for files 
    * download files  
    * change shared folder  
    * change download folder  
4. The __server daemon__ receives updates from the file monitoring and election daemon. 
    * Updates received from __folder monitoring daemon__ is fowarded to the leader. For example: indexed files/folders information. 
    * Updates received from the __election daemon__ like `leader change` event, triggers the server to forward the indexed files/folders information to the new leader
    * Queries received from the __iwant client__ like `file search` is forwarded to the leader, who then performs fuzzy search on the metadata it received from other peers and returns a list containing (filename, size, checksum)
    * Queries received from the __iwant client__ like `file download` is forwarded to the leader, who forwards the roothash of the file/folder along with the list of peers who have the file. The __server daemon__ then intiates download process with peers mentioned in the peers list.
    * Updates received from the __iwant client__ like `changing shared folder`, triggers the __server daemon__ to make sure that the __folder monitoring daemon__ indexes the new folder and after indexing is complete, the __server daemon__ updates the leader with the new indexed files/folders meta information.

## Todo
* Create test modules
* Make download faster
* Incorporate tight security mechanisms
* Improve UI for file/folder download progress bar
* Add streaming functionality

## Why it may not work? 
* Firewall 
* Multicast not supported in your router.


## Errors
All logs are present in `~/.iwant/.iwant.log` or `AppData\Roaming\.iwant\.iwant.log`

## Liked the project ? 
[![Say Thanks!](https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg)](https://saythanks.io/to/nirvik)  
Any ideas, bugs or modifications required, feel free to me send me a PR :) 


