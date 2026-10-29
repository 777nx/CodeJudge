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
python -c @"
from pathlib import Path
p = Path(r'$dist') / '使用说明.txt'
p.write_text('''CodeJudge 使用说明
================

1. 双击 CodeJudge.exe
2. 选择学生答卷文件夹（含 .docx / 图片）
3. 填写阿里云百炼 API Key（DashScope）
4. 点击「开始批改」
5. 成绩表在本目录 output\\Java期中成绩表.xlsx

注意：
- 需要联网（识图 API）
- 旧版 .doc 建议安装 Microsoft Word
- 请复制整个 CodeJudge 文件夹到其他电脑，不要只拷 exe
- API Key 会保存在同目录 codejudge_config.json
''', encoding='utf-8')
print('wrote', p)
"@

Write-Host "Build OK: $dist\CodeJudge.exe"
Get-ChildItem $dist -File | Select-Object Name, Length | Format-Table
$size = (Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("Total size: {0:N1} MB" -f $size)
