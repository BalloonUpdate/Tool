import re
import yaml
import os.path
from io import BytesIO
from typing import Optional, List
from qcloud_cos import CosS3Client, CosConfig, CosServiceError
from src.utilities.dir_hash import dir_hash
from src.utilities.file import File
from src.service_provider.ParallelUploadServiceProvider import ParallelUploadServiceProvider

# 修复 Python 3.10 的不兼容性
import sys

if sys.version_info >= (3, 10):
    import collections.abc, collections

    collections.Iterable = collections.abc.Iterable


class TencentCOS(ParallelUploadServiceProvider):
    def __init__(self, uploadTool, config):
        super(TencentCOS, self).__init__(uploadTool, config)
        self.cache = []  # 缓存的远程文件结构
        self.modified = False  # 是否有过上传行为
        self.rootDir: Optional[File] = None  # 本地根目录
        self.prefix = config.get('prefix', '')  # COS 目录前缀
        if self.prefix == '/':
            self.prefix = ''
        if self.prefix != '' and not self.prefix.endswith('/'):
            self.prefix = self.prefix + '/'

        secret_id = config['secret_id']
        secret_key = config['secret_key']
        region = config['region']
        accelerate = config.get('accelerate', False)  # 增加一个配置项：如果开启全球加速则使用全球加速接口上传，优化海外上传速度
        if accelerate:
            print("使用全球加速上传，请注意流量费用")

        self.bucket = config['bucket']
        self.client = CosS3Client(CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key))
        self.uploadClient = self.client if not accelerate else CosS3Client(
            CosConfig(Region='accelerate', SecretId=secret_id, SecretKey=secret_key))
        self.cacheFileName = config['cache_file']
        self.headerRules = config['header_rules'] if 'header_rules' in config else []

    def initialize(self, rootDir: File):
        self.rootDir = rootDir

    def fetchDirectory(self):
        entries: List[str] = []
        marker = ''

        while True:
            response = self.client.list_objects(Bucket=self.bucket, MaxKeys=1000, Prefix=self.prefix, Marker=marker)
            if 'Contents' in response:
                entries += [e["Key"] for e in response['Contents']]
            if response['IsTruncated'] == 'false':
                break
            marker = response['NextMarker']

        # 将路径计算过程移至本地，减少网络请求开销（尽管这个算法并不讨巧但是比网络请求快多了）
        structure = []
        for entry in entries:
            isdir = entry.endswith('/')
            path = entry[len(self.prefix):]  # 在路径计算前移除 prefix
            path = path.rstrip('/') if isdir else path
            basename = os.path.basename(path)
            dirname = os.path.dirname(path)
            cursor = structure
            if dirname is not '':
                for dirLevel in dirname.split('/'):
                    if len(list(filter(lambda x: x['name'] == dirLevel, cursor))) == 0:
                        cursor.append({'name': dirLevel, 'children': []})
                    cursor = next(filter(lambda x: x['name'] == dirLevel, cursor))['children']
            if isdir:
                cursor.append({'name': basename, 'children': []})
            else:
                cursor.append({'name': basename, 'length': 0, 'hash': ''})
        return structure

    def fetchAll(self):
        if self.exists(self.cacheFileName):
            self.cache = yaml.safe_load(self.downloadObject(self.cacheFileName).read())
            print('缓存已找到 ' + self.cacheFileName)
            return self.cache

        return self.fetchDirectory()

    def fetchFragments(self):
        result = []
        fragments = self.client.list_multipart_uploads(Bucket=self.bucket)
        if 'Upload' in fragments:
            for f in fragments['Upload']:
                result += [f['Key']]
        return result

    def deleteObjects(self, paths):
        for i in range(0, len(paths), 999):
            batch = paths[i:i + 999]
            batch_objs = [{'Key': self.prefix + f} for f in batch]
            self.client.delete_objects(Bucket=self.bucket, Delete={'Object': batch_objs})

        self.modified = True

    def deleteDirectories(self, paths):
        self.deleteObjects([path + '/' for path in paths])

    def uploadObject(self, path, localPath, baseDir, length, hash):
        file = File(localPath)
        # headers = {'x-oss-meta-hash': file.sha1, **self.getHeaders(file.relPath(baseDir))}
        headers = self.getHeaders(file.relPath(baseDir))

        if self.uploadTool.debugMode and len(headers) > 0:
            print(headers)

        # 仅仅将上传添加到队列，等到下一步（CleanUp）再使用多线程上传
        self.uploadInboundQueue.put({
            "key": self.prefix + path,
            "local": localPath,
            "headers": headers
        })
        self.modified = True

    def uploadWorker(self, task):
        result = self.uploadClient.upload_file(
            Bucket=self.bucket, Key=task["key"], LocalFilePath=task["local"],
            EnableMD5=True, Metadata=task["headers"])
        return result

    def downloadObject(self, path):
        buf = BytesIO()
        response = self.client.get_object(Bucket=self.bucket, Key=self.prefix + path)
        for chunk in response['Body'].get_raw_stream().stream(4 * 1024):
            buf.write(chunk)
        buf.seek(0)
        return buf

    def makeDirectory(self, path):
        # COS 无需手动创建目录，上传子文件时会自动创建目录
        # if not self.exists(path):
        #     self.client.put_object(Bucket=self.bucket, Key=path+'/', Body='')
        self.modified = True

    def exists(self, path):
        try:
            self.client.head_object(Bucket=self.bucket, Key=self.prefix + path)
            return True
        except CosServiceError as e:
            if e.get_error_code() == 'NoSuchResource':
                return False
            raise e

    def cleanup(self):
        # 实际上传文件之后，需要更新缓存文件
        if self.modified:
            print('正在更新缓存...')
            cache = dir_hash(self.rootDir)

            if self.exists(self.cacheFileName):
                self.deleteObjects([self.cacheFileName])

            cacheContent = yaml.safe_dump(cache, sort_keys=False, canonical=True).encode('utf-8')
            self.client.put_object(Bucket=self.bucket, Key=self.prefix + self.cacheFileName, Body=cacheContent)

            print('缓存已更新 ' + self.cacheFileName)

    def getName(self):
        return '腾讯云对象存储(COS)'

    def getHeaders(self, path):
        headers = {}

        if isinstance(self.headerRules, list):
            for rule in self.headerRules:
                pattern = rule['pattern']
                hds = rule['headers']
                if re.search(pattern, path) is not None:
                    headers.update(hds)

        return headers
