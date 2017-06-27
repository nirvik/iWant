import os
import hashlib
from twisted.internet import defer, reactor
from twisted.enterprise import adbapi
import piece


@defer.inlineCallbacks
def bootstrap(folder, dbpool):
    """Returns all the files and folder meta information that needs to be shared
    :param folder: absolute path of the shared folder
    :param dbpool: twisted.enterprise.adbapi.ConnectionPool object
    """
    if not os.path.exists(folder):
        raise NotImplementedError
    else:
        # we need to remove all the entries for which the path doesnot exist
        yield remove_all_deleted_files(dbpool)
        all_filenames_response = yield dbpool.runQuery('select filename from indexer')
        all_filenames = set(map(lambda x: x[0], all_filenames_response))
        # print 'all the filenames are {0}'.format(all_filenames)
        files_to_be_unshared = set(
            filter(
                lambda x: not x.startswith(
                    os.path.abspath(folder)),
                all_filenames))
        files_to_be_shared = all_filenames - files_to_be_unshared
        # print 'files to be shared {0}'.format(files_to_be_shared)

        all_unshared_files_response = yield dbpool.runQuery('select filename from indexer where share=0')
        all_unshared_files = set(
            map(lambda x: x[0], all_unshared_files_response))
        all_shared_files = all_filenames - all_unshared_files

        share_remaining_files = files_to_be_shared - all_shared_files
        unshare_remaining_files = files_to_be_unshared - all_unshared_files
        yield share(share_remaining_files, dbpool)
        yield unshare(unshare_remaining_files, dbpool)
        yield index_folder(folder, dbpool)
        combined_response = {}
        combined_response['ADD'] = []
        combined_response['DEL'] = []
        combined_response['shared_folder'] = folder
        files_added_metainfo = []
        files_removed_metainfo = []

        for filepath in unshare_remaining_files:
            file_entry = yield dbpool.runQuery('select filename, size, hash, roothash from indexer where filename=?', (filepath,))
            files_removed_metainfo.append(file_entry[0])

        # files_removed_metainfo.extend(removed_files_temp)
        sharing_files = yield dbpool.runQuery('select filename, size, hash, roothash from indexer where share=1')
        files_added_metainfo.extend(sharing_files)
        combined_response['ADD'] = files_added_metainfo
        combined_response['DEL'] = files_removed_metainfo
        defer.returnValue(combined_response)


@defer.inlineCallbacks
def remove_all_deleted_files(dbpool):
    """Removes file entries from database that are deleted from the file system
    :param dbpool: twisted.enterprise.adbapi.ConnectionPool object
    """
    filenames = yield dbpool.runQuery('select filename from indexer')
    for filename in filenames:
        if not os.path.exists(filename[0]):
            print '[Indexer][Removing]: {0}'.format(filename[0])
            yield dbpool.runQuery('delete from indexer where filename=?', (filename[0],))
    resume_table_filenames = yield dbpool.runQuery('select filename from resume')
    for filename in resume_table_filenames:
        if not os.path.exists(filename[0]):
            print '[Resume][Removing]: {0}'.format(filename[0])
            yield dbpool.runQuery('delete from resume where filename=?', (filename[0],))


@defer.inlineCallbacks
def unshare(files, dbpool):
    """Sets the share value of the files to 0 in the database
    :param files: list of absolute file paths
    :param dbool: twisted.enterprise.adbapi.ConnectionPool object
    """
    for f in files:
        yield dbpool.runQuery('update indexer set share=0 where filename=?', (f,))
    defer.returnValue('unshared')


@defer.inlineCallbacks
def share(files, dbpool):
    """Sets the share value of the files to 1 in the database
    :param files: list of absolute file paths
    :param dbool: twisted.enterprise.adbapi.ConnectionPool object
    """
    for f in files:
        yield dbpool.runQuery('update indexer set share=1 where filename=?', (f,))
    defer.returnValue('shared')


