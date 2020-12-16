@echo off
pyinstaller --noconfirm --version-file version-file.txt -i icon.ico -F -n Deployer main.py
echo Build finished!