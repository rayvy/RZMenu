@echo off
chcp 65001 > nul
echo Running RZMenu Translation Analyzer...
echo ---------------------------------------------
python "%~dp0analyze.py"
echo ---------------------------------------------
pause
