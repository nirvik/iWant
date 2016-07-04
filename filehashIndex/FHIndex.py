import os
from collections import namedtuple
import hashlib
import json

FileObj = namedtuple('FileObj','filename checksum size')
HIDX_EXTENSION = '.hindex'
PIDX_EXTENSION = '.pindex'

class FileHashIndexer(object):
    def __init__(self , path):
        if not os.path.exists(path):
            raise NotImplementedError
        else:
            self.path = os.path.abspath(path)
            self.hash_index = {}
            self.path_index = {}

    def index(self):
        ''' better would be return a defferred '''
        self._create_file_index()

    def _create_file_index(self):
        hashed_idx_path = os.path.join(self.path,HIDX_EXTENSION)
        filename_idx_path = os.path.join(self.path,PIDX_EXTENSION)

        if os.path.exists(hashed_idx_path):
            data =open(hashed_idx_path).read()
            self.hash_index= json.loads(data)

        if os.path.exists(filename_idx_path):
            data = open(filename_idx_path).read()
            self.path_index = json.loads(data)



        for root,_discard,filenames in os.walk(self.path):
            for filepath in filenames:
                destination_file_path = os.path.join(root,filepath)
                filesize = round(os.path.getsize(destination_file_path) / (1024.0 * 1024.0),2)
                if destination_file_path in self.path_index:
                    sha_checksum = self.path_index[destination_file_path]
                    if self.hash_index[sha_checksum][-1] != filesize:
                        print 'Change in file size'
                        self._delete(destination_file_path)
                    else:
                        continue
                checksum = self._get_hash(destination_file_path)

                fileObject = FileObj(filename=destination_file_path,checksum= checksum,size=filesize)
                self.hash_index[checksum] = fileObject
                self.path_index[destination_file_path] = checksum

        discarded_file_list = []
        for filename in self.path_index:
            if not os.path.exists(filename):
                discarded_file_list.append(filename)

        for files in discarded_file_list:
            self._delete(files)

        self._save_hash_data()

    def _save_hash_data(self):
        hashed_data  = os.path.join(self.path,HIDX_EXTENSION)
        with open(hashed_data,'wb') as f:
            f.write(json.dumps(self.hash_index))
        filepath_data = os.path.join(self.path,PIDX_EXTENSION)
        with open(filepath_data,'wb') as f:
            f.write(json.dumps(self.path_index))

    def _delete(self , pathname):
        checksum = self.path_index[pathname]
        del self.path_index[pathname]
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
        sha_hash = self._get_hash(filename)
        if sha_hash != checksum:
            print 'There has been a change in contents of the file'
            raise NotImplementedError
        return open(filename,'rb')

    @staticmethod
    def _get_hash(filepath):
        sha_hash = hashlib.sha1()
        with open(filepath,'rb') as f:
            buff = f.read()
            sha_hash.update(hashlib.sha1(buff).hexdigest())
        return sha_hash.hexdigest()

    def reduced_index(self):
        red_fn=lambda x:(os.path.basename(x[0]), x[2])
        return json.dumps(dict([(k,red_fn(v)) for k,v in self.hash_index.iteritems()]))

if __name__ == '__main__':
    new_file = FileHashIndexer('/home/nirvik/HandMeShareFolder/')
    new_file.index()
    #print new_file.getFile(u'6792d84bdf59de317d66e84e9f0f97facdfa0b23')
    print new_file.reduced_index()
