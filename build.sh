#!/bin/bash
rm  *.spec
pyinstaller streamer_server.py --onefile --add-data="templates:templates"