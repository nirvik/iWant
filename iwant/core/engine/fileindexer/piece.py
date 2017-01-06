import os
def piece_size(file_size):
        print 'Size {0} MB'.format(file_size)
        if file_size >= 1000:  # more than 1 gb
            return 512000
        elif file_size>=500 and file_size<1000:
            return 256000
        elif file_size>=250 and file_size<500:
            return 128000
        elif file_size>=125 and file_size<250:
            return 64000
        elif file_size>=63 and file_size<125:
            return 32000
        else:
            return 16000

