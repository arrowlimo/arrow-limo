@echo off
echo ============================================
echo   Arrow Limousine - Access Files
echo ============================================
echo.
echo Opening network locations...
echo.

REM Open file storage
echo Opening file storage (limo_files)...
start \\DISPATCHMAIN\limo_files

REM Open application files
echo Opening application folder...
start \\DISPATCHMAIN\limo

echo.
echo ============================================
echo   Network Paths Reference
echo ============================================
echo.
echo File Storage:
echo   \\DISPATCHMAIN\limo_files
echo.
echo Application Files:
echo   Frontend: \\DISPATCHMAIN\limo\frontend
echo   Backend:  \\DISPATCHMAIN\limo\modern_backend
echo.
echo If Z: drive didn't map, you can access
echo files directly using these network paths.
echo.
pause
