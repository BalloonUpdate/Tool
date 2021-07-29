from abc import ABC, abstractmethod

from src.utilities.file import File
from src.utilities.file_comparer import SimpleFileObject


class AbstractServiceProvider(ABC):
    def __init__(self, uploadTool, config):
        self.uploadTool = uploadTool
        self.config = config

    def initialize(self):
        pass

    @abstractmethod
    def fetchBukkit(self):
        pass

    @abstractmethod
    def fetchFragments(self):
        pass

    @abstractmethod
    def deleteObjects(self, paths):
        pass

    @abstractmethod
    def deleteDirectories(self, paths):
        pass

    @abstractmethod
    def uploadObject(self, path, localPath, baseDir, length, hash):
        pass

    def compareFile(self, remoteFile: SimpleFileObject, localRelPath: str, localAbsPath: str):
        return remoteFile.sha1 == File(localAbsPath).sha1

    def cleanup(self):
        pass

    @abstractmethod
    def getProviderName(self):
        pass
