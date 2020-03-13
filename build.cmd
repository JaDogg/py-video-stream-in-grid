@echo off
pyinstaller server.py --onefile --add-data="templates\index.html;.\templates\index.html"