@defer.inlineCallbacks
def folder_delete_handler(path, dbpool, modified_folder):
    """Removes all the files from the db which are under modified folder and returns those filenames, which are deleted, in a dict
    :param path: absolute pathname of the shared folder
    :param dbool: twisted.enterprise.adbapi.ConnectionPool object
    :param modified_folder: absolute pathname of the folder deleted
    """
    response = {}
    response['ADD'] = []
    response['DEL'] = []
    response['shared_folder'] = None
    path = os.path.realpath(path)
    file_property_list = []
    all_shared_files_from_db = yield dbpool.runQuery('select filename from indexer where share=1')
    relevant_files = filter(
        lambda x: x[0].startswith(modified_folder),
        all_shared_files_from_db)

    for filename in relevant_files:
        file_removed_response = yield dbpool.runQuery('select filename, size, hash, roothash from indexer where filename=?', (filename[0],))
        # print 'removing a folder {0}'.format(file_removed_response)
        file_property_list.append(file_removed_response[0])
        yield dbpool.runQuery('delete from indexer where filename=?', (filename[0],))

    parent = {}
    folder_properties = {}
    parent[path] = -1
    folder_properties[path] = {}
    folder_properties[path]['size'] = 0.0
    folder_properties[path]['hash'] = ''

    for root, _, filenames in os.walk(path):
        if root not in parent:
            immediate_parent = os.path.dirname(root)
            parent[root] = immediate_parent
            folder_properties[root] = {}
            folder_properties[root]['size'] = 0.0
            folder_properties[root]['hash'] = ''
        total_size = 0.0
        folder_hash = ''
        for filename in filenames:
            destination_path = os.path.join(root, filename)
            total_size += get_file_size(destination_path)
            file_hash_db = yield dbpool.runQuery('select hash from indexer where filename=?', (destination_path,))
            folder_hash += file_hash_db[0][0]

        hasher = hashlib.md5()
        hasher.update(folder_hash)
        folder_properties[root]['size'] = total_size
        folder_properties[root]['hash'] = hasher.hexdigest()

        temp_path = root
        while parent[temp_path] != -1:
            folder_properties[parent[temp_path]]['size'] += total_size
            parent_folder_hash = folder_properties[
                parent[temp_path]]['hash']
            parent_folder_hash += folder_hash
            hasher = hashlib.md5()
            hasher.update(parent_folder_hash)
            folder_properties[parent[temp_path]]['hash'] = hasher.hexdigest()
            temp_path = parent[temp_path]

    folders_updated_list = []
    for keys, values in folder_properties.iteritems():
        folder_path = keys
        size = values['size']
        folder_hash = values['hash']
        folder_hash_db = yield dbpool.runQuery('select hash from indexer where filename=?', (folder_path,))
        if folder_hash_db[0][0] != folder_hash:
            folder_index_entry = (
                size,
                folder_hash,
                folder_hash,
                folder_hash,
                True,
                folder_path
            )
            yield dbpool.runQuery('update indexer set size=?, hash=?, piecehashes=?, roothash=?, isdirectory=? where filename=?', (folder_index_entry))
            folders_updated_list.extend(
                [(folder_path, size, folder_hash, folder_hash)])  # , True)])

    response['DEL'] = file_property_list
    response['ADD'] = folders_updated_list
    defer.returnValue(response)


@defer.inlineCallbacks
def index_folder(folder, dbpool, modified_folder=None):
    """Creates the metadata of all the files insider the folder being shared
    :param folder: absolute pathname of the share folder
    :param dbool: twisted.enterprise.adbapi.ConnectionPool object
    :param modified_folder: (optional) absolute pathname of the folder modified

    returns a dict containing a list containing (file_name, size, file_hash, root_hash) of files to be deleted and shared , shared_folder
    """
    response = {}
    response['DEL'] = []
    response['ADD'] = []
    response['shared_folder'] = None
    file_property_list = []

    # for aggregating folder data
    parent = {}
    folder_properties = {}
    folder_path = os.path.realpath(folder)
    parent[folder_path] = -1
    folder_properties[folder_path] = {}
    folder_properties[folder_path]['size'] = 0
    folder_properties[folder_path]['hash'] = ''
    folder_properties[folder_path]['updated'] = False

    for root, _, filenames in os.walk(folder_path):
        if root not in parent:
            parent_of_root = os.path.dirname(root)
            parent[root] = parent_of_root
            folder_properties[root] = {}
            folder_properties[root]['size'] = 0
            folder_properties[root]['hash'] = ''
            folder_properties[root]['updated'] = False
        folder_size = 0  # for folder size
        file_hash = ''  # for folder hash
        for filename in filenames:
            destination_path = os.path.join(root, filename)
            indexed_file_property = yield index_file(destination_path, dbpool)
            if len(indexed_file_property['ADD']) == 0:
                # its already been indexed in the db
                file_hash_db = yield dbpool.runQuery('select hash from indexer where filename=?', (destination_path,))
                file_hash += file_hash_db[0][0]
            else:
                file_hash += indexed_file_property['ADD'][0][2]
            folder_size += get_file_size(destination_path)
            # Adding only relevant files to the list.. If there is any
            # modification, we should only be concerned with the modified files
            if modified_folder:
                if destination_path.find(modified_folder) != -1:
                    file_property_list.extend(indexed_file_property['ADD'])
            else:
                file_property_list.extend(indexed_file_property['ADD'])

        #  Recursively updating the parent hash and size
        folder_properties[root]['size'] = folder_size
        hasher = hashlib.md5()
        hasher.update(file_hash)
        folder_properties[root]['hash'] = hasher.hexdigest()
        recursive_folder_path = root

        while parent[recursive_folder_path] != -1:
            folder_properties[
                parent[recursive_folder_path]]['size'] += folder_size
            folder_hash = folder_properties[
                parent[recursive_folder_path]]['hash']
            folder_hash += file_hash
            hasher = hashlib.md5()
            hasher.update(folder_hash)
            folder_properties[parent[recursive_folder_path]][
                'hash'] = hasher.hexdigest()
            recursive_folder_path = parent[recursive_folder_path]

    for keys, values in folder_properties.iteritems():
        folder = keys
        size = values['size']
        folder_hash = values['hash']
        # print 'folder=> {0} \n size=>{1} \t hash=>{2}'.format(keys, size,
        # folder_hash)
        folder_hash_db = yield dbpool.runQuery('select hash from indexer where filename=?', (folder,))
        try:
            if folder_hash_db[0][0] != folder_hash:
                folder_index_entry = (
                    size,
                    folder_hash,
                    folder_hash,
                    folder_hash,
                    True,
                    folder
                )
                yield dbpool.runQuery('update indexer set size=?, hash=?, piecehashes=?, roothash=?, isdirectory=? where filename=?', (folder_index_entry))
                file_property_list.extend(
                    [(folder, size, folder_hash, folder_hash)])  # , True)])
        except:
            folder_index_entry = (
                folder,
                1,
                size,
                folder_hash,
                folder_hash,
                folder_hash,
                True
            )
            yield dbpool.runQuery('insert into indexer values (?,?,?,?,?,?,?)', (folder_index_entry))
            file_property_list.extend(
                [(folder, size, folder_hash, folder_hash)])  # , True)])
    response['ADD'] = file_property_list
    defer.returnValue(response)


