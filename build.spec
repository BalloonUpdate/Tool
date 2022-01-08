# -*- mode: python ; coding: utf-8 -*-

def get_git_tag(default):
    import os
    import re
    ref = os.getenv('GITHUB_REF', '')
    match = re.search(r'(?<=refs/tags/).*', ref)
    if match is not None:
        tag_name = match[0][1:] if match[0].startswith('v') else match[0]
    else:
        tag_name = default
    return tag_name

def get_git_sha():
    import os
    return os.getenv('GITHUB_SHA', '')

# 生成版本号文件
import json
import time

metadata_file = 'meta.json'
version_text = get_git_tag('0.0.0')
commit_sha = get_git_sha()
compile_time = time.strftime("%Y-%m-%d %H:%M-%S %z")

with open(metadata_file, "w+", encoding="utf-8") as f:
    f.write(json.dumps({
        "version": version_text,
        "commit": commit_sha,
        "compile_time": compile_time
    }, ensure_ascii=False, sort_keys=False))

block_cipher = None

a = Analysis(['UploadToolMain.py'],
             pathex=['.'],
             binaries=[],
             datas=[
                (metadata_file, '.')
             ],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          name='Tool-'+version_text,
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None , icon='icon.ico')

os.remove(metadata_file)