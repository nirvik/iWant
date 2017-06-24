def piece_size(file_size):
    """
    Based on the size of the file, we decide the size of the pieces.
    :param file_size: represents size of the file in MB.
    """
    # print 'Size {0} MB'.format(file_size)
    if file_size >= 1000:  # more than 1 gb
        return 2 ** 19
    elif file_size >= 500 and file_size < 1000:
        return 2 ** 18
    elif file_size >= 250 and file_size < 500:
        return 2 ** 17
    elif file_size >= 125 and file_size < 250:
        return 2 ** 16
    elif file_size >= 63 and file_size < 125:
        return 2 ** 15
    else:
        return 2 ** 14
