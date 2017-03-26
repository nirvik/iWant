For any update operation in the database, the return value is in the form of ["ADD/DEL", (path, file size, file hash, root hash)]

In the network, the list is passed on to the leader, who will extract the first element and determine if he has to add or delete the entry in his database

In the bootstrap method, it is made sure that only minimal number of files are made to set their shared value in database to true. For example, lets say I am sharing a directory called "/home/nirvik/Movies/".
Suppose, the program is closed and we add 5 movies to the Movies/ . Since, there is no one watching the Movies/ directory and updating the database, nothing really happens. 
Next time when we run the program, it has to set the share value of the remaining 5 movies to true.
It would be unwise to set the share value of all the files in Movies/ directory again. Say, there were 100 movies. So, you have to set the share value of 100 movies again which were already set to true.
Therefore, we extract all the filenames and gather only the files that have matching prefix of the shared directory. Lets call all the files "to be" shared as X. Likewise, the remaining files are "to be" unshared, called Y.

X = l + m ( l is shared files, m is new)
Y = c + d ( c is shared files, d is unshared)

Set of all files = P + Q (P is all shared, Q is all unshared)
Now we want to set the share value of m. Therefore, we do this =>

X - P => X - (X intersection P)

X intersection P = l
X = l + m

X - P = l + m - l = m

Hence we update only m 
