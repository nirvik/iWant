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
* __Cross Platform__: Works in Linux/Windows/Mac 

## Installation 
```sh
python setup.py install --user
```

## Usage
```
iWant.

Usage:
    iwanto start
    iwanto search <name>
    iwanto download <hash>
    iwanto share <path>
    iwanto change download path to <destination>
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
    change download path to <destination>       Change download folder

```

## How to run 
Run `iwanto start` (this runs the iwant service).   


## Running server   
In windows, admin access is required to run the server
```sh
$ iwanto start
```

## Search files    
Type the name of file ;)  (P.S No need of accurate names)
```sh
$ iwanto search <filename>
```
Example: 
```sh
$ iwanto search "slicon valey"
```

## Download files  
To download the file , just enter the hash of the file you get after searching. 
```sh
iwanto download <hash_of_the_file>
```
Example: 
```sh
iwanto download b8f67e90097c7501cc0a9f1bb59e6443
```
## Change shared folder  
Changing shared folder, while the iwant service is still running
```sh
iwanto share <path>
```
Example: 
```sh
iwanto share /home/User/Movies/
```
## Change downloads folder  
Changing downloads folder, while the iwant service is still running 
```sh
iwanto change download path to <path>
```
Example: 
```sh
iwanto change download path to /home/User/Downloads
```


## Display your Shared/Donwload folder  
```sh
iwanto view config
```

## How does it work ? 

As soon as the program starts, it spawns the __election daemon__, __folder monitoring daemon__ and __server daemon__. 
1. The __election daemon__ manages the entire consensus. It updates the __server daemon__ as soon as there is a leader change. It coordinates with other peers in the network regarding contesting elections, leader unavailability, network failure, split brain situation etc. The consensus description is mention [here](iwant/core/engine/consensus/README.md)
2. When the __folder monitoring daemon__ starts, it indexes all the files in the shared folder, updates the entries in the database and informs the server about the metainformation of the files/folders indexed.
    - Any changes made in the shared folder will trigger the __folder monitoring daemon__ to index the modified files and inform the server.
    - It also makes the necessary changes to the database
3. The __server daemon__ receives updates from the file monitoring and election daemon. 
    - Any update received from __folder monitoring daemon__ is fowarded to the leader. 
    - Any update received from the __election daemon__ like `leader change` event, the server forwards the meta information to the leader
    - Any queries received from the __iwant client__ like `file search` is forwarded to the leader, who then performs fuzzy search on the metadata it received from other peers and returns a list containing (filename, size, checksum)
    - Any queries received from the __iwant client__ like `file download` is forwarded to the leader, who forwards the roothash of the file/folder along with the list of peers who have the file. The __server daemon__ then intiates download process with peers mentioned in the peers list.
    - Updates received from the __iwant client__ like `changing shared folder`, the __server daemon__ makes sure that the __folder monitoring daemon__ indexes the new folder and after indexing is complete, the __server daemon__ updates the leader with the new metainformation.
4. The __iwant client__ talks to the __server daemon__ when the user wishes to `search`, `download`, `change shared folder` and `change download folder`

## Errors

All logs are present in `~/.iwant/.iwant.log` or `AppData\Roaming\.iwant\.iwant.log`

## Security

## FAQ
