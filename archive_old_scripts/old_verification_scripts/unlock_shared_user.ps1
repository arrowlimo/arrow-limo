# Unlock and setup shared account - RUN AS ADMIN
$username = "ArrowDispatch"
$password = "Dispatch2026!"

# Unlock if locked
try {
    $user = Get-LocalUser -Name $username -ErrorAction Stop
    if ($user.Enabled -eq $false) {
        Enable-LocalUser -Name $username
        Write-Host "Account unlocked: $username" -ForegroundColor Green
    }
} catch {
    # Create if doesn't exist
    $securePassword = ConvertTo-SecureString $password -AsPlainText -Force
    New-LocalUser -Name $username -Password $securePassword -PasswordNeverExpires -UserMayNotChangePassword -Description "Shared account for dispatch workstations"
    Enable-LocalUser -Name $username
    Write-Host "Created user: $username" -ForegroundColor Green
}

# Add to Users group
Add-LocalGroupMember -Group "Users" -Member $username -ErrorAction SilentlyContinue

# Grant share access
Grant-SmbShareAccess -Name "limo_files" -AccountName $username -AccessRight Full -Force -ErrorAction SilentlyContinue

# Grant NTFS permissions
icacls "Z:\limo_files" /grant "${username}:(OI)(CI)F" /T /C

Write-Host "`n[OK] Setup complete!" -ForegroundColor Green
Write-Host "`nCredentials for dispatch computers:" -ForegroundColor Yellow
Write-Host "Username: DISPATCHMAIN\$username" -ForegroundColor White
Write-Host "Password: $password" -ForegroundColor White
