# Network Share Setup - Run as Administrator
Write-Host "Setting up network share..." -ForegroundColor Cyan

$sharePath = "Z:\limo_files"
$shareName = "limo_files"

# Remove existing share if present
Get-SmbShare -Name $shareName -ErrorAction SilentlyContinue | Remove-SmbShare -Force

# Create new share
New-SmbShare -Name $shareName -Path $sharePath -FullAccess "Everyone" -Description "Arrow Limousine File Storage"
Set-SmbShare -Name $shareName -FolderEnumerationMode Unrestricted -Force

# Set NTFS permissions
$acl = Get-Acl $sharePath
$permission = "Everyone","FullControl","ContainerInherit,ObjectInherit","None","Allow"
$accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule $permission
$acl.AddAccessRule($accessRule)
Set-Acl $sharePath $acl

Write-Host "Share created: \\$env:COMPUTERNAME\limo_files" -ForegroundColor Green
Write-Host "On dispatch1, run: net use Z: \\$env:COMPUTERNAME\limo_files /persistent:yes" -ForegroundColor Yellow
