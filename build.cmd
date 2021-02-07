@echo off

python ci\generate_version_file.py

python ci\version.py both > temp.txt
set /p filename=< temp.txt

python ci\version.py version > temp.txt
set /p version_text=< temp.txt

del temp.txt

del /f /s /q dist\%filename%.exe

echo ----------------Build for %filename%----------------

pyinstaller --noconfirm --version-file version-file.txt -i icon.ico -c -F -n %filename% main.py

echo ----------------Clean up----------------

del /f /s /q version-file.txt
del /f /s /q %filename%.spec

echo ----------------Build %filename% finished!----------------