import os, sys
from collections import namedtuple
import hashlib
import json
import pickle
import progressbar
from piece import piece_size
FileObj = namedtuple('FileObj','filename checksum size pieceHashes')

class FileHashIndexer(object):

    HIDX_EXTENSION = '.hindex'
    PIDX_EXTENSION = '.pindex'
    #PIECE_SIZE = 16000

    def __init__(self , path, config_folder, bootstrap=False):
        self.hash_index = {}
        self.path_index = {}
        self.current_path = config_folder

        hashed_idx_path = os.path.join(self.current_path, FileHashIndexer.HIDX_EXTENSION)
        filename_idx_path = os.path.join(self.current_path, FileHashIndexer.PIDX_EXTENSION)
        self.state = "INDEX"

        try:
            self.hash_index = self.loadJSON(hashed_idx_path)
            self.path_index = self.loadJSON(filename_idx_path)
        except:
            raise NotImplementedError

        if bootstrap:
            # We need to remove files which doesnot belong to the directory peer is sharing
            if os.path.exists(path):
                files_to_be_deleted = filter(lambda x: not x.startswith(os.path.abspath(path)),\
                        self.path_index.keys())
                if len(files_to_be_deleted) > 0:
                    print 'Deleting.. '
                for count, files in enumerate(files_to_be_deleted):
                    self._delete(files)
                self._save_hash_data()

        if not os.path.exists(path):
            raise NotImplementedError
            self.state = "CANNOT INDEX"
        else:
            self.path = os.path.abspath(path)

    def index(self):
        '''
        Check how asynchronous deferred works
        '''
        self._create_file_index()

    @staticmethod
    def getfilesize(path):
        return float(os.path.getsize(path))

    @staticmethod
    def loadJSON(path):
        '''
            Mission to change from pickle to json
        '''
        with open(path,'rb') as f:
            data = f.read()
        try:
            json_data = pickle.loads(data)  # json.loads(data)
        except:
            json_data = {}
        return json_data

    @staticmethod
    def number_of_files_in(path):
        count = 0
        for _, _, filenames in os.walk(path):
            for filename in filenames:
                count+=1
        return count

    def compute_hash_diff_file(self, destination_file_path, singleFile=False):
        computed_file_size = self.getfilesize(destination_file_path)
        filesize = computed_file_size/ (1000.0 * 1000.0)
        if destination_file_path in self.path_index:
            md5_checksum = self.path_index[destination_file_path]
            if self.hash_index[md5_checksum][-2] != filesize:
                # print 'Change in file size'
                self._delete(destination_file_path)
            else:
                return
        checksum, pieceHashes = self.get_hash(destination_file_path)
        fileObject = FileObj(filename=destination_file_path, \
                checksum=checksum,size=filesize, pieceHashes=pieceHashes)
        self.hash_index[checksum] = fileObject
        self.path_index[destination_file_path] = checksum

        if singleFile:  # if only one file is updated then save it
            self._save_hash_data()

    def _create_file_index(self):
        if self.state == "CANNOT INDEX":
            return
        total = self.number_of_files_in(self.path)
        count = 0
        self.bar = progressbar.ProgressBar(maxval=total,\
                widgets=[progressbar.Bar('=','[',']'),' ', progressbar.Percentage()]).start()
        print 'Indexing files in the shared folder'
        for root,_discard,filenames in os.walk(self.path):
            for filepath in filenames:
                # print '{0} : Processing'.format(filepath)
                destination_file_path = os.path.join(root, filepath)
                self.compute_hash_diff_file(destination_file_path)
                count+=1
                self.bar.update(count)
        self.bar.finish()

        discarded_file_list = []
        for filename in self.path_index:
            if not os.path.exists(filename):
                discarded_file_list.append(filename)

        for files in discarded_file_list:
            self._delete(files)
            print 'discarding {0}'.format(files)
        self._save_hash_data()


    def _save_hash_data(self):
        hashed_data  = os.path.join(self.current_path, FileHashIndexer.HIDX_EXTENSION)
        with open(hashed_data,'wb') as f:
            f.write(pickle.dumps(self.hash_index))
        filepath_data = os.path.join(self.current_path, FileHashIndexer.PIDX_EXTENSION)
        with open(filepath_data,'wb') as f:
            f.write(pickle.dumps(self.path_index))
        return (self.hash_index, self.path_index)

    def _delete(self , pathname):
        checksum = self.path_index[pathname]
        del self.path_index[pathname]
        '''
            when a file is moved from subdirectory to parent
            and then moved again from parent to subdirectory,
            the path of the file changes , but not the checksum value.
            Therefore, delete from the hash_index only when the pathname
            is equal to pathname saved in the hash_index value.
            The checksum key of the hash_index will always point to
            the correct filepath.
        '''
        try:
            if self.hash_index[checksum][0] == pathname:
                del self.hash_index[checksum]
        except Exception as e:
            print e
            print 'really have to handle this shitty error'

    def getFile(self,fileHashIndex):
        if fileHashIndex not in self.hash_index:
            print 'This file is not present with us '
            self._create_file_index()
            raise NotImplementedError
        filename , checksum , size, pieceHashes = self.hash_index[fileHashIndex]
        if not os.path.exists(filename):
            print 'There has been a change in directory of the path'
            raise NotImplementedError
        md5_hash, hash_string = self.get_hash(filename)
        if md5_hash != checksum:
            print 'There has been a change in contents of the file'
            raise NotImplementedError
        return open(filename,'rb')

    @staticmethod
    def get_hash(filepath):
        hash_string = ''
        md5_hash = hashlib.md5()
        file_size = os.path.getsize(filepath) / (1000.0 * 1000.0)  # converting size to MB
        chunk_size = piece_size(file_size)
        with open(filepath,'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                md5_hash.update(chunk)
                piece_hash = hashlib.md5()
                piece_hash.update(chunk)
                hash_string += piece_hash.hexdigest()
        return md5_hash.hexdigest(), hash_string

    def reduced_index(self):
        red_fn=lambda x:(os.path.basename(x[0]), x[2], x[3])
        return dict([(k,red_fn(v)) for k,v in self.hash_index.iteritems()])

if __name__ == '__main__':
    new_file = FileHashIndexer('/home/nirvik/Pictures/', '/home/nirvik/.iwant/')
    new_file.index()
    #d = new_file.hash_index
    #print new_file.getFile(u'6792d84bdf59de317d66e84e9f0f97facdfa0b23')
    #print new_file.reduced_index()
