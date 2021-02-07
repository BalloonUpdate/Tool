from qcloud_cos import CosS3Client, CosConfig

from src.utilities.file import File
from src.object_storage_service.abstract_oss_client import AbstractOssClient


class TencentCOS(AbstractOssClient):
    def __init__(self, **configs):
        super(TencentCOS, self).__init__(**configs)

        secret_id = configs['secret_id']
        secret_key = configs['secret_key']
        region = configs['region']
        bukkit = configs['bukkit']

        self.client = CosS3Client(CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key))

    def fetchDirectory(self, path='', i=''):
        structure = []

        marker = ''
        while True:
            pureName2 = path[:path.rfind('/')]
            pureName2 = pureName2[pureName2.rfind('/') + 1:]
            print(i + pureName2)
            response = self.client.list_objects(Bucket=self.config['bukkit'], Delimiter='/', Prefix=path, Marker=marker)

            # 所有的文件
            if 'Contents' in response:
                for file in response['Contents']:
                    temp = file['Key']
                    name = temp[temp.rfind('/') + 1:]
                    headers = self.client.head_object(Bucket=self.config['bukkit'], Key=file['Key'])
                    hash = headers['x-cos-meta-updater-sha1'] if 'x-cos-meta-updater-sha1' in headers else ''
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
                        'tree': self.fetchDirectory(folder['Prefix'], i + '    ')
                    })

            if response['IsTruncated'] == 'false':
                break

            marker = response['NextMarker']
        return structure

    def fetchBukkit(self):
        return self.fetchDirectory()

    def fetchFragments(self):
        result = []
        fragments = self.client.list_multipart_uploads(Bucket=self.config['bukkit'])
        if 'Upload' in fragments:
            for f in fragments['Upload']:
                result += [f['Key']]
        return result

    def deleteObjects(self, paths):
        objs = [{'Key': f} for f in paths]
        self.client.delete_objects(Bucket=self.config['bukkit'], Delete={'Object': objs})

    def deleteDirectories(self, paths):
        objs = [{'Key': f + '/'} for f in paths]
        self.client.delete_objects(Bucket=self.config['bukkit'], Delete={'Object': objs})

    def uploadObject(self, path, localPath):
        file = File(localPath)
        metadata = {
            'x-cos-meta-updater-sha1': file.sha1,
            'x-cos-meta-updater-length': str(file.length)
        }
        self.client.upload_file(Bucket=self.config['bukkit'], Key=path, LocalFilePath=localPath, MAXThread=4, Metadata=metadata)

    def getProviderName(self):
        return '腾讯云对象存储(COS)'
