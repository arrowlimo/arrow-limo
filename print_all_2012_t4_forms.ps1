# Print all 2012 T4 forms to default printer
$t4_dir = "l:\limo\T4_2012_Forms"
$pattern = "T4_2012_*.pdf"

Write-Host "=================================="
Write-Host "Printing all 2012 T4 Forms"
Write-Host "=================================="
Write-Host ""

# Get all 2012 T4 PDFs
$files = Get-ChildItem -Path $t4_dir -Filter $pattern -File | Sort-Object Name

Write-Host "Found $($files.Count) T4 forms to print:"
Write-Host ""

$count = 0
foreach ($file in $files) {
    $count = $count + 1
    Write-Host "$count. Sending to printer: $($file.Name)"
    
    # Use Start-Process to print via system default
    try {
        Start-Process -FilePath $file.FullName -Verb Print -WindowStyle Hidden -Wait -ErrorAction Stop
        Write-Host "   Success"
    }
    catch {
        Write-Host "   Error: $_"
    }
    
    Start-Sleep -Milliseconds 1000
}

Write-Host ""
Write-Host "=================================="
Write-Host "Complete! Sent $count T4 forms to printer."
Write-Host "=================================="
Write-Host ""
