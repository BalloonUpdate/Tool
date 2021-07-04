import calendar
import json
import os
import ssl
import time
from ftplib import FTP, FTP_TLS

from ci.file import File
from src.service_provider.abstract_service_provider import AbstractServiceProvider
from src.utilities.file_comparer import SimpleFileObject
from src.utilities.glue import glue


class FtpClient:
    def __init__(self, host, port, user, passwd, secure, prot_p):
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.secure = secure
        self.prot_p = prot_p

        if secure:
            context = ssl.SSLContext()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            self.ftp = FTP_TLS(context=context)
        else:
            self.ftp = FTP()
        self.ftp.encoding = "utf-8"

    def open(self, timeout=5000):
        print(f"connect to {self.host}:{self.port}")
        self.ftp.connect(self.host, self.port, timeout=timeout)
        self.ftp.login(self.user, self.passwd)

        if self.secure and self.prot_p:
            self.ftp.prot_p()

        print(f'\n------来自{self.host}:{self.port}的消息------')
        print(self.ftp.getwelcome())
        print('')

    def close(self):
        self.ftp.close()
        print(f"disconnected from {self.host}:{self.port}")

    def uploadFile(self, localFile: File, remoteFile: str):
        if not localFile.exists:
            raise FileNotFoundError(f"'{localFile.path}' not found")

        if localFile.isDirectory:
            raise IsADirectoryError(f"'{localFile.path}' is not a file")

        with open(localFile.path, 'rb') as ff:
            self.ftp.storbinary('STOR ' + remoteFile, ff)

    def deleteFile(self, remoteFile: str):
        self.ftp.delete(remoteFile)

    def deleteDirectory(self, remoteDir: str):
        self.ftp.rmd(remoteDir)

    def mlsd(self):
        return [a for a in self.ftp.mlsd()]

    def fileListByMlsd(self, path: str):
        return [a[0] for a in self.ftp.mlsd(path)]

    def nlst(self):
        return self.ftp.nlst()

    def cd(self, path: str):
        self.ftp.cwd(path)

    def pwd(self):
        return self.ftp.pwd()

    def mkdir(self, path: str):
        self.ftp.mkd(path)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class Ftp(AbstractServiceProvider):
    def __init__(self, config):
        super(Ftp, self).__init__(config)

        self.cacheFile = File('ftp.cache.json')
        self.cache = json.loads(self.cacheFile.content) if self.cacheFile.exists else []

        if self.cacheFile.exists:
            print('cache loaded 缓存已加载')

        self.host = config['host']
        self.port = config['port']
        self.user = config['user']
        self.passwd = config['password']
        self.basePath = config['base_path']
        self.secure = config['secure']
        self.prot_p = config['prot_p']

        self.ftp = FtpClient(self.host, self.port, self.user, self.passwd, self.secure, self.prot_p)

    def findInCache(self, path: str):
        dirname = os.path.dirname(path)
        basename = os.path.basename(path)

        current = self.cache

        for name in dirname.split('/'):
            if name == '' or current is None:
                continue

            for child in current:
                if child['name'] == name:
                    current = child['children']
                    break

        if current is None:
            return None

        for child in current:
            if child['name'] == basename:
                return child
        return None

    def initialize(self):
        self.ftp.open()

    def fetchDirectory(self, path='', i=''):
        # print(i + path)

        print(f"cd into: {self.ftp.pwd()}")
        self.ftp.cd(self.basePath + path)

        result = []

        for fileObj in self.ftp.mlsd():
            filename = fileObj[0]
            filetype = fileObj[1]['type']
            modify = int(fileObj[1]['modify'])
            length = int(fileObj[1]['size'] if filetype == 'file' else '-1')

            # Convert to timestamp
            modify = calendar.timegm(time.strptime(str(modify), '%Y%m%d%H%M%S'))

            timezoneOffset = self.config['timezone_offset']
            if timezoneOffset != 0:
                modify += 60 * 60 * timezoneOffset

            if filetype == 'file':
                result += [{
                    'name': filename,
                    'length': length,
                    'hash': str(modify)+'/'+str(length)
                }]

            if filetype == 'dir':
                prefix = (path+'/') if path != '' else ''
                result += [{
                    'name': filename,
                    'children': self.fetchDirectory(prefix+filename, i + '    ')
                }]

        return result

    def fetchBukkit(self):
        return self.fetchDirectory()

    def fetchFragments(self):
        return []

    def deleteObjects(self, paths):
        for f in paths:
            self.ftp.deleteFile(self.basePath + f)
            # print('delete file: /' + f)

    def deleteDirectories(self, paths):
        for f in paths:
            self.ftp.deleteDirectory(self.basePath + f)
            # print('delete directory: /' + f)

    def uploadObject(self, path, localPath, length, hash):
        localFile = File(localPath)

        # check whether directory exists
        layers = path.split('/')
        _layers = [''] + [
            glue(layers[:level+1], '/')
            for level in range(0, len(layers)-1)
        ]
        # print('---------   ' + str(_layers)+'     Raw: '+str(layers))

        # indent = ''
        for i in range(0, len(_layers)-1):
            parent = _layers[i]
            child = _layers[i+1]

            res = self.ftp.fileListByMlsd(self.basePath + parent)
            # print(indent+'* '+parent+'  |  '+child+'  ===  ' + self.basePath + parent+'  mlsd: '+str(res))

            if os.path.basename(child) not in res:
                # print(indent+'mkdir: '+child)
                print('mkdir: ' + child)
                self.ftp.mkdir(self.basePath + child)
            # indent += '    '

        # print(f"upload {localFile.path} => /{path}")
        self.ftp.uploadFile(localFile, self.basePath + path)

    def compareFile(self, remoteFile: SimpleFileObject, localRelPath: str, localAbsPath: str):
        localCache = self.findInCache(localRelPath)
        r_hash = remoteFile.sha1
        l_hash = localCache['hash'] if localCache is not None else ''
        r = r_hash == l_hash
        # print(str(r)+'   /   '+r_hash+' / '+l_hash)
        return r

    def cleanup(self):
        print('prepare to save cache 正在更新缓存')

        cache = self.fetchDirectory()

        if not self.cacheFile.exists:
            self.cacheFile.create()

        with open(self.cacheFile.path, "w+", encoding="utf-8") as f:
            f.write(json.dumps(cache, ensure_ascii=False, indent=4))

        print('cache saved 缓存已更新')

        self.ftp.close()

    def getProviderName(self):
        return 'FTP '+self.host+':'+str(self.port)
