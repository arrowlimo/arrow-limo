# Create shared network user - RUN AS ADMIN
$username = "ArrowDispatch"
$password = "Dispatch2026!" | ConvertTo-SecureString -AsPlainText -Force

# Create user if doesn't exist
try {
    Get-LocalUser -Name $username -ErrorAction Stop
    Write-Host "User $username already exists" -ForegroundColor Yellow
} catch {
    New-LocalUser -Name $username -Password $password -PasswordNeverExpires -Description "Shared account for dispatch workstations"
    Write-Host "Created user: $username" -ForegroundColor Green
}

# Add to Users group
Add-LocalGroupMember -Group "Users" -Member $username -ErrorAction SilentlyContinue

# Grant access to the share
Grant-SmbShareAccess -Name "limo_files" -AccountName $username -AccessRight Full -Force

# Grant NTFS permissions
icacls "Z:\limo_files" /grant "${username}:F" /T

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "`nOn dispatch1, use:" -ForegroundColor Yellow
Write-Host "net use Z: \\DISPATCHMAIN\limo_files /user:DISPATCHMAIN\$username /persistent:yes" -ForegroundColor White
Write-Host "`nPassword: Dispatch2026!" -ForegroundColor White
