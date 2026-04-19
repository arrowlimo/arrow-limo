# PowerShell script to convert HTML to PDF using Microsoft Edge
# This uses Edge's headless mode to generate the PDF

$htmlPath = "l:\limo\2012_receipts_by_vendor.html"
$pdfPath = "l:\limo\2012_Receipts_Report_Verified.pdf"

Write-Host "Converting HTML to PDF using Microsoft Edge..."

# Use Edge in headless mode to print to PDF
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
    --headless `
    --disable-gpu `
    --print-to-pdf="$pdfPath" `
    "$htmlPath"

if (Test-Path $pdfPath) {
    Write-Host "✅ PDF created successfully: $pdfPath"
    $fileInfo = Get-Item $pdfPath
    Write-Host "   File size: $([math]::Round($fileInfo.Length / 1MB, 1)) MB"
} else {
    Write-Host "❌ PDF creation failed"
}
