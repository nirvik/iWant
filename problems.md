---
Problems
---

Q. create file of particular size in python ?  
A. http://stackoverflow.com/questions/8816059/create-file-of-particular-size-in-python  

Q. While file transfer, some pieces were missing. why ? the checksum didnt match. Why?  
A. Since the checksum didnt match, it probably means that there is something wrong with the string manipulation at client side. Turns out I used the replace method in the string to remove the delimiter from the data received. This creates a problem as the same delimiter might be present in the middle of the string.  

Q. Sharing empty files creates a huge problem. How ?  
A. Different named empty files will have the same hash, which will be indexed and submitted to the leader. Every time, a new folder is shared, the leader tries to remove the previous entries which are added on the basis of the hash of the file. If single hash corresponds to multiple empty files, then this creates a problem. It would be better not share empty files. But lets say, people are sharing large codebase. There is a huge possibility to have empty init files. 
