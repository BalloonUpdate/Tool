@echo off

python ci\generate_version_file.py
pyinstaller --noconfirm --version-file version-file.txt -i icon.ico -c -F -n Tool main.py