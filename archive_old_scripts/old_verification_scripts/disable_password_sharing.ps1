# Disable Password Protected Sharing - Run as Administrator
Write-Host "Disabling password-protected sharing..." -ForegroundColor Cyan

# Enable guest account
net user guest /active:yes

# Set registry keys to disable password-protected sharing
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "everyoneincludesanonymous" -Value 1 -Type DWord
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters" -Name "RestrictNullSessAccess" -Value 0 -Type DWord

# Enable insecure guest logons (needed for Windows 10/11)
if (-not (Test-Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\LanmanWorkstation")) {
    New-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\LanmanWorkstation" -Force
}
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\LanmanWorkstation" -Name "AllowInsecureGuestAuth" -Value 1 -Type DWord

Write-Host "Registry settings updated!" -ForegroundColor Green
Write-Host "Now manually disable password-protected sharing:" -ForegroundColor Yellow
Write-Host "1. Press Win+R and type: control.exe /name Microsoft.NetworkAndSharingCenter" -ForegroundColor White
Write-Host "2. Click 'Change advanced sharing settings'" -ForegroundColor White  
Write-Host "3. Expand 'All Networks'" -ForegroundColor White
Write-Host "4. Select 'Turn off password protected sharing'" -ForegroundColor White
Write-Host "5. Click 'Save changes'" -ForegroundColor White

Start-Process "control.exe" -ArgumentList "/name Microsoft.NetworkAndSharingCenter"
