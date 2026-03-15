@echo off
echo ===================================================================
echo RESTORE NEON DATABASE
echo ===================================================================
echo.
echo WARNING: This will REPLACE the current Neon database!
echo THIS IS EXTREMELY DANGEROUS!
echo.
pause

set PGPASSWORD=npg_rlL0yK9pvfCW

echo Restoring from: l:\limo\database_backups_20260205_120225\neon\data.backup
pg_restore -h ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech -U neondb_owner -d neondb --clean --if-exists --no-owner --no-privileges "l:\limo\database_backups_20260205_120225\neon\data.backup"

echo.
echo Restore complete!
pause
