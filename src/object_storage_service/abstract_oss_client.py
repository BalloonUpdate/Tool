from abc import ABC, abstractmethod


class AbstractOssClient(ABC):
    def __init__(self, **configs):
        self.config = {}
        for k, v in configs.items():
            self.config[k] = v

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
    def uploadObject(self, path, localPath):
        pass

    @abstractmethod
    def getProviderName(self):
        pass
