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

## 使用

依赖：Python 3（`openpyxl`、处理旧版 `.doc` 时需 `pywin32`）、Node.js（通义视觉识图脚本）。

可选环境变量：`CODEJUDGE_VISION_JS`（指向 `vision.js` 绝对路径）。

```bash
pip install openpyxl pywin32
python tools/extract_submissions.py   # 抽图
python tools/grade_exam.py            # 识图打分
python tools/rebuild_grades.py        # 仅重解析已有 vision_raw
python tools/export_excel.py          # 导出 Excel → output/Java期中成绩表.xlsx
```
