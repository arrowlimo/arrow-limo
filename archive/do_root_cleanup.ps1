$arch = "L:\limo\archive\archive_20260418"
$limo = "L:\limo"
New-Item -ItemType Directory -Path $arch -Force | Out-Null

$total = 0

# Helper
function MoveToArch($files) {
    $c = 0
    foreach ($f in $files) {
        $dest = Join-Path $arch $f.Name
        if (Test-Path $dest) { $dest = Join-Path $arch ($f.BaseName + "_DUP" + $f.Extension) }
        Move-Item $f.FullName $dest -Force
        $c++
    }
    return $c
}

# .py files
$c = MoveToArch (Get-ChildItem "$limo\*.py")
Write-Host ".py moved: $c"; $total += $c

# .csv files
$c = MoveToArch (Get-ChildItem "$limo\*.csv")
Write-Host ".csv moved: $c"; $total += $c

# .sql files
$c = MoveToArch (Get-ChildItem "$limo\*.sql")
Write-Host ".sql moved: $c"; $total += $c

# .log files
$c = MoveToArch (Get-ChildItem "$limo\*.log")
Write-Host ".log moved: $c"; $total += $c

# .txt files except requirements.txt
$c = MoveToArch (Get-ChildItem "$limo\*.txt" | Where-Object Name -ne 'requirements.txt')
Write-Host ".txt moved: $c"; $total += $c

# .md files except README.md
$c = MoveToArch (Get-ChildItem "$limo\*.md" | Where-Object Name -ne 'README.md')
Write-Host ".md moved: $c"; $total += $c

# T4 PDFs to T4_2012_Forms
$t4dir = "$limo\T4_2012_Forms"
New-Item -ItemType Directory -Path $t4dir -Force | Out-Null
$c = 0
Get-ChildItem "$limo\T4_*.pdf" | ForEach-Object { Move-Item $_.FullName "$t4dir\$($_.Name)" -Force; $c++ }
Write-Host "T4 PDFs to T4_2012_Forms: $c"; $total += $c

# Other PDFs to archive
$c = MoveToArch (Get-ChildItem "$limo\*.pdf" | Where-Object Name -notmatch '^T4_')
Write-Host "other PDFs moved: $c"; $total += $c

# .json to archive (but keep render.yaml adjacent; skip package.json)
$c = MoveToArch (Get-ChildItem "$limo\*.json" | Where-Object { $_.Name -notmatch '^(package|tsconfig)' })
Write-Host ".json moved: $c"; $total += $c

# .xlsx
$c = MoveToArch (Get-ChildItem "$limo\*.xlsx")
Write-Host ".xlsx moved: $c"; $total += $c

# .html
$c = MoveToArch (Get-ChildItem "$limo\*.html")
Write-Host ".html moved: $c"; $total += $c

# .bat
$c = MoveToArch (Get-ChildItem "$limo\*.bat")
Write-Host ".bat moved: $c"; $total += $c

# .ps1
$c = MoveToArch (Get-ChildItem "$limo\*.ps1")
Write-Host ".ps1 moved: $c"; $total += $c

# .dump
$c = MoveToArch (Get-ChildItem "$limo\*.dump" -ErrorAction SilentlyContinue)
Write-Host ".dump moved: $c"; $total += $c

Write-Host ""
Write-Host "=== TOTAL MOVED: $total ==="
Write-Host ""
Write-Host "=== REMAINING ROOT FILES ==="
Get-ChildItem "$limo" -File -Depth 0 | Select-Object Name | Format-Table -HideTableHeaders
