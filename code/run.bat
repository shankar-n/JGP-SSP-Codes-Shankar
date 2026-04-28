@echo off

REM Change this to your Anaconda install path if needed
CALL "%USERPROFILE%\anaconda3\Scripts\activate.bat"

REM Activate your environment (replace with your env name)
CALL conda activate base

REM Launch marimo editor (replace notebook filename)
marimo edit notebook1.py

pause