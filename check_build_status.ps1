#!/usr/bin/env powershell
"""
Arrow Limousine Desktop App - Build Status Checker
Run this anytime to check if the exe build is complete
"""

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Arrow Limousine Desktop App - Build Status Checker            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check if Python build is still running
$pythonProcesses = Get-Process python* -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Write-Host "⏳ BUILD IN PROGRESS" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Active Python processes:" -ForegroundColor White
    $pythonProcesses | Select-Object Name, Id, @{Name="Time Running";Expression={if($_.StartTime){[math]::Round(((Get-Date) - $_.StartTime).TotalSeconds)} else {"N/A"}}} | Format-Table
    Write-Host ""
    Write-Host "Wait a few more minutes for the build to complete." -ForegroundColor Gray
    Write-Host "First-time builds take 3-5 minutes. This is normal." -ForegroundColor Gray
} else {
    Write-Host "No Python build processes running." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Build Output:" -ForegroundColor White
Write-Host "─────────────────────────────────────────────────────────────────"

# Check for exe
if (Test-Path ".\dist\ArrowLimousineApp.exe") {
    $exeFile = Get-Item ".\dist\ArrowLimousineApp.exe"
    Write-Host ""
    Write-Host "✅ BUILD COMPLETE!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Exe Location:" -ForegroundColor White
    Write-Host "  $($exeFile.FullName)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Exe Details:" -ForegroundColor White
    Write-Host "  Size: $([math]::Round($exeFile.Length/1MB, 2)) MB" -ForegroundColor Green
    Write-Host "  Created: $($exeFile.CreationTime)" -ForegroundColor Green
    Write-Host ""
    
    if (Test-Path ".\dist\ArrowLimousine_Deployment") {
        Write-Host "Deployment Package:" -ForegroundColor White
        Write-Host "  Location: .\dist\ArrowLimousine_Deployment" -ForegroundColor Green
        Write-Host "  Status: Ready to distribute" -ForegroundColor Green
        Write-Host ""
        Write-Host "Next Steps:" -ForegroundColor Cyan
        Write-Host "  1. Test the exe: double-click .\dist\ArrowLimousineApp.exe" -ForegroundColor White
        Write-Host "  2. Create distribution ZIP:" -ForegroundColor White
        Write-Host "     Compress-Archive -Path '.\dist\ArrowLimousine_Deployment' -DestinationPath 'ArrowLimousine_Installer.zip'" -ForegroundColor Gray
        Write-Host "  3. Send ZIP to dispatcher with .env.example instructions" -ForegroundColor White
    }
} else {
    Write-Host ""
    Write-Host "⏳ EXE NOT YET CREATED" -ForegroundColor Yellow
    Write-Host ""
    
    # Check if build directory exists
    if (Test-Path ".\build") {
        $buildSize = (Get-ChildItem ".\build" -Recurse | Measure-Object -Property Length -Sum).Sum
        Write-Host "Build files created: $([math]::Round($buildSize/1MB, 2)) MB" -ForegroundColor Gray
        Write-Host "This indicates the build is in progress. Build typically takes 3-5 minutes total." -ForegroundColor Gray
    } else {
        Write-Host "Build directory not found. Did you start the build?" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To start the build, run:" -ForegroundColor Cyan
        Write-Host "  .\build_exe.bat   (Windows batch - recommended)" -ForegroundColor White
        Write-Host "  .\build_exe.ps1   (PowerShell)" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host ""

# Show file system
Write-Host "Files in dist/ folder:" -ForegroundColor White
if (Test-Path ".\dist") {
    Get-ChildItem ".\dist" -Depth 1 | Select-Object Name, @{Name="Type";Expression={if($_.PSIsContainer){"Folder"}else{"File"}}}, @{Name="Size";Expression={if($_.PSIsContainer){$size=($_ | Measure-Object -Property Length -Sum -Recurse).Sum; "$([math]::Round($size/1MB,2))MB (Folder)"} else {$_.Length}}} | Format-Table -AutoSize
} else {
    Write-Host "  dist/ folder not yet created (build hasn't started or completed)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Need help?" -ForegroundColor Yellow
Write-Host "  See: DEPLOYMENT_QUICK_START.md" -ForegroundColor White
Write-Host "  See: BUILD_DEPLOYMENT.md" -ForegroundColor White
Write-Host ""
