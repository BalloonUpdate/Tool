from abc import ABC, abstractmethod

from src.utilities.file import File
from src.utilities.file_comparer import SimpleFileObject


class AbstractServiceProvider(ABC):
    def __init__(self, uploadTool, config):
        self.uploadTool = uploadTool
        self.config = config

    def initialize(self, rootDir: File):
        """初始化回调
        :param rootDir: 本地根目录
        """
        pass

    @abstractmethod
    def fetchAll(self):
        """获取远程目录结构回调"""
        pass

    def fetchFragments(self):
        """获取文件碎片回调"""
        return []

    @abstractmethod
    def deleteObjects(self, paths):
        pass

    @abstractmethod
    def deleteDirectories(self, paths):
        pass

    @abstractmethod
    def uploadObject(self, path, localPath, baseDir, length, hash):
        """文件上传回调
        :param path: 相对路径
        :param localPath: 本地文件绝对路径
        :param baseDir: 本地根目录的路径
        :param length: 文件大小
        :param hash: 文件校验
        """
        pass

    def compareFile(self, remote: SimpleFileObject, local: str, path: str):
        """文件对比回调
        :param remote: 远程文件对象
        :param local: 本地文件路径
        :param path: 相对路径
        """
        return remote.sha1 == File(local).sha1

    def cleanup(self):
        """清理退出回调"""
        pass

    @abstractmethod
    def getName(self):
        """可阅读的服务提供商的名字"""
        pass

