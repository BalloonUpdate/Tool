import os
import shutil
import time
import hashlib
import pathlib


# 2020年12月16日23:25:45
class File:
    def __init__(self, filePath):
        if not isinstance(filePath, str):
            raise TypeError(f"the file path must be a string, not '{filePath}' ({type(filePath)})")

        if os.path.isabs(filePath):
            self.__absPath = os.path.abspath(filePath).replace("\\", "/")
        else:
            self.__absPath = os.path.abspath(os.path.join(os.getcwd(), filePath)).replace("\\", "/")

    @property
    def isDirectory(self):
        return os.path.isdir(self.path)

    @property
    def isFile(self):
        return os.path.isfile(self.path)

    @property
    def isLink(self):
        return os.path.islink(self.path)

    @property
    def exists(self):
        return os.path.exists(self.path)

    def rename(self, newName):
        os.rename(self.path, self.parent.append(newName).path)

    def mkdirs(self):
        if not self.exists:
            os.makedirs(self.path)

    def makeParentDirs(self):
        if not self.parent.exists:
            os.makedirs(self.parent.path)

    def create(self, content=None):
        if not self.exists:
            self.makeParentDirs()

            if content is not None:
                with open(self.path, "x+", encoding="utf-8") as f:
                    f.write(content)
            else:
                pathlib.Path(self.path).touch()
            return True
        return False

    @property
    def content(self):
        if not self.exists:
            raise FileNotFoundError(f"'{self.path}' is not found")

        if self.isDirectory:
            raise IsADirectoryError(f"'{self.path}' is not a file")

        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()

    @content.setter
    def content(self, content):
        if self.exists and self.isDirectory:
            raise IsADirectoryError(f"'{self.path}' is not a file")

        with open(self.path, "w+", encoding="utf-8") as f:
            f.write(content)

    @property
    def name(self):
        return os.path.basename(self.path)

    @property
    def length(self):
        if not self.exists:
            raise FileNotFoundError(f"'{self.path}' is not found")

        if not self.isFile:
            raise IsADirectoryError(f"'{self.path}' is not a file")

        return os.path.getsize(self.path)

    @property
    def files(self):
        if not self.exists:
            raise FileNotFoundError(f"'{self.path}' is not found")

        if self.isFile:
            raise NotADirectoryError(f"'{self.path}' is not a Directory")

        files = [
            File(os.path.join(self.path, f))
            for f in os.listdir(self.path)
        ]

        return files

    @property
    def isDirty(self):
        if not self.exists:
            raise FileNotFoundError(f"'{self.path}' is not found")

        if self.isFile:
            return self.length > 0

        return len(self.files) > 0

    def clear(self):
        if not self.exists:
            return

        if self.isFile:
            self.content = ""
            return

        for pf in self.files:
            pf.delete()

    def copyTo(self, dist):
        dist = dist if isinstance(dist, File) else File(dist)

        assert self.exists, f"{self.path} is not found"

        if dist.exists:
            dist.delete()

        if self.isFile:
            shutil.copy2(self.path, dist.path, follow_symlinks=False)
        else:
            shutil.copytree(self.path, dist.path, symlinks=False)

    def moveTo(self, dist):
        dist = dist if isinstance(dist, File) else File(dist)

        assert self.exists, f"{self.path} is not found"

        if dist.exists:
            dist.delete()

        shutil.move(self.path, dist.path)
        # os.renames(self.path, dist.path)

    @property
    def path(self):
        return self.__absPath.replace("\\", "/")

    @property
    def windowsPath(self):
        return self.__absPath.replace("/", "\\")

    def relPath(self, baseDir=None):
        if baseDir is None:
            return os.path.relpath(self.path).replace("\\", "/")

        bd = baseDir if isinstance(baseDir, File) else File(baseDir)
        if bd.isDirectory:
            return os.path.relpath(self.path, bd.path).replace("\\", "/")
        return self.path

    @property
    def parent(self):
        return File(os.path.dirname(self.path))

    def delete(self):
        if self.exists:
            if self.isFile:
                os.remove(self.path)

            if self.isDirectory:
                shutil.rmtree(self.path)

    def append(self, relPath):
        if self.isFile:
            raise NotADirectoryError(f"'{self.path}' is not a Directory, can not get content in subfolder")

        return File(os.path.join(self.path, relPath))

    @property
    def sha1(self):
        if not self.exists:
            raise FileNotFoundError(f"'{self.path}' is not found")

        if self.isDirectory:
            raise IsADirectoryError(f"'{self.path}' is not a file")

        with open(self.path, 'rb') as f:
            sha1obj = hashlib.sha1()
            sha1obj.update(f.read())
            return sha1obj.hexdigest()

    @property
    def hash(self):
        return self.sha1

    @property
    def createdTime(self):
        return int(os.path.getctime(self.path))

    @property
    def modifiedTime(self):
        return int(os.path.getmtime(self.path))

    def getCreatedTimeByFormat(self, format="%Y-%m-%d %H:%M:%S"):
        return time.strftime(format, time.localtime(self.createdTime))

    def getModifiedTimeByFormat(self, format="%Y-%m-%d %H:%M:%S"):
        return time.strftime(format, time.localtime(self.modifiedTime))

    class Iter:
        def __init__(self, obj):
            self.files = obj.files
            self.index = 0
            self.end = len(self.files)

        def __next__(self):
            if self.index < self.end:
                ret = self.files[self.index]
                self.index += 1
                return ret
            else:
                raise StopIteration

    def __call__(self, relPath):
        if not isinstance(relPath, str):
            raise TypeError(f"The key must be a string, not '{relPath}' ({type(relPath)})")

        return self.append(relPath)

    def __getitem__(self, key):
        return self.__call__(key)

    def __add__(self, other):
        return self.__call__(other)

    def __contains__(self, item):
        return os.path.exists(self.append(item).path)

    def __len__(self):
        return len(self.files)

    def __iter__(self):
        return self.Iter(self)

    def __repr__(self):
        return str(__class__)+': '+self.name