@defer.inlineCallbacks
def index_file(path, dbpool):
    """Builds meta information of a single file
    :param file: absolute pathname of the file to be indexed
    :param dbool: twisted.enterprise.adbapi.ConnectionPool object

    returns a dict containing a list containing (file_name, size, file_hash, root_hash) of files to be deleted and shared , shared_folder
    """
    response = {}
    response['DEL'] = []
    response['ADD'] = []
    response['shared_folder'] = None
    filesize = get_file_size(path)
    filesize_from_db = yield dbpool.runQuery('select size from indexer where filename=?', (path,))
    try:
        if filesize_from_db[0][0] != filesize:
            file_hash, piece_hashes, root_hash = get_file_hashes(path)
            file_index_entry = (
                filesize,
                file_hash,
                piece_hashes,
                root_hash,
                False,
                path,
            )
            print 'updating the hash'
            yield dbpool.runQuery('update indexer set size=?, hash=?, piecehashes=?, roothash=?, isdirectory=? where filename=?', (file_index_entry))
            file_property_list = [
                (path, filesize, file_hash, root_hash)]  # , False)]
            response['ADD'] = file_property_list
            defer.returnValue(response)
    except IndexError:
        # print '@index_file {0}'.format(filesize_from_db)
        if len(filesize_from_db) == 0:
            file_hash, piece_hashes, root_hash = get_file_hashes(path)
            print '[New File: Indexed] {0}'.format(path)
            file_index_entry = (
                path,
                1,
                filesize,
                file_hash,
                piece_hashes,
                root_hash,
                False)
            yield dbpool.runQuery('insert into indexer values (?,?,?,?,?,?,?)', (file_index_entry))
            file_property_list = [
                (path, filesize, file_hash, root_hash)]  # , False)]
            response['ADD'] = file_property_list
            defer.returnValue(response)
    else:
        defer.returnValue(response)


def get_file_size(path):
    """Returns the file in MB
    param path: absolute pathname of the file
    """
    return os.stat(path).st_size / (1000.0 * 1000.0)


