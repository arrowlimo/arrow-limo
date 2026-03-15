# =========================================================
# CHECK VS CODE SETTINGS FOR AUTO-FORMATTER CORRUPTION
# Run this on DISPATCH1 to verify protection is enabled
# =========================================================

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  CHECKING VS CODE FORMATTER SETTINGS" -ForegroundColor Cyan
Write-Host "  DISPATCH1 Protection Verification" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

$IssuesFound = 0

# Check 1: Dangerous Extensions Installed
Write-Host "[1/5] Checking for dangerous extensions..." -ForegroundColor Yellow
Write-Host ""

$DangerousExtensions = @(
    "ms-python.black-formatter",
    "esbenp.prettier-vscode",
    "ms-python.autopep8",
    "charliermarsh.ruff"
)

try {
    $InstalledExtensions = code --list-extensions 2>$null
    
    foreach ($ext in $DangerousExtensions) {
        if ($InstalledExtensions -contains $ext) {
            Write-Host "  ❌ DANGER: $ext is installed!" -ForegroundColor Red
            $IssuesFound++
        } else {
            Write-Host "  ✅ OK: $ext not installed" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "  ⚠️  Could not check extensions (VS Code may not be in PATH)" -ForegroundColor Yellow
}

# Check 2: Workspace Settings File
Write-Host ""
Write-Host "[2/5] Checking workspace settings file..." -ForegroundColor Yellow
Write-Host ""

$SettingsPath = "L:\limo\.vscode\settings.json"

if (Test-Path $SettingsPath) {
    Write-Host "  ✅ Settings file exists: $SettingsPath" -ForegroundColor Green
    
    $Settings = Get-Content $SettingsPath -Raw
    
    # Check for dangerous settings
    if ($Settings -match '"editor.formatOnSave":\s*false') {
        Write-Host "  ✅ Format on Save is OFF" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Format on Save is not properly disabled!" -ForegroundColor Red
        $IssuesFound++
    }
    
    if ($Settings -match '"black-formatter.importStrategy":\s*"disabled"') {
        Write-Host "  ✅ Black formatter is disabled" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Black formatter setting not found" -ForegroundColor Yellow
        $IssuesFound++
    }
    
    if ($Settings -match '"prettier.enable":\s*false') {
        Write-Host "  ✅ Prettier is disabled" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Prettier disable setting not found" -ForegroundColor Yellow
        $IssuesFound++
    }
    
} else {
    Write-Host "  ❌ Settings file not found at: $SettingsPath" -ForegroundColor Red
    Write-Host "     This is a problem! The workspace may not have formatter protection." -ForegroundColor Red
    $IssuesFound++
}

# Check 3: Test main.py syntax
Write-Host ""
Write-Host "[3/5] Testing main.py syntax..." -ForegroundColor Yellow
Write-Host ""

$MainPyPaths = @(
    "L:\limo\desktop_app\main.py",
    "L:\limo\DEPLOYMENT_PACKAGE\app\desktop_app\main.py",
    "Y:\ArrowLimo\app\desktop_app\main.py"
)

foreach ($path in $MainPyPaths) {
    if (Test-Path $path) {
        try {
            $result = python -m py_compile "$path" 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✅ $path - Syntax OK" -ForegroundColor Green
            } else {
                Write-Host "  ❌ $path - SYNTAX ERRORS!" -ForegroundColor Red
                Write-Host "     $result" -ForegroundColor Red
                $IssuesFound++
            }
        } catch {
            Write-Host "  ⚠️  Could not test $path" -ForegroundColor Yellow
        }
    }
}

# Check 4: User VS Code Settings
Write-Host ""
Write-Host "[4/5] Checking user VS Code settings..." -ForegroundColor Yellow
Write-Host ""

$UserSettingsPath = "$env:APPDATA\Code\User\settings.json"

if (Test-Path $UserSettingsPath) {
    Write-Host "  ℹ️  User settings file exists" -ForegroundColor Cyan
    
    $UserSettings = Get-Content $UserSettingsPath -Raw
    
    if ($UserSettings -match '"editor.formatOnSave":\s*true') {
        Write-Host "  ⚠️  WARNING: Format on Save is ON in user settings!" -ForegroundColor Yellow
        Write-Host "     Workspace setting should override this, but be careful." -ForegroundColor Yellow
    } else {
        Write-Host "  ✅ Format on Save not enabled in user settings" -ForegroundColor Green
    }
} else {
    Write-Host "  ℹ️  No user settings file found (using defaults)" -ForegroundColor Cyan
}

# Check 5: Protection Files
Write-Host ""
Write-Host "[5/5] Checking protection files..." -ForegroundColor Yellow
Write-Host ""

$ProtectionFiles = @{
    "L:\limo\DEPLOYMENT_PACKAGE\.editorconfig" = "EditorConfig protection"
    "L:\limo\DEPLOYMENT_PACKAGE\app\desktop_app\pyproject.toml" = "Black exclusion config"
    "L:\limo\DEPLOYMENT_PACKAGE\WARNING_NO_AUTO_FORMATTERS.md" = "Warning documentation"
}

foreach ($file in $ProtectionFiles.Keys) {
    if (Test-Path $file) {
        Write-Host "  ✅ $($ProtectionFiles[$file]): EXISTS" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  $($ProtectionFiles[$file]): MISSING" -ForegroundColor Yellow
        Write-Host "     File: $file" -ForegroundColor Yellow
    }
}

# Summary
Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  SUMMARY" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

if ($IssuesFound -eq 0) {
    Write-Host "✅ ALL CHECKS PASSED!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your VS Code is properly configured to prevent" -ForegroundColor Green
    Write-Host "auto-formatter corruption." -ForegroundColor Green
    Write-Host ""
    Write-Host "Safe to edit code on DISPATCH1." -ForegroundColor Green
} else {
    Write-Host "⚠️  FOUND $IssuesFound ISSUE(S)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Review the warnings above and take action:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To fix:" -ForegroundColor White
    Write-Host "  1. Uninstall dangerous extensions in VS Code" -ForegroundColor White
    Write-Host "  2. Verify .vscode\settings.json has correct settings" -ForegroundColor White
    Write-Host "  3. Never enable Format on Save" -ForegroundColor White
    Write-Host ""
    Write-Host "See: L:\limo\DEPLOYMENT_PACKAGE\WARNING_NO_AUTO_FORMATTERS.md" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

Read-Host "Press Enter to exit"
