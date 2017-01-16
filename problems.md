Q. create file of particular size in python ? 
A. http://stackoverflow.com/questions/8816059/create-file-of-particular-size-in-python

Q. While file transfer, some pieces were missing. why ? the checksum didnt match. Why?
A. Since the checksum didnt match, it probably means that there is something wrong with the string manipulation at client side. Turns out I used the replace method in the string to remove the delimiter from the data received. This creates a problem as the same delimiter might be present in the middle of the string.
