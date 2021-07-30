from src.utilities.file import File


class SimpleFileObject:
    def __init__(self, name: str, length: int = None, hash: str = None, children: list = None):
        self.name = name
        self.length = length
        self.hash = hash
        self.children = children

        isFile = self.isFile
        isDir = self.isDirectory
        isValidFile = length is not None and hash is not None

        if not isFile and not isDir:
            assert False, f'unknown file type: the file type must be explicated by parameters ({self.name})'

        if isFile and isDir:
            assert False, f'inexplicit file/dir type: the file type must be either File or Directory ({self.name})'

        if isFile and not isValidFile:
            missingParameter = 'length' if length is None else 'hash'
            assert False, f'missing necessary parameter: {missingParameter} ({self.name})'

    @staticmethod
    def FromDict(obj: dict):
        if 'children' in obj:
            children = [SimpleFileObject.FromDict(f) for f in obj['children']]
            return SimpleFileObject(obj['name'], children=children)
        else:
            return SimpleFileObject(obj['name'], length=obj['length'], hash=obj['hash'])

    @staticmethod
    def FromFile(file: File):
        if file.isDirectory:
            children = [SimpleFileObject.FromFile(f) for f in file]
            return SimpleFileObject(file.name, children=children)
        else:
            return SimpleFileObject(file.name, length=file.length, hash=file.sha1)

    @property
    def isDirectory(self):
        return self.children is not None

    @property
    def isFile(self):
        return self.length is not None or self.hash is not None

    @property
    def files(self):
        if not self.isDirectory:
            raise NotADirectoryError(f"'{self.name}' is not a Directory")
        return self.children

    @property
    def sha1(self):
        return self.hash

    def getByName(self, name):
        for child in self.children:
            if child.name == name:
                return child
        return None

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

    def __getitem__(self, name: str):
        if not isinstance(name, str):
            raise TypeError(f"The file must be a string, not '{name}' ({type(name)})")

        if not self.__contains__(name):
            raise FileNotFoundError(f"'{name}' is not found")

        return self.getByName(name)

    def __call__(self, relPath):
        return self.__getitem__(relPath)

    def __contains__(self, file: str):
        if not isinstance(file, str):
            raise TypeError(f"The key must be a string, not '{file}' ({type(file)})")

        for subFile in self.children:
            if subFile.name == file:
                return True

        return False

    def __len__(self):
        return len(self.children)

    def __iter__(self):
        return self.Iter(self)


class FileComparer2:
    def __init__(self, basePath: File, compareFunc=None):
        super().__init__()
        self.basePath = basePath

        def defaultCompareFunc(remoteFile: SimpleFileObject, localRelPath: str, localAbsPath: str):
            return remoteFile.sha1 == File(localAbsPath).sha1

        self.compareFunc = compareFunc if compareFunc is not None else defaultCompareFunc

        self.oldFiles = []
        self.oldFolders = []
        self.newFiles = {}
        self.newFolders = []

    def findNewFiles(self, current: SimpleFileObject, template: File):
        """只扫描新增的文件(不包括被删除的)
        :param current: 远程文件结构(目录)
        :param template: 本地文件结构(目录)
        """

        for t in template:
            if t.name not in current:  # 文件不存在
                self.addNewFile(SimpleFileObject.FromFile(t), t)
            else:  # 文件存在的话要进行进一步判断
                corresponding = current(t.name)

                if t.isDirectory:
                    if corresponding.isFile:
                        # 先删除旧的再获取新的
                        self.addOldFile(corresponding, template.relPath(self.basePath))
                        self.addNewFile(corresponding, t)
                    else:
                        self.findNewFiles(corresponding, t)
                else:
                    if corresponding.isFile:
                        # if corresponding.sha1 != t.sha1:  # 校验hash
                        if not self.compareFunc(corresponding, t.path, t.relPath(self.basePath)):
                            # 先删除旧的再获取新的
                            self.addOldFile(corresponding, template.relPath(self.basePath))
                            self.addNewFile(corresponding, t)
                    else:
                        # 先删除旧的再获取新的
                        self.addOldFile(corresponding, template.relPath(self.basePath))
                        self.addNewFile(corresponding, t)

    def findOldFiles(self, current: SimpleFileObject, template: File):
        """只扫描需要删除的文件
        :param current: 远程文件结构(目录)
        :param template: 本地文件结构(目录)
        """

        for c in current:
            if c.name in template:
                corresponding = template(c.name)
                # 如果两边都是目录，递归并进一步判断
                if c.isDirectory and corresponding.isDirectory:
                    self.findOldFiles(c, corresponding)
                # 其它情况均由findMissingFiles进行处理了，这里不需要重复计算
            else:  # 如果远程端没有有这个文件，就直接删掉好了
                self.addOldFile(c, template.relPath(self.basePath))

    def addOldFile(self, file: SimpleFileObject, dir: str):
        """添加需要删除的文件/目录
        :param file: 删除的文件(文件/目录)
        :param dir: file所在的目录(文件/目录)
        """
        path = dir + '/' + file.name
        pathWithoutDotSlash = path[2:] if path.startswith('./') else path

        if file.isDirectory:
            for u in file:
                if u.isDirectory:
                    self.addOldFile(u, path)
                else:
                    newPath = path + '/' + u.name
                    self.oldFiles += [newPath[2:] if newPath.startswith('./') else newPath]

            self.oldFolders += [pathWithoutDotSlash]
        else:
            self.oldFiles += [pathWithoutDotSlash]

    def addNewFile(self, missing: SimpleFileObject, template: File):
        """添加需要传输的文件
        :param missing: 缺失的文件对象(文件/目录)
        :param template: 对照模板(文件/目录)
        :return:
        """

        if missing.isDirectory != template.isDirectory:
            assert False, 'the types did not equals'

        if missing.isDirectory:
            folder = template.parent.relPath(self.basePath)
            if folder not in self.newFolders and folder != '.':
                self.newFolders += [folder]
            for m in missing:
                mCorresponding = template(m.name)
                if m.isDirectory:
                    self.addNewFile(m, mCorresponding)
                else:
                    self.newFiles[mCorresponding.relPath(self.basePath)] = [m.length, m.hash]
        else:
            self.newFiles[template.relPath(self.basePath)] = [template.length, template.sha1]

    def compareWithSimpleFileObject(self, current: File, template: SimpleFileObject):
        self.findNewFiles(template, current)
        self.findOldFiles(template, current)

    def compareWithList(self, current: File, template: list):
        template2 = {'name': '', 'children': template}
        self.findNewFiles(SimpleFileObject.FromDict(template2), current)
        self.findOldFiles(SimpleFileObject.FromDict(template2), current)
