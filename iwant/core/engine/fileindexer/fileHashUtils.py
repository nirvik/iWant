import os
from twisted.enterprise import adbapi
import hashlib
from twisted.internet import defer, reactor
#from piecer import piece_size
import piece

#filename = 'iwant.db'
#dbpool = adbapi.ConnectionPool('sqlite3', filename, check_same_thread=False)

@defer.inlineCallbacks
def bootstrap(folder, dbpool):
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

        #print 'sharing files {0}'.format(share_remaining_files)
        #print 'unsharing files {0}'.format(unshare_remaining_files)
        share_msg = share(share_remaining_files, dbpool)
        unshare_msg = unshare(unshare_remaining_files, dbpool)
        indexing_done = yield index_folder(folder, dbpool)
        defer.returnValue('done')


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
    all_shared_files_from_db = yield dbpool.runQuery('select filename from indexer where share=1')
    relevant_files = filter(lambda x: x[0].startswith(path), all_shared_files_from_db)
    for filename in relevant_files:
        yield dbpool.runQuery('delete from indexer where filename=?',(filename[0],))
    defer.returnValue('done')

@defer.inlineCallbacks
def file_delete_handler(path, dbpool):
    remove_file = yield dbpool.runQuery('delete from indexer where filename=?',(path,))
    defer.returnValue('done')

@defer.inlineCallbacks
def index_folder(folder, dbpool):
    for root, _, filenames in os.walk(folder):
        for filename in filenames:
            destination_path = os.path.join(root, filename)
            x = yield index_file(destination_path, dbpool)
    defer.returnValue('done')

@defer.inlineCallbacks
def index_file(path, dbpool):
    filesize = get_file_size(path)
    filesize_from_db = yield dbpool.runQuery('select size from indexer where filename=?',(path,))
    try:
        if filesize_from_db[0][0] != filesize:
            file_hash, piece_hashes, root_hash = get_file_hashes(path)
            file_index_entry = (filesize, file_hash, piece_hashes, root_hash, path)
            print 'updating the hash'
            yield dbpool.runQuery('update indexer set size=?, hash=?, piecehashes=?, roothash=? where filename=?', (file_index_entry))
            defer.returnValue('done')
    except IndexError:
        print '@index_file {0}'.format(filesize_from_db)
        if len(filesize_from_db)==0:
            file_hash, piece_hashes, root_hash = get_file_hashes(path)
            print 'this is a new entry {0}'.format(path)
            file_index_entry = (path, 1, filesize, file_hash, piece_hashes, root_hash)
            print file_index_entry
            yield dbpool.runQuery('insert into indexer values (?,?,?,?,?,?)', (file_index_entry))
            defer.returnValue('done')
    else:
        pass

def get_file_size(path):
    '''
    return file size in mb
    '''
    return os.stat(path).st_size/(1000.0 * 1000.0)


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

if __name__ == '__main__':
    bootstrap('/home/nirvik/Music/Maa')
    #bootstrap('/home/nirvik/Documents')
    #bootstrap('/home/nirvik/colleges')
    #x = get_file('56ae4cf859179e0d32e9733d45d7f714')
    #x.addCallback(readit)
    reactor.run()
