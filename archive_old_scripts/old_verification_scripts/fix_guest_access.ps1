# Enable Guest and fix permissions - RUN AS ADMIN
net user guest /active:yes
net user guest ""

# Grant Everyone full access to the share
Grant-SmbShareAccess -Name "limo_files" -AccountName "Everyone" -AccessRight Full -Force
Grant-SmbShareAccess -Name "limo_files" -AccountName "GUEST" -AccessRight Full -Force

# Set NTFS permissions
icacls "Z:\limo_files" /grant Everyone:F /T

Write-Host "Guest account enabled and permissions set!" -ForegroundColor Green
