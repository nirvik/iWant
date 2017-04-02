import os
from twisted.enterprise import adbapi
import hashlib
from twisted.internet import defer, reactor
import piece

@defer.inlineCallbacks
def bootstrap(folder, dbpool):
    print 'this is where its fucked up {0}'.format(folder)
    if not os.path.exists(folder):
        raise NotImplementedError
    else:
        all_filenames_response = yield dbpool.runQuery('select filename from indexer')
        all_filenames = set(map(lambda x: x[0], all_filenames_response))
        files_to_be_unshared = set(filter(lambda x: not x.startswith(os.path.abspath(folder)), all_filenames))
        files_to_be_shared = all_filenames - files_to_be_unshared

        all_unshared_files_response = yield dbpool.runQuery('select filename from indexer where share=0')
        all_unshared_files = set(map(lambda x: x[0], all_unshared_files_response))
        all_shared_files = all_filenames - all_unshared_files

        share_remaining_files = files_to_be_shared - all_shared_files
        unshare_remaining_files = files_to_be_unshared - all_unshared_files

        share_msg = share(share_remaining_files, dbpool)
        unshare_msg = unshare(unshare_remaining_files, dbpool)
        indexing_done = yield index_folder(folder, dbpool)

        combined_response = {}
        combined_response['ADD'] = []
        combined_response['DEL'] = []
        combined_response['shared_folder'] = folder
        files_added_metainfo = []
        files_removed_metainfo = []

        for filepath in unshare_remaining_files:
            file_entry = yield dbpool.runQuery('select filename, size, hash, roothash from indexer where filename=?', (filepath,))
            files_removed_metainfo.append(file_entry[0])

        #files_removed_metainfo.extend(removed_files_temp)
        sharing_files = yield dbpool.runQuery('select filename, size, hash, roothash from indexer where share=1')
        files_added_metainfo.extend(sharing_files)
        combined_response['ADD'] = files_added_metainfo
        combined_response['DEL'] = files_removed_metainfo
        defer.returnValue(combined_response)


@defer.inlineCallbacks
def unshare(files, dbpool):
    for f in files:
        yield dbpool.runQuery('update indexer set share=0 where filename=?',(f,))
    defer.returnValue('unshared')

@defer.inlineCallbacks
def share(files, dbpool):
    for f in files:
        yield dbpool.runQuery('update indexer set share=1 where filename=?',(f,))
    defer.returnValue('shared')

@defer.inlineCallbacks
def folder_delete_handler(path, dbpool):
    response = {}
    response['ADD'] = []
    response['DEL'] = []
    response['shared_folder'] = None
    file_property_list = []
    all_shared_files_from_db = yield dbpool.runQuery('select filename from indexer where share=1')
    relevant_files = filter(lambda x: x[0].startswith(path), all_shared_files_from_db)
    for filename in relevant_files:
        file_removed_response = yield dbpool.runQuery('select filename, size, hash, roothash from indexer where filename=?',(filename[0],))
        file_property_list.extend(file_removed_property)
    for filename in relevant_files:
        yield dbpool.runQuery('delete from indexer where filename=?',(filename[0],))
    response['DEL'] = file_property_list
    defer.returnValue(response)

@defer.inlineCallbacks
def file_delete_handler(path, dbpool):
    response = {}
    response['DEL'] = []
    response['ADD'] = []
    response['shared_folder'] = None
    file_property_list = []
    file_removed_response = yield dbpool.runQuery('select filename, size, hash, roothash from indexer where filename=?',(path,))
    file_property_list.extend(file_removed_response)
    remove_file = yield dbpool.runQuery('delete from indexer where filename=?',(path,))
    response['DEL'] = file_proper_list
    defer.returnValue(response)

@defer.inlineCallbacks
def index_folder(folder, dbpool):
    response = {}
    response['DEL'] = []
    response['ADD'] = []
    response['shared_folder'] = None
    file_property_list = []
    for root, _, filenames in os.walk(folder):
        for filename in filenames:
            destination_path = os.path.join(root, filename)
            indexed_file_property = yield index_file(destination_path, dbpool)
            file_property_list.extend(indexed_file_property['ADD'])
    response['ADD'] = file_property_list
    defer.returnValue(file_property_list)

@defer.inlineCallbacks
def index_file(path, dbpool):
    response = {}
    response['DEL'] = []
    response['ADD'] = []
    response['shared_folder'] = None
    filesize = get_file_size(path)
    filesize_from_db = yield dbpool.runQuery('select size from indexer where filename=?',(path,))
    try:
        if filesize_from_db[0][0] != filesize:
            file_hash, piece_hashes, root_hash = get_file_hashes(path)
            file_index_entry = (filesize, file_hash, piece_hashes, root_hash, path)
            print 'updating the hash'
            yield dbpool.runQuery('update indexer set size=?, hash=?, piecehashes=?, roothash=? where filename=?', (file_index_entry))
            file_property_list = [(path, filesize, file_hash, root_hash)]
            response['ADD'] = file_property_list
            defer.returnValue(response)
    except IndexError:
        print '@index_file {0}'.format(filesize_from_db)
        if len(filesize_from_db)==0:
            file_hash, piece_hashes, root_hash = get_file_hashes(path)
            print 'this is a new entry {0}'.format(path)
            file_index_entry = (path, 1, filesize, file_hash, piece_hashes, root_hash)
            yield dbpool.runQuery('insert into indexer values (?,?,?,?,?,?)', (file_index_entry))
            file_property_list = [(path, filesize, file_hash, root_hash)]
            response['ADD'] = file_property_list
            defer.returnValue(response)
    else:
        defer.returnValue([])

def get_file_size(path):
    '''
    return file size in mb
    '''
    return os.stat(path).st_size/(1000.0 * 1000.0)

@defer.inlineCallbacks
def check_hash_present(hash_value, dbpool):
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
    print 'going to get fucked for {0}'.format(filename)
    yield dbpool.runQuery('insert into indexer values (?,?,?,?,?,?)', (file_entry))
    yield dbpool.runQuery('insert into resume values (?,?)', (filename, checksum))

def get_file_hashes(filepath):
    hash_list = ''
    md5_hash = hashlib.md5()
    #chunk_size = piece_size(filepath)
    filesize = get_file_size(filepath)
    chunk_size = piece.piece_size(filesize)
    print 'CHUNK SIZE {0}'.format(chunk_size)
    with open(filepath,'rb') as f:
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
    bootstrap('/home/nirvik/Music/Maa')
    #bootstrap('/home/nirvik/Documents')
    #bootstrap('/home/nirvik/colleges')
    #x = get_file('56ae4cf859179e0d32e9733d45d7f714')
    #x.addCallback(readit)
    reactor.run()
