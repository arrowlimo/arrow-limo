@echo off
echo ===================================================================
echo RESTORE LOCAL DATABASE
echo ===================================================================
echo.
echo WARNING: This will REPLACE the current database!
echo.
pause

set PGPASSWORD=alms_secure_password_2024

echo Restoring from: l:\limo\database_backups_20260205_120225\local\data.backup
pg_restore -h localhost -U alms -d almsdata --clean --if-exists --no-owner --no-privileges "l:\limo\database_backups_20260205_120225\local\data.backup"

echo.
echo Restore complete!
pause
