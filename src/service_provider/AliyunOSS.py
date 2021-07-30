import re
from io import BytesIO, BufferedRandom

import oss2
import yaml

from src.utilities.dir_hash import dir_hash
from src.utilities.file import File
from src.service_provider.AbstractServiceProvider import AbstractServiceProvider


class AliyunOSS(AbstractServiceProvider):
    def __init__(self, uploadTool, config):
        super(AliyunOSS, self).__init__(uploadTool, config)

        self.cache = []  # 缓存的远程文件结构
        self.modified = False  # 是否有过上传行为
        self.rootDir: File = None  # 本地根目录

        access_id = config['access_id']
        access_key = config['access_key']
        region = config['region']
        bucket = config['bucket']
        self.bucket = oss2.Bucket(oss2.Auth(access_id, access_key), region, bucket)
        oss2.defaults.connection_pool_size = 4  # 设置最大并发数限制

        self.cacheFileName = config['cache_file']
        self.headerRules = config['header_rules'] if 'header_rules' in config else []

    def initialize(self, rootDir: File):
        self.rootDir = rootDir

    def fetchDirectory(self, path='', i=''):
        directory = []

        pureName2 = path[:path.rfind('/')]
        pureName2 = pureName2[pureName2.rfind('/') + 1:]
        print(i + pureName2)

        d = []

        for obj in oss2.ObjectIteratorV2(self.bucket, prefix=path, delimiter='/', fetch_owner=True):
            if obj.is_prefix():  # 判断obj为文件夹。
                pureName = obj.key[:obj.key.rfind('/')].replace(path, '')
                d += [[pureName, obj.key]]
                # print(i + 'd: ' + pureName)

            else:  # 判断obj为文件。
                if obj.key == path:
                    continue

                pureName = obj.key[obj.key.rfind('/') + 1:]
                # print(i + 'f: ' + pureName)

                # 因为本地没有缓存文件，所以用不上这段代码
                # if path + pureName == '/' + self.cacheFileName:
                #     continue

                # headers = self.bucket.head_object(obj.key).headers
                # hash = headers['x-oss-meta-hash'] if 'x-oss-meta-hash' in headers else ''
                directory.append({
                    'name': pureName,
                    'length': 0,
                    'hash': ''
                    # 'length': headers['Content-Length'],
                    # 'hash': hash
                })

        for D in d:
            # print(i+'D: '+D[0])
            directory.append({
                'name': D[0],
                'children': self.fetchDirectory(D[1], i + '    ')
            })

        return directory

    def fetchAll(self):
        if self.exists(self.cacheFileName):
            self.cache = yaml.safe_load(self.downloadObject(self.cacheFileName).read())
            print('缓存已找到 ' + self.cacheFileName)
            return self.cache

        return self.fetchDirectory()

    def fetchFragments(self):
        result = []
        for upload_info in oss2.MultipartUploadIterator(self.bucket):
            result += [upload_info.key]
            # self.fragments += [upload_info.key, upload_info.upload_id]
        return result

    def deleteObjects(self, paths):
        def del_(paths_):
            self.bucket.batch_delete_objects(paths_)

        paths_ = paths[:]
        while len(paths_) > 999:
            del_(paths_[:999])
            paths_ = paths_[999:]
        if len(paths_) > 0:
            del_(paths_)
        self.modified = True

    def deleteDirectories(self, paths):
        self.bucket.batch_delete_objects([dir + '/' for dir in paths])
        self.modified = True

    def uploadObject(self, path, localPath, baseDir, length, hash):
        file = File(localPath)
        # headers = {'x-oss-meta-hash': file.sha1, **self.getHeaders(file.relPath(baseDir))}
        headers = self.getHeaders(file.relPath(baseDir))

        if self.uploadTool.debugMode and len(headers) > 0:
            print(headers)

        oss2.resumable_upload(self.bucket, path, localPath, num_threads=4, headers=headers)
        self.modified = True

    def downloadObject(self, path):
        buf = BufferedRandom(BytesIO())
        for chunk in self.bucket.get_object(path):
            buf.write(chunk)
        buf.seek(0)
        return buf

    def makeDirectory(self, path):
        if not self.exists(path):
            self.bucket.put_object(key=path+'/', data='')
        self.modified = True

    def exists(self, path):
        return self.bucket.object_exists(path)

    def cleanup(self):
        # 实际上传文件之后，需要更新缓存文件
        if self.modified:
            print('正在更新缓存...')
            cache = dir_hash(self.rootDir)

            if self.exists(self.cacheFileName):
                self.deleteObjects([self.cacheFileName])

            cacheContent = yaml.safe_dump(cache).encode('utf-8')
            self.bucket.put_object(key=self.cacheFileName, data=cacheContent)

            print('缓存已更新 ' + self.cacheFileName)

    def getName(self):
        return '阿里云对象存储服务(OSS)'

    def getHeaders(self, path):
        headers = {}

        if isinstance(self.headerRules, list):
            for rule in self.headerRules:
                pattern = rule['pattern']
                hds = rule['headers']
                if re.search(pattern, path) is not None:
                    headers.update(hds)

        return headers
