@echo off
cd /d "%~dp0"
py -3 -m veille_v2
if errorlevel 1 python -m veille_v2
