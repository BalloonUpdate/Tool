import re

from qcloud_cos import CosS3Client, CosConfig

from src.utilities.file import File
from src.service_provider.AbstractServiceProvider import AbstractServiceProvider


class TencentCOS(AbstractServiceProvider):
    def __init__(self, uploadTool, config):
        super(TencentCOS, self).__init__(uploadTool, config)

        secret_id = config['secret_id']
        secret_key = config['secret_key']
        region = config['region']
        self.bucket = config['bucket']
        self.client = CosS3Client(CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key))

        self.headerRules = config['header_rules'] if 'header_rules' in config else []

    def fetchDirectory(self, path='', i=''):
        structure = []

        marker = ''
        while True:
            pureName2 = path[:path.rfind('/')]
            pureName2 = pureName2[pureName2.rfind('/') + 1:]
            print(i + pureName2)
            response = self.client.list_objects(Bucket=self.bucket, Delimiter='/', Prefix=path, Marker=marker)

            # 所有的文件
            if 'Contents' in response:
                for file in response['Contents']:
                    temp = file['Key']
                    name = temp[temp.rfind('/') + 1:]
                    headers = self.client.head_object(Bucket=self.bucket, Key=file['Key'])
                    hash = headers['x-oss-meta-hash'] if 'x-oss-meta-hash' in headers else ''
                    if len(name) == 0:
                        continue
                    structure.append({
                        'name': name,
                        'length': file['Size'],
                        'hash': hash
                    })

            # 所有的目录
            if 'CommonPrefixes' in response:
                for folder in response['CommonPrefixes']:
                    temp = folder['Prefix'][:-1]
                    pureName = temp[temp.rfind('/') + 1:]
                    structure.append({
                        'name': pureName,
                        'children': self.fetchDirectory(folder['Prefix'], i + '    ')
                    })

            if response['IsTruncated'] == 'false':
                break

            marker = response['NextMarker']
        return structure

    def fetchBukkit(self):
        return self.fetchDirectory()

    def fetchFragments(self):
        result = []
        fragments = self.client.list_multipart_uploads(Bucket=self.bucket)
        if 'Upload' in fragments:
            for f in fragments['Upload']:
                result += [f['Key']]
        return result

    def deleteObjects(self, paths):
        def del_(paths_):
            objs = [{'Key': f} for f in paths_]
            self.client.delete_objects(Bucket=self.bucket, Delete={'Object': objs})

        paths_ = paths[:]
        while len(paths_) > 999:
            del_(paths_[:999])
            paths_ = paths_[999:]
        if len(paths_) > 0:
            del_(paths_)

    def deleteDirectories(self, paths):
        objs = [{'Key': f + '/'} for f in paths]
        self.client.delete_objects(Bucket=self.bucket, Delete={'Object': objs})

    def uploadObject(self, path, localPath, baseDir, length, hash):
        file = File(localPath)
        headers = {'x-oss-meta-hash': file.sha1, **self.getHeaders(file.relPath(baseDir))}

        if self.uploadTool.debugMode:
            print(headers)

        self.client.upload_file(Bucket=self.bucket, Key=path, LocalFilePath=localPath, MAXThread=4, Metadata=headers)

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
