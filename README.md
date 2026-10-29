# CodeJudge — Java 实操卷批改工具

从 Word/截图答卷中提取图片，调用视觉模型按评分细则打分，并导出 Excel。

## 隐私说明

- 学校名称、班级标识、原始答卷、成绩表等**不进入 Git**（见 `.gitignore`）。
- 请将答卷放在 `data/submissions/`（详见 `data/README.md`）。

## 评分细则（宽松示例）

| 分项 | 分值 |
|------|------|
| A 类名 TestStudent | 20 |
| B 完整 main + 有注释（类/方法注释均可） | 20（无注释最多 5） |
| C 定义 Student 类（可同文件） | 10 |
| D name / age 字段 | 10 |
| E sayHello 大意正确即可 | 10 |
| F 实例化并调用 | 15 |
| G 能运行有输出 | 15 |

缺截图不整卷归零；能核实的部分照常给分。姓名默认按文件名解析。

## 使用（推荐：绿色 exe）

```powershell
# 在本机打包
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

将生成的 `dist\CodeJudge\` **整个文件夹**拷到任意 Windows 电脑，双击 `CodeJudge.exe`：

1. 选择答卷目录  
2. 填写阿里云百炼 API Key  
3. 开始批改 → 得到 `output\Java期中成绩表.xlsx`

需联网；旧版 `.doc` 建议本机有 Word。无需安装 Python / Node。

## 使用（源码）

依赖：Python 3、`openpyxl`（旧版 `.doc` 可选 `pywin32`）。

```bash
pip install openpyxl pywin32
python main.py                        # 图形界面
# 或命令行：
python tools/extract_submissions.py
python tools/grade_exam.py
python tools/export_excel.py
```

环境变量：`DASHSCOPE_API_KEY`（可选，界面也可填写）。
