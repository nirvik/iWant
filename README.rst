iWant
=====

CLI based decentralized peer to peer file sharing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

What is it?
-----------

A commandline tool for searching and downloading files in LAN network,
without any central server.

Features
--------

-  **Decentralized** : There is no central server hosting files.
   Therefore, no central point of failure
-  **Easy discovery of files**: As easy as searching for something in
   Google.
-  **File download from multiple peers**: If the seeder fails/leaves the
   group, leecher will continue to download from another seeder in the
   network
-  **Directory download**: Supports downloading directories
-  **Resume download**: Resume download from where you left off.
-  **Consistent data**: Any changes(modification, deletion, addition)
   made to files inside the shared folder will be instantly reflected in
   the network
-  **Cross Platform**: Works in Linux/Windows/Mac. More testing needs to
   be done in Mac

Why I built this ?
------------------

-  I like the idea of typing some filename in the terminal and download
   it if people around me have it.
-  No third party registration.
-  No crazy configuration.
-  Wanted it to be cross platform.
-  Zero downtime.
-  No browser.. just terminal
-  For fun ¯\\\ *(ツ)*/¯

Installation
------------

.. code:: sh

    python setup.py install --user

System Dependencies
-------------------

Make sure, you have the following system dependencies installed: \*
libffi-dev \* libssl-dev

Usage
-----

::

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

**Note: Shared and Download folder cannot be the same**

How to run
----------

Run ``iwanto start`` (this runs the iwant service).

Running client
--------------

To run services like, search, download, view config and change config,
open up another terminal and make sure that iwant server is running.

Running server
--------------

In windows, admin access is required to run the server

.. code:: sh

    iwanto start






Search files
------------

Type the name of file ;) (P.S No need of accurate names)

.. code:: sh

    iwanto search <filename>

Example:

.. code:: sh

    iwanto search "slicon valey"






Download files
--------------

To download the file , just enter the hash of the file you get after
searching.

.. code:: sh

    iwanto download <hash of the file>

Example:

.. code:: sh

    iwanto download b8f67e90097c7501cc0a9f1bb59e6443






Change shared folder
--------------------

Change shared folder anytime (Even when iwant service is running)

.. code:: sh

    iwanto share <path>

Example:

.. code:: sh

    iwanto share /home/User/Movies/

In windows, give quotes:

.. code:: sh

    iwanto share "C:\Users\xyz\books\"






Change downloads folder
-----------------------

Change download folder anytime

.. code:: sh

    iwanto download to <path>

Example:

.. code:: sh

    iwanto download to /home/User/Downloads

In windows, give quotes:

.. code:: sh

    iwanto download to "C:\User\Downloads"

View shared/donwload folder
---------------------------

.. code:: sh

    iwanto view config

How does it work ?
------------------

As soon as the program starts, it spawns the **election daemon**,
**folder monitoring daemon** and **server daemon**.

1. The **election daemon** takes care of the following activities

   -  Manages the consensus.
   -  Notifies the **server daemon** as soon as there is a leader
      change.
   -  It coordinates with other peers in the network regarding
      contesting elections, leader unavailability, network failure,
      split brain situation etc.
   -  It uses **multicast** for peer discovery. 
      
      

2. When the **folder monitoring daemon** starts, it performs the
   following steps

   -  Indexes all the files in the shared folder
   -  Updates the entries in the database
   -  Informs the server about the indexed files and folders.
   -  Any changes made in the shared folder will trigger the **folder
      monitoring daemon** to index the modified files, update the
      database and then inform the server about the changes

3. The **iwant client** talks to the **server daemon** when the user
   wishes to:

   -  search for files
   -  download files
   -  change shared folder
   -  change download folder

4. The **server daemon** receives commands from **iwant client** and
   updates from **file monitoring and election daemon**.

   -  Updates received from **folder monitoring daemon** is fowarded to
      the leader. For example: indexed files/folders information.
   -  Updates received from the **election daemon** like
      ``leader change`` event, triggers the server to forward the
      indexed files/folders information to the new leader
   -  Queries received from the **iwant client** like ``file search`` is
      forwarded to the leader, who then performs fuzzy search on the
      metadata it received from other peers and returns a list
      containing (filename, size, checksum)
   -  Queries received from the **iwant client** like ``file download``
      is forwarded to the leader, who forwards the roothash of the
      file/folder along with the list of peers who have the file. The
      **server daemon** then intiates download process with peers
      mentioned in the peers list.
   -  Updates received from the **iwant client** like
      ``changing shared folder``, triggers the **server daemon** to make
      sure that the **folder monitoring daemon** indexes the new folder
      and after indexing is complete, the **server daemon** updates the
      leader with the new indexed files/folders meta information.

Todo
----

-  Create test modules
-  Make download faster
-  Incorporate tight security mechanisms
-  Improve UI for file/folder download progress bar
-  Add streaming functionality

Why it may not work?
--------------------

-  Firewall
-  Multicast not supported in your router.

Errors
------

All logs are present in ``~/.iwant/.iwant.log`` or
``AppData\Roaming\.iwant\.iwant.log``

Liked the project ?
-------------------

| |Say Thanks!|
| Any ideas, bugs or modifications required, feel free to me send me a
  PR :)

.. |Say Thanks!| image:: https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg
   :target: https://saythanks.io/to/nirvik
