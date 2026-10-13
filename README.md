# chatlog 分析工具包

把一份长期双人聊天记录（SQLite 导出），逐日交给大模型理解，产出**每日情绪浓度评分（1-5）**、**事件提取**、**索引表**和**日历热力图**。

设计目标：**任何 agent 拿到这个目录，读完本文件 + `AGENTS.md` 就能独立跑通全流程**，不需要原始作者在场。

> **English**: A day-by-day LLM analyzer for long-term two-person chat logs. It scores each day's emotional intensity (1-5), extracts events, and produces an event index plus an interactive calendar heatmap. Designed to be picked up and run by any agent with zero prior context — see `AGENTS.md` for the quick spec. All docs are in Chinese; code comments are bilingual-friendly.

---

## 1. 快速开始（三步）

```bash
pip install -r requirements.txt

# 冒烟测试：用合成样本数据跑通全流程（2 天，花费约 1 分钱）
python run_all.py --db examples/sample.db --out /tmp/smoke --api-key sk-xxx

# 零成本验证载荷：只构建请求不调用 API（不花钱）
python run_all.py --db examples/sample.db --out /tmp/smoke --dry-run

# 正式运行：全量
python run_all.py --db /path/to/chat.db --out /path/to/output --api-key sk-xxx --workers 5

# 使用外部（已校准的）prompt 替代内置模板
python run_all.py --db /path/to/chat.db --out /path/to/output \
  --api-key sk-xxx --prompt-file /path/to/prompt_calibrated.txt
```

`run_all.py` 依次执行三阶段：**清洗切分 → 逐日评分 → 汇总产出**。全部支持断点续跑（重跑自动跳过已完成的天）。

Key 也可用环境变量：`export DEEPSEEK_API_KEY=sk-xxx`

---

## 2. 目录结构

```
run_all.py                  一键串起三阶段
config.example.json         可选配置文件模板
requirements.txt

pipeline/
  config.py                 参数解析（所有阶段共用）
  clean_split.py            Stage 1 清洗 + 按天切分
  prompt_template.py        Stage 2 的评分规则（★改这里 = 改评分标准）
  run_analysis.py           Stage 2 逐日评分（5 并发 + 断点）
  build_outputs.py          Stage 3 汇总：索引表 / 事件文档 / 可视化

docs/
  输入数据格式.md            SQLite 表结构与字段语义，含字段映射说明
  评分规则与校准方法.md       ★方法论核心：规则设计、锚点校准、防漂移
  产出物说明.md              四类产出物的字段与用途

examples/
  sample.db                 合成样本数据（2 天，可公开分发）
  make_sample_db.py         样本数据生成脚本
```

---

## 3. 输入要求

一份 SQLite 数据库，含 `msg` 表，字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `ts` | INTEGER | **毫秒**时间戳（注意不是秒） |
| `tstr` | TEXT | `YYYY-MM-DD HH:MM:SS` 格式时间 |
| `sender` | TEXT | 发送者昵称 |
| `mtype` | TEXT | 消息类型，`type_1` 为普通消息 |
| `text` | TEXT | 正文；资源消息为占位符如 `[图片: hash.png]` |
| `system` | INTEGER | 1 = 系统消息，需剔除 |
| `hasres` / `restype` | INTEGER/TEXT | 是否含资源（image/audio/video/file） |

细节与字段映射说明见 `docs/输入数据格式.md`。**换用其他导出工具时，只需把字段映射到这张表即可。**

---

## 4. 输出

| 产出 | 路径 | 用途 |
|------|------|------|
| 每日评分 JSON | `results/<日期>.json` | 原始结构化结果，一切产出的数据源 |
| 事件索引表 | `输出/事件索引表.md` / `.csv` | 全部事件的表格索引，可筛选统计 |
| 年度事件文档 | `输出/事件/<年>.md` | 按年浏览事件与当日概要 |
| 可视化 | `输出/可视化.html` | 日历热力图 + 大事件时间轴 + 统计面板 |
| 清洗后日数据 | `data/days/<日期>.json` | 供复查原文用 |

字段定义见 `docs/产出物说明.md`。

---

## 5. 关于评分规则（最重要的一节）

评分标准写在 `pipeline/prompt_template.py`，包含：

- **情绪浓度 1-5 分**的定义（面向"情绪内敛型"情侣标定，不以情绪外显强度为主要依据）
- **行为信号表**（他们式的不开心/开心长什么样）
- **6 个锚定样例**（分数标尺，跑之前必须按目标数据重新校准）
- **极性**与**事件等级**（事件等级与浓度正交，是两个维度）

> **换一份聊天记录使用时，规则文本可以沿用，但锚点必须重校准。**
> 校准方法（怎么挑候选日、怎么定分、怎么验证）见 `docs/评分规则与校准方法.md`，那是本工具包真正的核心资产。

### 重要：prompt 版本决定标尺位置

内置的 `prompt_template.py` 中的锚点经过**泛化**处理（去掉具体日期，改为结构示范），目的是让工具包可公开分发。实测发现：

- 泛化锚点版与原始校准版在 2/3 分边界上存在**系统性偏移**（约 111/1200 天由 3 分降为 2 分，年度均值差 0.06-0.15）
- 这不是随机噪声：用同一版本 prompt 在两个不同环境复跑 60 天，结果 **100% 一致、平均偏差 0.000**

结论：**具体数据集的"权威标尺"应保存为独立的 prompt 文件，用 `--prompt-file` 加载**，而不要把校准后的锚点写回内置模板（会破坏工具包的通用性）。同一份结果集必须始终使用同一版 prompt，混用不同版本会污染事件计数类统计。

---

## 6. 成本与耗时（实测参考）

- 模型：`deepseek-flash`（DeepSeek-V4.1-Flash，1M 上下文，支持 JSON 输出）
- 规模：1200 天 / 约 31 万条消息
- 实测：输入约 500 万 token、输出约 50 万 token，**总成本约 6 元**，5 并发耗时约 20 分钟
- 结论：全量重跑很便宜，**不要怕重跑** —— 校准后整段重跑是正确的做法

---

## 7. 常见坑（都已处理，换数据时注意）

1. `ts` 是毫秒，不是秒
2. 图片只有哈希占位符，**模型看不到图片内容**，必须在 prompt 里声明这个盲区
3. 系统消息（`system=1`）与 `[自动回复]` 是机器生成的，需剔除，否则污染词面和判断
4. 刷屏连发（同一人连续发相同文本）需折叠为 `文本 xN`，否则会虚增消息量和情绪强度
5. 超长日（实测最大 3,880 条）在 1M 上下文下仍可单次处理，无需分窗

---

## 8. 免责与隐私

- 工具包本身**不含任何真实聊天数据**，`examples/sample.db` 为完全合成的样本
- 若把真实数据用于分析，注意 API 调用会把对话内容发送给模型提供方
