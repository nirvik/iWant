import os
import hashlib
from twisted.internet import defer, reactor
from twisted.enterprise import adbapi
import piece


@defer.inlineCallbacks
def bootstrap(folder, dbpool):
    if not os.path.exists(folder):
        raise NotImplementedError
    else:
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
        # print 'finally we share remaining {0}'.format(share_remaining_files)
        # print 'finall we unshare remaining
        # {0}'.format(unshare_remaining_files)
        share_msg = yield share(share_remaining_files, dbpool)
        unshare_msg = yield unshare(unshare_remaining_files, dbpool)
        indexing_done = yield index_folder(folder, dbpool)
        # print 'please reach here {0}'.format(indexing_done)
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
        # print 'idiot ! we are obviously sharing {0}'.format(sharing_files)
        files_added_metainfo.extend(sharing_files)
        combined_response['ADD'] = files_added_metainfo
        combined_response['DEL'] = files_removed_metainfo
        defer.returnValue(combined_response)


@defer.inlineCallbacks
def unshare(files, dbpool):
    for f in files:
        yield dbpool.runQuery('update indexer set share=0 where filename=?', (f,))
    defer.returnValue('unshared')


@defer.inlineCallbacks
def share(files, dbpool):
    for f in files:
        yield dbpool.runQuery('update indexer set share=1 where filename=?', (f,))
    defer.returnValue('shared')


@defer.inlineCallbacks
def folder_delete_handler(path, dbpool):
    response = {}
    response['ADD'] = []
    response['DEL'] = []
    response['shared_folder'] = None
    file_property_list = []
    all_shared_files_from_db = yield dbpool.runQuery('select filename from indexer where share=1')
    relevant_files = filter(
        lambda x: x[0].startswith(path),
        all_shared_files_from_db)
    for filename in relevant_files:
        file_removed_response = yield dbpool.runQuery('select filename, size, hash, roothash from indexer where filename=?', (filename[0],))
        # file_property_list.extend(file_removed_property[0])
        print 'removing a folder {0}'.format(file_removed_response)
        file_property_list.append(file_removed_response[0])
    for filename in relevant_files:
        yield dbpool.runQuery('delete from indexer where filename=?', (filename[0],))
    response['DEL'] = file_property_list
    defer.returnValue(response)


@defer.inlineCallbacks
def file_delete_handler(path, dbpool):
    response = {}
    response['DEL'] = []
    response['ADD'] = []
    response['shared_folder'] = None
    file_property_list = []
    file_removed_response = yield dbpool.runQuery('select filename, size, hash, roothash from indexer where filename=?', (path,))
    print 'Removing a single file from {0}'.format(file_removed_response)
    file_property_list.extend(file_removed_response)
    remove_file = yield dbpool.runQuery('delete from indexer where filename=?', (path,))
    response['DEL'] = file_property_list
    defer.returnValue(response)


@defer.inlineCallbacks
def index_folder(folder, dbpool, modified_folder=None):
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
                if filename.find(modified_folder) != -1:
                    print '{0} is the one that is modified'.format(filename)
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
        print 'folder=> {0} \n size=>{1} \t hash=>{2}'.format(keys, size, folder_hash)
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
            [(folder, size, folder_hash, folder_hash, True)])
    response['ADD'] = file_property_list
    defer.returnValue(response)


@defer.inlineCallbacks
def index_file(path, dbpool):
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
                (path, filesize, file_hash, root_hash, False)]
            response['ADD'] = file_property_list
            defer.returnValue(response)
    except IndexError:
        print '@index_file {0}'.format(filesize_from_db)
        if len(filesize_from_db) == 0:
            file_hash, piece_hashes, root_hash = get_file_hashes(path)
            print 'this is a new entry {0}'.format(path)
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
                (path, filesize, file_hash, root_hash, False)]
            response['ADD'] = file_property_list
            defer.returnValue(response)
    else:
        defer.returnValue(response)


def get_file_size(path):
    '''
    return file size in mb
    '''
    return os.stat(path).st_size / (1000.0 * 1000.0)


@defer.inlineCallbacks
def check_hash_present_in_resume(hash_value, dbpool):
    response = yield dbpool.runQuery('select hash from resume where hash = ?', (hash_value,))
    if len(response) == 0:
        defer.returnValue(False)
    else:
        defer.returnValue(True)


@defer.inlineCallbacks
def remove_resume_entry(hash_value, dbpool):
    filename_response = yield dbpool.runQuery('select filename from indexer where hash=?', (hash_value,))
    filename = filename_response[0][0]
    yield dbpool.runQuery('delete from resume where hash=?', (hash_value,))
    yield dbpool.runQuery('delete from indexer where filename=?', (filename,))


@defer.inlineCallbacks
def add_new_file_entry_resume(file_entry, dbpool):
    filename, checksum = file_entry[0], file_entry[3]
    print 'adding to resume table {0}'.format(filename)
    # why is this necessary
    yield dbpool.runQuery('insert into indexer values (?,?,?,?,?,?)', (file_entry))
    yield dbpool.runQuery('insert into resume values (?,?)', (filename, checksum))


def get_file_hashes(filepath):
    hash_list = ''
    md5_hash = hashlib.md5()
    # hunk_size = piece_size(filepath)
    filesize = get_file_size(filepath)
    chunk_size = piece.piece_size(filesize)
    print 'CHUNK SIZE {0}'.format(chunk_size)
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
    file_query_response = yield dbpool.runQuery('select filename from indexer where hash=?', (file_hash,))
    print file_query_response[0][0]
    defer.returnValue(open(file_query_response[0][0], 'rb'))


@defer.inlineCallbacks
def get_piecehashes_of(file_hash, dbpool):
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

    bootstrap('/home/nirvik/Pictures', dbpool)
    # bootstrap('/home/nirvik/Documents')
    # bootstrap('/home/nirvik/colleges')
    # readit = get_file('56ae4cf859179e0d32e9733d45d7f714')
    # x.addCallback(readit)
    reactor.run()
