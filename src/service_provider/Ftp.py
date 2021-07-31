import calendar
import io
import os
import ssl
import time
from ftplib import FTP as _FTP, FTP_TLS
from io import BufferedRandom

import yaml

from src.service_provider.AbstractServiceProvider import AbstractServiceProvider
from src.utilities.dir_hash import dir_hash
from src.utilities.file import File
from src.utilities.file_comparer import SimpleFileObject
from src.utilities.glue import glue


class FtpFileObject:
    def __init__(self, name: str, length: int, modified: int):
        self.name = name
        self.modified = modified
        self.length = length

    @property
    def isFile(self):
        return self.length >= 0


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
            self.ftp = _FTP()
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

    def uploadFile(self, file: File, path: str):
        if not file.exists:
            raise FileNotFoundError(f"'{file.path}' not found")

        if file.isDirectory:
            raise IsADirectoryError(f"'{file.path}' is not a file")

        with open(file.path, 'rb') as ff:
            self.ftp.storbinary('STOR ' + path, ff)

    def uploadBinary(self, buf: io.RawIOBase, path: str):
        self.ftp.storbinary('STOR ' + path, buf)

    def downloadBinary(self, filename, buffer_size=4 * 1024 * 1024):
        buf = BufferedRandom(io.BytesIO(), buffer_size=buffer_size)

        def cb(chunk):
            buf.write(chunk)

        self.ftp.retrbinary('RETR ' + filename, cb)
        return buf

    def downloadAsText(self, filename, encoding='utf-8'):
        buf = self.downloadBinary(filename)
        buf.seek(0)

        return buf.read().decode(encoding)

    def deleteFile(self, path: str):
        self.ftp.delete(path)

    def deleteDirectory(self, path: str):
        self.ftp.rmd(path)

    def listFiles(self, path=''):
        """列出详细文件信息"""
        files = []
        for f in self.mlsd(path):
            isFile = f[1]['type'] == 'file'
            files += [FtpFileObject(**{
                'name': f[0],
                'length': int(f[1]['size']) if isFile else -1,
                'modified': int(f[1]['modify'])
            })]
        return files

    def exists(self, path):
        if path.endswith('/'):
            path = path[:-1]
        basename = os.path.basename(path)
        dirname = os.path.dirname(path)
        return basename in [os.path.basename(f) for f in self.nlst(dirname)]

    # 低级API

    def mlsd(self, path=''):
        """列出当前目录下的文件信息"""
        return [a for a in self.ftp.mlsd(path)]

    def nlst(self, path=''):
        """列出当前目录下的文件名"""
        return self.ftp.nlst(path)

    def cd(self, path: str):
        """获取当前工作目录"""
        self.ftp.cwd(path)

    def pwd(self):
        """切换当前工作目录"""
        return self.ftp.pwd()

    def mkdir(self, path: str):
        """创建文件夹"""
        self.ftp.mkd(path)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class Ftp(AbstractServiceProvider):
    def __init__(self, uploadTool, config):
        super(Ftp, self).__init__(uploadTool, config)

        self.cache = []  # 缓存的远程文件结构
        self.modified = False  # 是否有过上传行为
        self.rootDir: File = None  # 本地根目录

        self.host = config['host']
        self.port = config['port']
        self.user = config['user']
        self.passwd = config['password']
        self.basePath = config['base_path']
        self.secure = config['secure']
        self.prot_p = config['prot_p']
        self.cacheFileName = config['cache_file']

        # 补上末尾的/
        self.basePath = self.basePath + '/' if not self.basePath.endswith('/') else self.basePath

        self.ftp = FtpClient(self.host, self.port, self.user, self.passwd, self.secure, self.prot_p)

    def initialize(self, rootDir: File):
        self.rootDir = rootDir
        self.ftp.open()

        # 创建根目录
        if self.basePath != '/' and not self.ftp.exists(self.basePath):
            self.ftp.mkdir(self.basePath)

    def fetchDirectory(self, path='/'):
        self.ftp.cd(self.basePath + (path[1:] if path.startswith('/') else path))
        print(f"cd into: {self.ftp.pwd()}")

        result = []

        for fileObj in self.ftp.listFiles():
            filename = fileObj.name
            isFile = fileObj.isFile

            if path + filename == '/' + self.cacheFileName:
                continue

            if isFile:
                result += [{'name': filename, 'length': -1, 'hash': ''}]
            else:
                result += [{'name': filename, 'children': self.fetchDirectory(path + filename + '/')}]

        return result

    def fetchAll(self):
        if self.ftp.exists(self.basePath + self.cacheFileName):
            self.cache = yaml.safe_load(self.ftp.downloadAsText(self.basePath + self.cacheFileName))
            print('缓存已找到 '+self.cacheFileName)
            return self.cache

        return self.fetchDirectory()

    def deleteObjects(self, paths):
        for f in paths:
            self.ftp.deleteFile(self.basePath + f)
        self.modified = True

    def deleteDirectories(self, paths):
        for f in paths:
            self.ftp.deleteDirectory(self.basePath + f)
        self.modified = True

    def uploadObject(self, path, localPath, baseDir, length, hash):
        localFile = File(localPath)

        layers = path.split('/')
        _layers = [''] + [
            glue(layers[:level + 1], '/')
            for level in range(0, len(layers) - 1)
        ]

        for i in range(0, len(_layers) - 1):
            parent = _layers[i]
            child = _layers[i + 1]

            # self.ftp.cd(self.basePath + parent)
            if not self.ftp.exists(self.basePath + child):
                print('mkdir: ' + child)
                self.ftp.mkdir(self.basePath + child)

        self.ftp.uploadFile(localFile, self.basePath + path)
        self.modified = True

    def makeDirectory(self, path):
        if not self.ftp.exists(self.basePath + path):
            self.ftp.mkdir(self.basePath + path)
        self.modified = True

    def cleanup(self):
        # 实际上传文件之后，需要更新缓存文件
        if self.modified:
            print('正在更新缓存...')
            cache = dir_hash(self.rootDir)

            if self.ftp.exists(self.basePath + self.cacheFileName):
                self.ftp.deleteFile(self.basePath + self.cacheFileName)

            buf = BufferedRandom(io.BytesIO())
            buf.write(yaml.safe_dump(cache, sort_keys=False).encode('utf-8'))
            buf.seek(0)
            self.ftp.uploadBinary(buf, self.basePath + self.cacheFileName)

            print('缓存已更新 '+self.cacheFileName)

        self.ftp.close()

    def getName(self):
        return 'FTP ' + self.host + ':' + str(self.port)
