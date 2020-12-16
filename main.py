import json
import sys

from qcloud_cos import CosConfig, CosS3Client, CosServiceError

from file import File
from file_comparer import FileComparer2
from structure_generator import generateStructure

inDevelopment = not getattr(sys, 'frozen', False)


def printObj(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=4))


def main():
    def generateRemoteTree(path=''):
        structure = []

        marker = ''
        while True:
            print('扫描目录: '+path[:-1])
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
                        'tree': generateRemoteTree(folder['Prefix'])
                    })

            if response['IsTruncated'] == 'false':
                break

            marker = response['NextMarker']
        return structure

    if len(sys.argv) < 2 and not inDevelopment:
        print('需要输入一个路径')
        sys.exit()

    settings = File(sys.executable).parent('cos.json') if not inDevelopment else File('cos.json')
    source = File(sys.argv[1]) if not inDevelopment else File(r'D:\nginx-1.19.1\updatertest')

    if not source.exists:
        print(f'目录 {source.path} 找不到')
        sys.exit()

    if source.isFile:
        print(f'需要输入一个"目录"的路径，{source.path}是一个文件!')
        sys.exit()

    if not settings.exists:
        print(f'文件 {settings.path} 找不到')
        sys.exit()

    # debugCos = File('cos.json')

    config = json.loads(settings.content)

    bukkit = config['bukkit']
    secret_id = config['secret_id']
    secret_key = config['secret_key']
    region = config['region']
    client = CosS3Client(CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key))

    ##

    # 为重新生成结构文件
    for dirInSource in source:
        # 跳过所有文件
        if dirInSource.isFile:
            continue

        print(f'正在生成 {dirInSource.name}.json')

        content = json.dumps(generateStructure(dirInSource), ensure_ascii=False, indent=4)
        dirInSource.parent(dirInSource.name + '.json').content = content

    print('正在扫描远程目录..  (可能需要点时间,具体速度由文件数量决定)')
    # tree = json.loads(debugCos.content)
    tree = generateRemoteTree()
    # debugCos.content = json.dumps(tree, ensure_ascii=False, indent=4)

    print('正在计算差异.. (可能需要亿点时间)')
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

    fragments = client.list_multipart_uploads(Bucket=bukkit)
    if 'Upload' in fragments:
        print('')
        for f in fragments['Upload']:
            print('文件碎片: ' + f['Key'])

    # 删除文件
    if len(comparer.uselessFiles) > 0:
        print('')
    for f in comparer.uselessFiles:
        print('删除远程文件: ' + f)

    if len(comparer.uselessFiles) > 0:
        listToDelete = [{'Key': f} for f in comparer.uselessFiles]
        client.delete_objects(Bucket=bukkit, Delete={'Object': listToDelete})

    # 删除目录
    if len(comparer.uselessFolders) > 0:
        print('')
    for f in comparer.uselessFolders:
        print('删除远程目录: ' + f)

    if len(comparer.uselessFolders) > 0:
        listToDelete = [{'Key': f + '/'} for f in comparer.uselessFolders]
        client.delete_objects(Bucket=bukkit, Delete={'Object': listToDelete})

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

        metadata = {'x-cos-meta-updater-sha1': hash, 'x-cos-meta-updater-length': str(length)}
        client.upload_file(Bucket=bukkit, Key=k, LocalFilePath=file.path, MAXThread=4, Metadata=metadata)

    print('\nDone')


if __name__ == "__main__":
    count = 1

    while True:
        try:
            main()

            input(f'任意键重新上传,如果不需要重新上传请退出本程序')
            print(f'\n\n\n------------------第{count}次重新上传------------------')
            count += 1
        except CosServiceError as e:
            print('COS异常(可能是配置信息不正确): ')
            print(e.get_error_code())
            print(e.get_error_msg())
            break
        except SystemExit:
            break
        except BaseException as e:
            print(e)
            break
    if not inDevelopment:
        input(f'任意键退出..')
