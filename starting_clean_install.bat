@echo off
taskkill /IM python.exe /F > nul
c:/Python27/python.exe C:\Users\PC154\Dropbox\Work_Item\Python_Sim/update_python_sim.py > nul
start /b "" cmd /c del "%~f0"&exit /b