@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM QUICK FIX: Update .env to use Windows Authentication
REM Run this if the PowerShell script doesn't work
REM ═══════════════════════════════════════════════════════════════════════════

echo.
echo ═══════════════════════════════════════════════════════════════════════════
echo  Quick Fix: Enable Windows Authentication
echo ═══════════════════════════════════════════════════════════════════════════
echo.
echo This will update your .env file to remove the password
echo and use Windows Integrated Authentication instead.
echo.
pause

cd /d L:\limo

REM Backup current .env
copy .env .env.backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
echo Backup created: .env.backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%

REM Create new .env with empty password (triggers Windows auth)
powershell -Command "(Get-Content .env) -replace '^DB_PASSWORD=.*', 'DB_PASSWORD=' | Set-Content .env.temp"
move /y .env.temp .env

echo.
echo ✓ Updated .env file to use Windows Authentication
echo.
echo Testing connection...
echo.

.venv\Scripts\python.exe diagnose_connection.py

echo.
echo If you see "CONNECTION SUCCESSFUL" above, you can now launch the app!
echo.
pause
