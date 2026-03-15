@echo off
REM Bulk Receipt Deletion Tool Launcher
REM Double-click this file to run the bulk delete tool

echo.
echo ================================================================
echo   BULK RECEIPT DELETION TOOL
echo ================================================================
echo.
echo This tool lets you select and delete multiple receipts at once.
echo.
echo Starting...
echo.

cd /d "%~dp0.."
.venv\Scripts\python.exe scripts\bulk_delete_receipts.py --quick

pause
