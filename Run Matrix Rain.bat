@echo off
cd /d "%~dp0"
REM Prefer pythonw (no console); fallback to py -3 or python
where pythonw >nul 2>&1 && pythonw "run_matrix_rain.pyw" && exit /b 0
py -3 "run_matrix_rain.pyw" 2>nul && exit /b 0
python "run_matrix_rain.pyw" 2>nul && exit /b 0
echo Matrix Rain needs Python 3 and PyQt5.
echo Install: pip install PyQt5
echo Or use the standalone "Matrix Rain.exe" from the dist folder if you built it.
pause
