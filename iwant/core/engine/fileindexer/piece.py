import os
def piece_size(file_size):
        print 'Size {0} MB'.format(file_size)
        if file_size >= 1000:  # more than 1 gb
            return 1024000 #512000
        elif file_size>=500 and file_size<1000:
            return 1024000 #256000
        elif file_size>=250 and file_size<500:
            return 1024000 #128000
        elif file_size>=125 and file_size<250:
            return 1024000#64000
        elif file_size>=63 and file_size<125:
            return 1024000#32000
        else:
            return 1024000#16000

