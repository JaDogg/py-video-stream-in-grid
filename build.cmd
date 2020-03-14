@echo off
del *.spec
pyinstaller streamer_server.py --onefile --add-data="templates;templates"