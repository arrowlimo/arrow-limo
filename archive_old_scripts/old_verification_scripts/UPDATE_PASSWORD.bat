@echo off
REM ═══════════════════════════════════════════════════════════════════════════  
REM Update .env with correct PostgreSQL password
REM ═══════════════════════════════════════════════════════════════════════════

echo.
echo ═══════════════════════════════════════════════════════════════════════════
echo  Update Database Password
echo ═══════════════════════════════════════════════════════════════════════════
echo.
echo Enter the PostgreSQL 'postgres' user password
echo (This is the password you set when PostgreSQL was installed)
echo.
set /p PGPASS="PostgreSQL Password: "

if "%PGPASS%"=="" (
    echo ERROR: Password cannot be empty
    pause
    exit /b 1
)

cd /d L:\limo

REM Backup current .env
copy .env .env.backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%
echo Backup created: .env.backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%

REM Update .env with new password
powershell -Command "(Get-Content .env) -replace '^DB_PASSWORD=.*', 'DB_PASSWORD=%PGPASS%' | Set-Content .env.temp"
move /y .env.temp .env

REM Also update .env.local
powershell -Command "(Get-Content .env.local) -replace '^DB_PASSWORD=.*', 'DB_PASSWORD=%PGPASS%' | Set-Content .env.local.temp"
move /y .env.local.temp .env.local

echo.
echo ✓ Password updated in .env and .env.local
echo.
echo Testing connection...
echo.

set DB_PASSWORD=%PGPASS%
.venv\Scripts\python.exe diagnose_connection.py

echo.
pause
