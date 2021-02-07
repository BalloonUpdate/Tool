import json
import sys
import traceback

import oss2
from qcloud_cos import CosServiceError

from src.constant import inDevelopment, serviceProviders
from src.utilities.dir_hash import dir_hash
from src.exception.no_service_provider_found import NoServiceProviderFoundError
from src.exception.parameter_error import ParameterError
from src.utilities.file import File
from src.utilities.file_comparer import FileComparer2
from src.object_storage_service.abstract_oss_client import AbstractOssClient


def printObj(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=4))


class Entry:
    def __init__(self):
        self.config = None
        self.source = None

    def loadConfig(self, file='config.json'):
        f = File(sys.executable).parent(file) if not inDevelopment else File(file)
        self.config = json.loads(f.content)

    def checkParam(self):
        if len(sys.argv) < 2 and not inDevelopment:
            raise ParameterError(f'需要输入一个路径')

        self.source = File(sys.argv[1]) if not inDevelopment else File(r'D:\hyperink\Desktop\root')

        if not self.source.exists:
            raise ParameterError(f'目录 {self.source.path} 找不到')

        if self.source.isFile:
            raise ParameterError(f'需要输入一个"目录"的路径，{self.source.path} 却是一个文件!')

    def hashingMode(self):
        print(f'正在生成 {self.source.name}.json')

        content = json.dumps(dir_hash(self.source), ensure_ascii=False, indent=4)
        self.source.parent(self.source.name + '.json').content = content

    def uploadingMode(self, providerName):
        if providerName in serviceProviders:
            provider = serviceProviders[providerName]

            params = {
                'bukkit': self.config['bukkit'],
                'secret_id': self.config['secret_id'],
                'secret_key': self.config['secret_key'],
                'region': self.config['region'],
            }

            client: AbstractOssClient = provider(**params)

            print('上传到' + client.getProviderName())

            # 生成本地目录校验文件
            if not self.config['skip_hashing_before_uploading']:
                for f in [file for file in self.source if file.isDirectory]:
                    print(f'正在生成 {f.name}.json')

                    content = json.dumps(dir_hash(f), ensure_ascii=False, indent=4)
                    f.parent(f.name + '.json').content = content

            # 获取远程文件目录
            print('正在获取远程文件目录..')
            remote = client.fetchBukkit()

            # 计算文件差异
            print('正在计算文件差异..')
            cp = FileComparer2(self.source)
            cp.compareWithList(self.source, remote)

            # 输出差异结果
            if len(cp.oldFolders) == 0 and len(cp.oldFiles) == 0 and \
                    len(cp.newFolders) == 0 and len(cp.newFiles) == 0:
                print('无差异')
            else:
                print(f'旧文件: {len(cp.oldFiles)}')
                print(f'旧目录: {len(cp.oldFolders)}')
                print(f'新文件: {len(cp.newFiles)}')
                print(f'新目录: {len(cp.newFolders)}')

            # 输出文件碎片
            fragments = client.fetchFragments()
            if len(fragments) > 0:
                for f in fragments:
                    print('文件碎片: ' + f)

            # 删除旧文件
            if len(cp.oldFiles) > 0 or len(cp.oldFolders) > 0:
                print('')
                for f in cp.oldFiles:
                    print('删除远程文件: ' + f)
                for f in cp.oldFolders:
                    print('删除远程目录: ' + f + '/')
                if len(cp.oldFiles) > 0:
                    client.deleteObjects(cp.oldFiles)
                if len(cp.oldFolders) > 0:
                    client.deleteDirectories(cp.oldFolders)

            # 上传新文件
            if len(cp.newFiles) > 0:
                print('')
                count = 0
                for path, v in cp.newFiles.items():
                    length = v[0]
                    hash = v[1]
                    localFile = self.source(path)

                    count += 1
                    print(f'上传本地文件({count}/{len(cp.newFiles)}): {path}')
                    client.uploadObject(path, localFile.path)
        else:
            raise NoServiceProviderFoundError('未知的服务提供商: '+providerName)

    def main(self):
        try:
            self.checkParam()
            self.loadConfig()
        except BaseException as e:
            print(e)
            print(traceback.format_exc())

            if not inDevelopment:
                input(f'任意键退出..')
            else:
                raise e

        serviceProvider = self.config['service_provider']

        if serviceProvider == '':
            self.hashingMode()
        else:
            try:
                self.uploadingMode(serviceProvider)
            except oss2.exceptions.ServerError as e:
                print(traceback.format_exc())
                print('OSS异常(可能是配置信息不正确): ')
                print(e.code)
                print(e.message)
            except CosServiceError as e:
                print(traceback.format_exc())
                print('COS异常(可能是配置信息不正确): ')
                print(e.get_error_code())
                print(e.get_error_msg())
            except SystemExit:
                pass
            except BaseException as e:
                print(e)
                print(traceback.format_exc())

            if not inDevelopment:
                input(f'任意键退出..')