@defer.inlineCallbacks
def get_structure(hash_value, dbpool):
    """This returns a response which contains information about the folder/file structure. This is sent to the leecher which can facilitate him in replicating the folder structure in his system.
    :param hash_value: hash string corresponding to the folder_name or a fiename
    :param dbpool: twisted.enterprise.adbapi.ConnectionPool object
    returns a dict: if hash_value is of a directory, it returns
    {
        isWindows: True/False,
        isFile: False,
        rootDirectory: foldername,
        files: [(parent_folder, basename_of_file, file_size, file_hash, root_hash),...]
    }
    if hash_value is of a filename, it returns
    {
        isWindows: True/False,
        isFile: False,
        rootHash: hash,
        filename: absolute file path,
        size: file size
    }

    """
    craft_response = {}
    if os.name != 'nt':
        craft_response['isWindows'] = False
    else:
        craft_response['isWindows'] = True
    response_db = yield dbpool.runQuery('select filename, roothash, size from indexer where hash=?', (hash_value,))
    filename, roothash, size = response_db[0]
    if os.path.isdir(filename):
        foldername = filename
        craft_response['isFile'] = False
        craft_response['rootDirectory'] = foldername
        files_list = []
        for root, dirpath, filenames in os.walk(foldername):
            for basename in filenames:
                absolute_filepath = os.path.join(root, basename)
                #file_hash, _, root_hash = get_file_hashes(absolute_filepath)
                hashes_response_db = yield dbpool.runQuery('select hash, roothash from indexer where filename=?', (absolute_filepath,))
                size = get_file_size(absolute_filepath)
                file_hash, root_hash = hashes_response_db[0]
                files_list.append((root, basename, size, file_hash, root_hash))
        craft_response['files'] = files_list
    else:
        craft_response['isFile'] = True
        craft_response['roothash'] = roothash
        craft_response['filename'] = filename
        craft_response['size'] = size

    defer.returnValue(craft_response)


@defer.inlineCallbacks
def check_hash_present_in_resume(filename, dbpool):
    """Checks if hash value is present in the resume table
    :param filename: absolute filepath
    :param dbpool: twisted.enterprise.adbapi.ConnectionPool object
    """
    response = yield dbpool.runQuery('select filename from resume where filename=?', (filename,))
    if len(response) == 0:
        defer.returnValue(False)
    else:
        filename = response[0][0]
        if not os.path.exists(filename):
            yield remove_resume_entry(filename, dbpool)
            defer.returnValue(False)
        defer.returnValue(True)


@defer.inlineCallbacks
def remove_resume_entry(filename, dbpool):
    """Removes file entry from the resume table
    :param filename: absolute filepath
    :param dbpool: twisted.enterprise.adbapi.ConnectionPool object
    """
    filename_response = yield dbpool.runQuery('select filename from indexer where filename=?', (filename,))
    filename = filename_response[0][0]
    # print 'everything deleted from indexer and resume'
    yield dbpool.runQuery('delete from resume where filename=?', (filename,))
    yield dbpool.runQuery('delete from indexer where filename=?', (filename,))


@defer.inlineCallbacks
def add_new_file_entry_resume(file_entry, dbpool):
    """Add file entry to the resume table
    :param filename: absolute filepath
    :param dbpool: twisted.enterprise.adbapi.ConnectionPool object
    """
    # print 'new entry added to resume table'
    # filename, checksum = file_entry[0], file_entry[3]
    # checksum = file_entry[3]
    filename = file_entry[0]
    yield dbpool.runQuery('insert into resume values (?)', (filename,))
    yield dbpool.runQuery('insert into indexer values (?,?,?,?,?,?,?)', (file_entry))


def get_file_hashes(filepath):
    """Generates md5 hash of the file based on content, hashes of all the chunks, hash of concatenated hashes from all chunks
    :param filepath: absolute filepath
    returns (hash, concatenated hashes of chunks, roothash)
    """
    hash_list = ''
    md5_hash = hashlib.md5()
    filesize = get_file_size(filepath)
    chunk_size = piece.piece_size(filesize)
    print 'Hashing: {0}\t Size {1}'.format(filepath, filesize)
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            md5_hash.update(chunk)
            piece_hash = hashlib.md5()
            piece_hash.update(chunk)
            hash_list += piece_hash.hexdigest()
    root_hash = hashlib.md5()
    root_hash.update(hash_list)
    return md5_hash.hexdigest(), hash_list, root_hash.hexdigest()


@defer.inlineCallbacks
def get_file(file_hash, dbpool):
    """Returns the corresponding file object
    :param file_hash: hash of the file
    :param dbpool: twisted.enterprise.adbapi.ConnectionPool object
    """
    file_query_response = yield dbpool.runQuery('select filename from indexer where hash=?', (file_hash,))
    # print file_query_response[0][0]
    defer.returnValue(open(file_query_response[0][0], 'rb'))


@defer.inlineCallbacks
def get_piecehashes_of(file_hash, dbpool):
    """Returns concatenated hash of all chunks belonging to a particular file
    :param file_hash: hash of the file
    :param dbpool: twisted.enterprise.adbapi.ConnectionPool object
    """
    file_pieces_response = yield dbpool.runQuery('select piecehashes from indexer where hash=?', (file_hash,))
    defer.returnValue(file_pieces_response[0][0])

if __name__ == '__main__':
    def set_text_factory(conn):
        conn.text_factory = str

    dbpool = adbapi.ConnectionPool(
        'sqlite3',
        '/home/nirvik/.iwant/iwant.db',
        check_same_thread=False,
        cp_openfun=set_text_factory)
    get_structure('b550c3580bfd0dffa7dbecaefc7816da', dbpool)
    reactor.run()
