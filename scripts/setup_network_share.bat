@echo off
REM Request admin privileges
powershell -Command "Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"l:\limo\scripts\setup_network_share.ps1\"' -Verb RunAs -Wait"
pause
