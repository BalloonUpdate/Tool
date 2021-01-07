import json
import sys
import traceback

from qcloud_cos import CosConfig, CosS3Client, CosServiceError
import oss2

from file import File
from file_comparer import FileComparer2
from structure_generator import generateStructure

inDevelopment = not getattr(sys, 'frozen', False)


def printObj(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=4))


def main():
    def generateRemoteTreeByCos(path='', i=''):
        structure = []

        marker = ''
        while True:
            pureName2 = path[:path.rfind('/')]
            pureName2 = pureName2[pureName2.rfind('/') + 1:]
            print(i + pureName2)
            response = client.list_objects(Bucket=bukkit, Delimiter='/', Prefix=path, Marker=marker)

            # 所有的文件
            if 'Contents' in response:
                for file in response['Contents']:
                    temp = file['Key']
                    name = temp[temp.rfind('/') + 1:]
                    headers = client.head_object(Bucket=bukkit, Key=file['Key'])
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
                        'tree': generateRemoteTreeByCos(folder['Prefix'], i + '    ')
                    })

            if response['IsTruncated'] == 'false':
                break

            marker = response['NextMarker']
        return structure

    def generateRemoteTreeByOss(path='', i=''):
        structure = []

        pureName2 = path[:path.rfind('/')]
        pureName2 = pureName2[pureName2.rfind('/')+1:]
        print(i + pureName2)

        d = []

        for obj in oss2.ObjectIteratorV2(bucket, prefix=path, delimiter='/', fetch_owner=True):
            if obj.is_prefix():  # 判断obj为文件夹。
                pureName = obj.key[:obj.key.rfind('/')].replace(path, '')
                d += [[pureName, obj.key]]
                # print(i + 'd: ' + pureName)

            else:  # 判断obj为文件。
                if obj.key == path:
                    continue
                pureName = obj.key[obj.key.rfind('/')+1:]
                # print(i + 'f: ' + pureName)
                headers = bucket.head_object(obj.key).headers
                hash = headers['x-oss-meta-updater-sha1'] if 'x-oss-meta-updater-sha1' in headers else ''
                structure.append({
                    'name': pureName,
                    'length': headers['Content-Length'],
                    'hash': hash
                })

        for D in d:
            # print(i+'D: '+D[0])
            structure.append({
                'name': D[0],
                'tree': generateRemoteTreeByOss(D[1], i + '    ')
            })

        return structure

    if len(sys.argv) < 2 and not inDevelopment:
        print('需要输入一个路径')
        sys.exit()

    cosSettings = File(sys.executable).parent('cos.json') if not inDevelopment else File('cos.json')
    ossSettings = File(sys.executable).parent('oss.json') if not inDevelopment else File('oss.json')
    source = File(sys.argv[1]) if not inDevelopment else File(r'D:\nginx-1.19.1\updatertest')

    if not source.exists:
        print(f'目录 {source.path} 找不到')
        sys.exit()

    if source.isFile:
        print(f'需要输入一个"目录"的路径，{source.path}是一个文件!')
        sys.exit()

    if cosSettings.exists and ossSettings.exists:
        print(f'Oss配置文件和Cos配置文件只能二选一')
        sys.exit()

    if not cosSettings.exists and not ossSettings.exists:
        print(f'找不到配置文件文件: {ossSettings.path} 或者 {cosSettings.path}')
        sys.exit()

    isCos = cosSettings.exists
    config = json.loads(cosSettings.content if isCos else ossSettings.content)

    bukkit = config['bukkit']
    secret_id = config['secret_id']
    secret_key = config['secret_key']
    region = config['region']
    client = CosS3Client(CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key))
    bucket = oss2.Bucket(oss2.Auth(secret_id, secret_key), region, bukkit)
    oss2.defaults.connection_pool_size = 4  # 设置最大并发数限制

    print('上传到阿里云对象存储(OSS)..' if not isCos else '上传到腾讯云对象存储(COS)..')
    print('')

    # 为重新生成结构文件
    for dirInSource in source:
        # 跳过所有文件
        if dirInSource.isFile:
            continue

        print(f'正在生成 {dirInSource.name}.json')

        content = json.dumps(generateStructure(dirInSource), ensure_ascii=False, indent=4)
        dirInSource.parent(dirInSource.name + '.json').content = content

    print('正在扫描远程目录..')
    tree = generateRemoteTreeByCos() if isCos else generateRemoteTreeByOss()

    print('正在计算差异..')
    comparer = FileComparer2(source)
    comparer.compareWith(tree, source)

    if len(comparer.uselessFolders) == 0 and len(comparer.uselessFiles) == 0 and \
            len(comparer.missingFolders) == 0 and len(comparer.missingFiles) == 0:
        print('无差异')
    else:
        print(f'旧文件: {len(comparer.uselessFiles)}')
        print(f'旧目录: {len(comparer.uselessFolders)}')
        print(f'新文件: {len(comparer.missingFiles)}')
        print(f'新目录: {len(comparer.missingFolders)}')

    # 文件碎片
    if isCos:
        fragments = client.list_multipart_uploads(Bucket=bukkit)
        if 'Upload' in fragments:
            print('')
            for f in fragments['Upload']:
                print('文件碎片: ' + f['Key'])
    else:
        showed = False
        for upload_info in oss2.MultipartUploadIterator(bucket):
            if not showed:
                showed = True
                print('文件碎片: ')
            print('key:', upload_info.key)
            print('upload_id:', upload_info.upload_id)

    # 删除文件
    if len(comparer.uselessFiles) > 0:
        print('')
    for f in comparer.uselessFiles:
        print('删除远程文件: ' + f)

    if len(comparer.uselessFiles) > 0:
        if isCos:
            temp = [{'Key': f} for f in comparer.uselessFiles]
            client.delete_objects(Bucket=bukkit, Delete={'Object': temp})
        else:
            if len(comparer.uselessFiles) > 0:
                bucket.batch_delete_objects(comparer.uselessFiles)

    # 删除目录
    if len(comparer.uselessFolders) > 0:
        print('')
    for f in comparer.uselessFolders:
        print('删除远程目录: ' + f)

    if len(comparer.uselessFolders) > 0:
        if isCos:
            temp = [{'Key': f + '/'} for f in comparer.uselessFolders]
            client.delete_objects(Bucket=bukkit, Delete={'Object': temp})
        else:
            for uf in comparer.uselessFolders:
                bucket.delete_object(uf + '/')

    # 上传文件
    if len(comparer.missingFiles) > 0:
        print('')
    count = 0
    for k, v in comparer.missingFiles.items():
        length = v[0]
        hash = v[1]
        file = source(k)

        count += 1
        print(f'上传本地文件({count}/{len(comparer.missingFiles)}): {k}')

        if isCos:
            metadata = {'x-cos-meta-updater-sha1': hash, 'x-cos-meta-updater-length': str(length)}
            client.upload_file(Bucket=bukkit, Key=k, LocalFilePath=file.path, MAXThread=4, Metadata=metadata)
        else:
            metadata = {'x-oss-meta-updater-sha1': hash, 'x-oss-meta-updater-length': str(length)}
            oss2.resumable_upload(bucket, k, file.path, num_threads=4, headers=metadata)

    print('\nDone')


if __name__ == "__main__":
    count = 1

    while True:
        try:
            main()

            if inDevelopment:
                break

            input(f'任意键重新上传,如果不需要重新上传请退出本程序')
            print(f'\n\n\n------------------第{count}次重新上传------------------')
            count += 1
        except oss2.exceptions.ServerError as e:
            print('OSS异常(可能是配置信息不正确): ')
            print(e.code)
            print(e.message)
            break
        except CosServiceError as e:
            print('COS异常(可能是配置信息不正确): ')
            print(e.get_error_code())
            print(e.get_error_msg())
            break
        except SystemExit:
            break
        except BaseException as e:
            print(e)
            print(traceback.format_exc())
            break
    if not inDevelopment:
        input(f'任意键退出..')
