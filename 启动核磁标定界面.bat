@echo off
setlocal
python "%~dp0nmr_gui.py"
if errorlevel 1 pause
