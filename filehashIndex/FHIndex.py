import os
from collections import namedtuple
import hashlib
import json

FileObj = namedtuple('FileObj','filename checksum size')
HIDX_EXTENSION = '.hindex'
PIDX_EXTENSION = '.pindex'

class FileHashIndexer(object):
    def __init__(self , path):
        self.hash_index = {}
        self.path_index = {}
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        hashed_idx_path = os.path.join(self.current_path,HIDX_EXTENSION)
        filename_idx_path = os.path.join(self.current_path,PIDX_EXTENSION)

        if os.path.exists(hashed_idx_path):
            self.hash_index = self.loadJSON(hashed_idx_path)

        if os.path.exists(filename_idx_path):
            self.path_index = self.loadJSON(filename_idx_path)

        if not os.path.exists(path):
            if path in self.path_index:
                self._delete(path)
                self._save_hash_data()
            else:
                raise NotImplementedError
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
        with open(path,'rb') as f:
            data = f.read()
        try:
            json_data = json.loads(data)
        except:
            json_data = {}
        return json_data

    def compute_hash_diff_file(self, destination_file_path, singleFile=False):
        computed_file_size = self.getfilesize(destination_file_path)
        filesize = computed_file_size/ (1024.0 * 1024.0)
        if destination_file_path in self.path_index:
            sha_checksum = self.path_index[destination_file_path]
            if self.hash_index[sha_checksum][-1] != filesize:
                print 'Change in file size'
                self._delete(destination_file_path)
            else:
                return
        checksum = self.get_hash(destination_file_path)
        fileObject = FileObj(filename=destination_file_path,checksum= checksum,size=filesize)
        self.hash_index[checksum] = fileObject
        self.path_index[destination_file_path] = checksum

        if singleFile:  # if only one file is updated then save it
            self._save_hash_data()

    def _create_file_index(self):
        for root,_discard,filenames in os.walk(self.path):
            for filepath in filenames:
                destination_file_path = os.path.join(root,filepath)
                self.compute_hash_diff_file(destination_file_path)

        discarded_file_list = []
        for filename in self.path_index:
            if not os.path.exists(filename):
                discarded_file_list.append(filename)

        for files in discarded_file_list:
            self._delete(files)
            print 'discarding {0}'.format(files)
        self._save_hash_data()


    def _save_hash_data(self):
        hashed_data  = os.path.join(self.current_path,HIDX_EXTENSION)
        with open(hashed_data,'wb') as f:
            f.write(json.dumps(self.hash_index))
        filepath_data = os.path.join(self.current_path,PIDX_EXTENSION)
        with open(filepath_data,'wb') as f:
            f.write(json.dumps(self.path_index))

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
        if self.hash_index[checksum][0] == pathname:
            del self.hash_index[checksum]

    def getFile(self,fileHashIndex):
        if fileHashIndex not in self.hash_index:
            print 'This file is not present with us '
            self._create_file_index()
            raise NotImplementedError
        filename , checksum , size = self.hash_index[fileHashIndex]
        if not os.path.exists(filename):
            print 'There has been a change in directory of the path'
            raise NotImplementedError
        sha_hash = self.get_hash(filename)
        if sha_hash != checksum:
            print 'There has been a change in contents of the file'
            raise NotImplementedError
        return open(filename,'rb')

    @staticmethod
    def get_hash(filepath):
        sha_hash = hashlib.sha1()
        with open(filepath,'rb') as f:
            buff = f.read()
            sha_hash.update(hashlib.sha1(buff).hexdigest())
        return sha_hash.hexdigest()

    def reduced_index(self):
        red_fn=lambda x:(os.path.basename(x[0]), x[2])
        return json.dumps(dict([(k,red_fn(v)) for k,v in self.hash_index.iteritems()]))

if __name__ == '__main__':
    new_file = FileHashIndexer('/home/nirvik/Pictures/')
    new_file.index()
    #print new_file.getFile(u'6792d84bdf59de317d66e84e9f0f97facdfa0b23')
    print new_file.reduced_index()
