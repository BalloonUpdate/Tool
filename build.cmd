@echo off
pyinstaller --noconfirm --version-file version-file.txt -F -n autodeployer main.py
echo Build finished!