import io
from io import BufferedRandom
from stat import S_ISDIR

import paramiko as paramiko
import yaml

from src.service_provider.AbstractServiceProvider import AbstractServiceProvider
from src.utilities.dir_hash import dir_hash
from src.utilities.file import File


class SFTPClient:
    def __init__(self, host, port, user, use_pkey, pkey_file, password):
        self.host = host
        self.port = port
        self.user = user
        self.usePkey = use_pkey
        self.pkeyFile = pkey_file
        self.password = password

        self.transport = paramiko.Transport((host, int(port)))
        self.sftp = None

    def open(self):
        print(f"正在连接到 {self.host}:{self.port}...")
        # 自动添加远端主机到 known_hosts 中
        # 从 transport 实例创建似乎并不需要
        # self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if self.usePkey:
            print("使用公钥进行身份验证...")
            pkey = paramiko.RSAKey.from_private_key_file(self.pkeyFile, self.password)
            self.transport.connect(username=self.user, password=self.password, pkey=pkey)
        else:
            print("使用密码进行身份验证...")
            self.transport.connect(username=self.user, password=self.password)
        # 从 transport 实例创建 SFTP 客户端实例
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        print(f"已连接到 {self.host}:{self.port}.")

    def close(self):
        self.transport.close()
        print(f"已从 {self.host}:{self.port} 断开.")

    def upload_file(self, local_path_or_file_buf, remote_path: str, is_file_buf: bool):
        # 区分从缓冲区上传和从本地路径上传，其实可以用 isInstance() 判断参数类型
        if is_file_buf:
            self.sftp.putfo(local_path_or_file_buf, self.abspath(remote_path))
        else:
            self.sftp.put(local_path_or_file_buf, self.abspath(remote_path))

    def open_remote_file(self, filename: str):
        buf = BufferedRandom(io.BytesIO())
        # 打开远端文件句柄
        remote_file_obj = self.sftp.open(self.abspath(filename), 'r')
        buf.write(remote_file_obj.read())
        remote_file_obj.close()
        buf.seek(0)
        return buf

    def delete_file(self, path: str):
        try:
            self.sftp.remove(self.abspath(path))
        except Exception:
            print('删除失败，文件可能不存在')

    def delete_directory(self, path: str):
        try:
            self.sftp.rmdir(self.abspath(path))
        except Exception:
            print('删除失败，目录可能不存在')

    def list_files(self, path: str):
        # 读取文件列表（包含文件描述符，用于快速判断是否为目录）
        return self.sftp.listdir_attr(self.abspath(path))

    # 设置工作目录
    def swd(self, path: str):
        self.sftp.chdir(self.abspath(path))

    def create_directory(self, path: str):
        self.sftp.mkdir(path, 0o755)

    # 处理相对路径为绝对路径，避免问题
    def abspath(self, path: str):
        return self.sftp.normalize(path)


class SFTP(AbstractServiceProvider):
    def __init__(self, upload_tool, config):
        super(SFTP, self).__init__(upload_tool, config)

        self.cache = []  # 缓存的远程文件结构
        self.modified = False  # 是否有过上传行为
        self.rootDir: File = None  # 本地根目录

        self.host = config['host']
        self.port = config['port']
        self.user = config['user']
        self.usePkey = config['usePkey']
        self.pkeyFile = config['pkeyFile']
        self.passwd = config['password']
        self.basePath = config['basePath']
        self.cacheFileName = config['cacheFile']

        self.sftp = SFTPClient(self.host, self.port, self.user, self.usePkey, self.pkeyFile, self.passwd)

    def initialize(self, root_dir: File):
        self.rootDir = root_dir
        self.sftp.open()
        # setWorkDir 失败意味目录不存在
        try:
            self.sftp.swd(self.basePath)
        except IOError:
            self.sftp.create_directory(self.basePath)
        self.sftp.swd(self.basePath)

    def list_recursively(self, path='.'):
        # 保存所有文件的列表
        result = []

        # 获取当前指定目录下的所有目录及文件，包含属性值
        for entry in self.sftp.list_files(path):
            filename = entry.filename
            full_path = self.sftp.abspath(f"{path}/{filename}")
            # 忽略缓存文件
            if full_path == self.sftp.abspath(self.cacheFileName):
                continue
            # 如果是目录，则添加并递归处理该目录
            if S_ISDIR(entry.st_mode):
                result.append({'name': filename, 'children': self.list_recursively(full_path)})
            else:
                result.append({'name': filename, 'length': -1, 'hash': ''})
        return result

    def fetchAll(self):
        # 尝试读取缓存
        try:
            self.cache = yaml.safe_load(self.sftp.open_remote_file(self.cacheFileName))
            print('缓存已找到 '+self.cacheFileName)
            return self.cache
        except IOError:
            # 未找到缓存，读取远程目录结构，准备全量上传
            return self.list_recursively()

    def deleteObjects(self, files):
        for file in files:
            self.sftp.delete_file(file)
        self.modified = True

    def deleteDirectories(self, paths):
        for path in paths:
            self.sftp.delete_directory(path)
        self.modified = True

    def uploadObject(self, remote_path, local_path, base_dir, length, file_hash):
        self.sftp.upload_file(local_path, remote_path, False)
        self.modified = True

    def makeDirectory(self, path):
        self.sftp.create_directory(path)
        self.modified = True

    def cleanup(self):
        if self.modified:
            print('正在更新缓存...')
            cache = dir_hash(self.rootDir)
            # 虽然可以直接修改，但是删除重传就完事了
            try:
                self.sftp.delete_file(self.cacheFileName)
            except IOError:
                pass
            buf = BufferedRandom(io.BytesIO())
            buf.write(yaml.safe_dump(cache, sort_keys=False).encode('utf-8'))
            buf.seek(0)
            self.sftp.upload_file(buf, self.cacheFileName, True)
            print(f'缓存已更新 {self.cacheFileName}')
        self.sftp.close()

    def getName(self):
        return 'SFTP ' + self.host + ':' + str(self.port)
