import json
import sys
import traceback

import oss2
import qcloud_cos

from src.constant import inDevelopment, serviceProviders
from src.exception.config_object_not_found import ConfigObjectNotFound
from src.utilities.dir_hash import dir_hash
from src.exception.no_service_provider_found import NoServiceProviderFoundError
from src.exception.parameter_error import ParameterError
from src.utilities.file import File
from src.utilities.file_comparer import FileComparer2
from src.service_provider.abstract_service_provider import AbstractServiceProvider


def printObj(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=4))


class Entry:
    def __init__(self):
        filename = 'config.json'
        self.configFile = File(sys.executable).parent(filename) if not inDevelopment else File(filename)
        self.config = None
        self.source = None

    def checkParam(self):
        if len(sys.argv) < 2 and not inDevelopment:
            raise ParameterError(f'需要输入一个路径')

        self.source = File(sys.argv[1]) if not inDevelopment else File(r'D:\aprilforest\Desktop\assets')

        if not self.source.exists:
            raise ParameterError(f'目录 {self.source.path} 找不到')

        if self.source.isFile:
            raise ParameterError(f'需要输入一个"目录"的路径，{self.source.path} 却是一个文件!')

    def hashingMode(self):
        for d in self.source:
            if d.isDirectory:
                print(f'正在生成 {d.name}.json')

                content = json.dumps(dir_hash(d), ensure_ascii=False, indent=4)
                d.parent(d.name + '.json').content = content

    def uploadingMode(self, providerName):
        if providerName in serviceProviders:
            provider = serviceProviders[providerName]

            if providerName not in self.config:
                raise ConfigObjectNotFound('config.json中找不到'+providerName+'对应的配置信息')

            correspondingConfig = self.config[providerName]

            client: AbstractServiceProvider = provider(correspondingConfig)

            print('上传到' + client.getProviderName())
            client.initialize()

            # 生成本地目录校验文件
            if not self.config['upload_without_hashing']:
                for f in [file for file in self.source if file.isDirectory]:
                    print(f'正在生成 {f.name}.json')

                    content = json.dumps(dir_hash(f), ensure_ascii=False, indent=4)
                    f.parent(f.name + '.json').content = content

            # 获取远程文件目录
            print('正在获取远程文件目录..')
            remote = client.fetchBukkit()

            # 计算文件差异
            print('正在计算文件差异..')
            cp = FileComparer2(self.source, client.compareFile)
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
                    client.uploadObject(path, localFile.path, length, hash)

            # 清理退出
            client.cleanup()
        else:
            raise NoServiceProviderFoundError(f'未知的服务提供商: <{providerName}>')

    def main(self):
        isHashMode = False

        try:
            self.checkParam()

            if self.configFile.exists:
                self.config = json.loads(self.configFile.content)
                self.uploadingMode(self.config['service_provider'])
                isHashMode = False
            else:
                self.hashingMode()
                isHashMode = True
        except oss2.exceptions.OssError as e:
            print(traceback.format_exc())
            print('OSS异常(可能是配置信息不正确)')
        except qcloud_cos.cos_exception.CosException as e:
            print(traceback.format_exc())
            print('COS异常(可能是配置信息不正确)')
        except SystemExit:
            pass
        except BaseException as e:
            print(e)
            print(traceback.format_exc())

        if not inDevelopment and not isHashMode:
            input(f'任意键退出..')
