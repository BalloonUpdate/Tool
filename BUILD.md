# 构建与开发

要构建此程序，需要安装 Python 3 和 Git。

运行此命令克隆仓库：

```shell
git clone https://github.com/updater-for-minecraft/Tool.git
cd Tool
```

推荐您使用虚拟环境开发。Python 提供了两种虚拟环境，`virtualenv` 和 `venv` 。

使用 `virtualenv` 创建虚拟环境，需要执行以下命令：

```shell
pip3 install virtualenv
python3 -m virtualenv venv
```

如果使用 `venv`，则可以使用以下命令：

```shell
python3 -m venv venv
```

然后，激活 `virtualenv` 或 `venv` 虚拟环境：

```shell
venv\Scripts\activate
```

在虚拟环境下安装依赖：

```shell
pip3 install -r requirements
```

在开发时，程序总是将 `fileToUpload` 作为待上传的目录。我们需要手动创建这个目录：

```shell
mkdir fileToUpload
```

然后运行程序进行测试：

```shell
UploadToolMain.py
```

修改完代码后，建议构建为可执行文件进行测试，以确保用户使用的体验与开发时一致：

```shell
pyinstaller build.spec
```

构建完成后，生成的 exe 文件在 `dist` 目录下。首次构建后，可以使用下面的命令复制示例的配置文件：

```shell
copy config.exam.yml dist\config.yml
```

