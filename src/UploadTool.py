import sys
import traceback

import oss2
import qcloud_cos
import yaml

from src.constant import inDevelopment, version
from src.exception.ConfigObjectNotFound import ConfigObjectNotFound
from src.service_provider.AliyunOSS import AliyunOSS
from src.service_provider.Ftp import Ftp
from src.service_provider.SFTP import SFTP
from src.service_provider.TencentCOS import TencentCOS
from src.utilities.dir_hash import dir_hash
from src.exception.NoServiceProviderFoundError import NoServiceProviderFoundError
from src.exception.ParameterError import ParameterError
from src.utilities.file import File
from src.utilities.file_comparer import FileComparer2
from src.service_provider.AbstractServiceProvider import AbstractServiceProvider


def printObj(obj):
    print(yaml.dump(obj))


class UploadTool:
    serviceProviders = {
        'tencent': TencentCOS,
        'aliyun': AliyunOSS,
        'ftp': Ftp,
        'sftp': SFTP
    }

    def __init__(self):
        filename = 'config.yml'
        self.configFile = File(sys.executable).parent(filename) if not inDevelopment else File(filename)
        self.config = None
        self.source = None
        self.debugMode = False

    def checkParam(self):
        if len(sys.argv) < 2 and not inDevelopment:
            raise ParameterError(f'需要输入一个路径')

        self.source = File(sys.argv[1]) if not inDevelopment else File('fileToUpload')

        if not self.source.exists:
            raise ParameterError(f'目录 {self.source.path} 找不到')

        if self.source.isFile:
            raise ParameterError(f'需要输入一个"目录"的路径，{self.source.path} 却是一个文件!')

    def hashingMode(self):
        for d in self.source:
            if d.isDirectory:
                print(f'正在生成 {d.name}.yml')

                content = yaml.dump(dir_hash(d))
                d.parent(d.name + '.yml').content = content

    def uploadingMode(self, providerName):
        if providerName in self.serviceProviders:
            provider = self.serviceProviders[providerName]

            if providerName not in self.config:
                raise ConfigObjectNotFound('config.yml中找不到'+providerName+'的对应配置信息')

            correspondingConfig = self.config[providerName]

            client: AbstractServiceProvider = provider(self, correspondingConfig)

            print('上传到' + client.getName())
            client.initialize(self.source)

            # 生成本地目录校验文件
            if 'upload_only' not in self.config or not self.config['upload_only']:
                for f in [file for file in self.source if file.isDirectory]:
                    print(f'正在生成 {f.name}.yml')

                    content = yaml.dump(dir_hash(f))
                    f.parent(f.name + '.yml').content = content

            # 获取远程文件目录
            print('正在获取远程文件目录..')
            remote = client.fetchAll()

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

            # 创建新目录
            if len(cp.newFolders) > 0:
                print('')
                count = 0
                for path in cp.newFolders:
                    count += 1
                    print(f'创建目录({count}/{len(cp.newFolders)}): {path}')
                    client.makeDirectory(path)

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
                    client.uploadObject(path, localFile.path, self.source.path, length, hash)

            # 清理退出
            client.cleanup()
        else:
            raise NoServiceProviderFoundError(f'未知的服务提供商: <{providerName}>, 可用值: '+str([k for k in self.serviceProviders.keys()]))

    def main(self):
        isHashMode = False

        print('UploadTool v'+version)

        try:
            self.checkParam()

            if self.configFile.exists:
                self.config = yaml.safe_load(self.configFile.content)

                self.debugMode = self.config['debug'] if 'debug' in self.config else False

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
            if e._message == 'check_hostname requires server_hostname':
                print('可能的解决方法：请检查电脑是否开启了代理上网')
                print('如果开启，请将<bucket-name>.cos.<region>.myqcloud.com添加到PAC白名单或者暂时关闭代理')
                print('<bucket-name>为桶名，<region>为地域，示例：test-123456.cos.ap-chengdu.myqcloud.com')
        except SystemExit:
            pass
        except BaseException as e:
            print(e)
            print(traceback.format_exc())

        # if not inDevelopment and not isHashMode and self.config is not None:
        #     if 'show_any_key_to_exit' in self.config and self.config['show_any_key_to_exit']:
        if not inDevelopment and not isHashMode and self.config is not None:
            if 'show_any_key_to_exit' in self.config:
                if self.config['show_any_key_to_exit']:
                    input(f'任意键退出..')


