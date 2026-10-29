# Build CodeJudge Windows app (onedir, portable, slim)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -q -U pip
python -m pip install -q "pyinstaller>=6.0" openpyxl

$pyArgs = @(
  "--noconfirm",
  "--clean",
  "--windowed",
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

$dist = Join-Path $PSScriptRoot "dist\CodeJudge"
# Write readme via Python (avoid PowerShell mojibake on Chinese filenames)
python tools\write_dist_readme.py $dist

Write-Host "Build OK: $dist\CodeJudge.exe"
Get-ChildItem $dist -File | Select-Object Name, Length | Format-Table
$size = (Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("Total size: {0:N1} MB" -f $size)
