# Build CodeJudge as a single-file Windows exe (onefile)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -q -U pip
python -m pip install -q "pyinstaller>=6.0" openpyxl

# Remove old onedir output if present
$oldDir = Join-Path $PSScriptRoot "dist\CodeJudge"
if (Test-Path $oldDir) {
  Remove-Item -Recurse -Force $oldDir
}

$pyArgs = @(
  "--noconfirm",
  "--clean",
  "--windowed",
  "--onefile",
  "--name", "CodeJudge",
  "--paths", "tools",
  "--hidden-import", "openpyxl",
  "--hidden-import", "openpyxl.cell._writer",
  "--hidden-import", "paths",
  "--hidden-import", "vision_client",
  "--hidden-import", "extract_submissions",
  "--hidden-import", "grade_exam",
  "--hidden-import", "export_excel",
  "--hidden-import", "pipeline",
  "--hidden-import", "write_dist_readme",
  "--exclude-module", "matplotlib",
  "--exclude-module", "pandas",
  "--exclude-module", "numpy",
  "--exclude-module", "scipy",
  "--exclude-module", "PySide6",
  "--exclude-module", "PyQt5",
  "--exclude-module", "PyQt6",
  "--exclude-module", "IPython",
  "--exclude-module", "notebook",
  "--exclude-module", "pytest",
  "main.py"
)

python -m PyInstaller @pyArgs

$distDir = Join-Path $PSScriptRoot "dist"
$exe = Join-Path $distDir "CodeJudge.exe"
if (-not (Test-Path $exe)) {
  throw "Build failed: $exe not found"
}

# README next to the single exe
python tools\write_dist_readme.py $distDir

Write-Host "Build OK: $exe"
Get-Item $exe | Select-Object FullName, @{N='MB';E={[math]::Round($_.Length/1MB,1)}}
Get-ChildItem $distDir -File | Select-Object Name, Length | Format-Table
