<div align="center">

<!-- 多语言切换：当前仅中文，待补 -->
<!-- **English** · [简体中文](README_zh.md) -->

# CLA: ChatLog Analyzer

### 把长期双人聊天记录逐日交给大模型理解，产出情绪浓度评分、事件提取、索引表与日历热力图。

**看见一段关系的时间形状——哪几天在吵，哪几天在笑，几年是怎么走过来的。**

[![license](https://img.shields.io/badge/license-MIT-f4c430?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](#快速开始)
[![model](https://img.shields.io/badge/model-deepseek--flash-4D6BFE?style=flat-square)](#成本与耗时)
[![dependencies](https://img.shields.io/badge/dependencies-1%20(httpx)-brightgreen?style=flat-square)](requirements.txt)
[![agent-ready](https://img.shields.io/badge/agent--ready-AGENTS.md-5c4ee5?style=flat-square)](AGENTS.md)

<!-- 项目主页 / 在线演示：待补 -->

[快速开始](#快速开始) · [工作原理](#工作原理) · [输入要求](#输入要求) · [产出物](#产出物) · [评分规则与标尺](#评分规则与标尺) · [常见问题](#常见问题) · [文档](#文档)

<code>pip install -r requirements.txt</code>

<br />

<!-- 截图：待补。建议放「日历热力图 + 大事件时间轴」整屏截图，存为 docs/assets/screenshot-calendar.png -->
<!-- <img src="docs/assets/screenshot-calendar.png" alt="CLA 生成的日历热力图与大事件时间轴" width="1200" /> -->

<br /><br />

</div>

---

一份几年的聊天记录，几万到几十万条消息，人眼通读不现实。CLA 把它逐日交给大模型理解：每天做一个独立判断，产出这天的**情绪浓度（1-5 分）**、**事件清单**和**当日概要**，最后汇总成可筛选的索引表和可交互的日历热力图。

它最初是为了回看一段四年的感情记录而写，所以整套设计都针对**长期、高频、口语化、情绪内敛**的双人对话做了标定：不靠感叹号判断情绪，而是看行为信号——分享的细节变多了没有、回复节奏变快还是变慢、称呼有没有变、是不是突然沉默。

评分标尺不是硬编码的规则文本，而是**可校准的锚点体系**：每个分数档配真实确认过的样例，换一份数据时按文档里的方法重新校准即可。这是这个工具包真正的核心资产。

> 完整的评分规则与校准方法论见 [`docs/评分规则与校准方法.md`](docs/评分规则与校准方法.md)。

## 快速开始

### 准备环境

需要 Python 3.11+，只有一个依赖：

```bash
pip install -r requirements.txt
```

模型 API Key 通过环境变量提供（默认使用 DeepSeek）：

```bash
export DEEPSEEK_API_KEY=sk-xxx
```

### 零成本验证

不确定环境和数据切分是否正常时，先用 `--dry-run`：只构建请求载荷、打印 token 估算，**不调用 API、不花钱**。

```bash
python run_all.py --db examples/sample.db --out /tmp/smoke --dry-run
```

### 冒烟测试

用完全合成的样本数据（`examples/sample.db`，3 天，成本约 1 分钱）跑通全流程：

```bash
python run_all.py --db examples/sample.db --out /tmp/smoke --api-key sk-xxx
```

跑完检查 `/tmp/smoke/输出/` 下是否生成四类产出。

### 正式运行

```bash
python run_all.py --db /path/to/chat.db --out /path/to/output --api-key sk-xxx --workers 5
```

`run_all.py` 依次执行三阶段：**清洗切分 → 逐日评分 → 汇总产出**。中断后重跑会自动跳过已完成的天（断点续跑）。只想重跑某一阶段时，用 `--only stage3` 这类参数。

### 使用外部校准 prompt

内置 `pipeline/prompt_template.py` 里的锚点经过泛化处理，便于公开分发。**具体数据集的权威标尺应单独保存为 prompt 文件**，运行时加载：

```bash
python run_all.py --db /path/to/chat.db --out /path/to/output \
  --api-key sk-xxx --prompt-file /path/to/prompt_calibrated.txt
```

详见 [评分规则与标尺](#评分规则与标尺)。

## 工作原理

三个阶段全部可独立运行、可断点续跑，数据流单向，改下游不用重跑上游：

| 阶段 | 脚本 | 做什么 | 产物 |
|------|------|--------|------|
| Stage 1 | `pipeline/clean_split.py` | 清洗噪声、按天切分、折叠刷屏 | `data/days/<日期>.json` |
| Stage 2 | `pipeline/run_analysis.py` | N 并发逐日评分，冻结 prompt，JSON 输出 | `results/<日期>.json` |
| Stage 3 | `pipeline/build_outputs.py` | 汇总成索引表、事件文档、可视化 | `输出/` 下四类文件 |

关键设计（改动会破坏可复现性）：

- **system prompt 全 worker 一字不差**，只有当天对话内容变化
- **`temperature=0` + 关闭思考模式**，压缩随机性
- **强制 JSON 输出**，避免解析歧义
- **每天落盘即完成**，重跑自动跳过

<!-- 流程图：待补。建议画「清洗切分 → 逐日评分 → 汇总产出」三阶段数据流 -->
<!-- ![CLA 工作流程](docs/assets/figures/pipeline-flow.svg) -->

## 输入要求

一份 SQLite 数据库，含 `msg` 表：

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `ts` | INTEGER | 是 | **毫秒**时间戳（写成秒会让日期计算全错） |
| `tstr` | TEXT | 是 | `YYYY-MM-DD HH:MM:SS`，管线按前 10 位切天 |
| `sender` | TEXT | 是 | 发送者昵称，`'0'` 表示系统/未知，会被剔除 |
| `mtype` | TEXT | 是 | 消息类型，`type_1` 普通消息；`type_19` 空消息剔除 |
| `text` | TEXT | 是 | 正文；资源消息为占位符，如 `[图片: hash.png]` |
| `system` | INTEGER | 是 | 1 = 系统消息，剔除 |
| `hasres` / `restype` | INTEGER / TEXT | 否 | 资源标记，用于归一化占位符 |

**换数据源时不要改清洗逻辑，改字段映射**：把其他导出工具的数据灌进这张表即可，细节与转换示例见 [`docs/输入数据格式.md`](docs/输入数据格式.md)。

数据特征会直接影响分析质量，使用前建议确认：

- 图片、语音、视频**内容不可见**，只有占位符。必须在 prompt 中声明这个盲区，否则模型会编造内容
- 系统消息与 `[自动回复]` 是机器生成的，需剔除，否则污染判断
- 刷屏连发（同一人连续发相同文本）会虚增情绪强度，需折叠为 `文本 xN`
- 没有聊天记录的日期**不评分**（可视化中标灰），不要用 1 分或 0 分填补

## 产出物

| 产出 | 路径 | 用途 |
|------|------|------|
| 每日评分 | `results/<日期>.json` | 原始结构化结果，一切产出的数据源 |
| 事件索引表 | `输出/事件索引表.md` / `.csv` | 全量事件表格，可筛选统计（csv 可直接进 Excel） |
| 年度事件文档 | `输出/事件/<年>.md` | 按年连续阅读事件与当日概要 |
| 可视化 | `输出/可视化.html` | 日历热力图 + 大事件时间轴 + 统计面板 |

每日评分 JSON 的核心字段：

```json
{
  "date": "2025-06-15",
  "intensity": 3,
  "polarity": "正",
  "polarity_note": "主导方向与理由，一句话",
  "low_confidence": false,
  "day_summary": "当天概要，一两句话",
  "events": [
    {"time": "09:58", "level": "小", "title": "事件短标题", "desc": "一两句描述"}
  ],
  "evidence": ["支撑评分的关键消息原文引用，最多5条"]
}
```

可视化是单文件、无外部依赖，双击即开：颜色表示极性（正红 / 负绿 / 混合紫 / 中性灰），深浅表示浓度 1-5，黑框表示当天含大事件，悬停可看当日评分、事件与概要。字段细节见 [`docs/产出物说明.md`](docs/产出物说明.md)。

## 评分规则与标尺

每个有聊天记录的日子产出三个独立维度（不是只打一个分）：

| 维度 | 说明 |
|------|------|
| **情绪浓度 1-5** | 这天的情绪有多强烈。面向内敛型对话标定：不以外显情绪强度为主要依据，改看行为信号 |
| **极性** | 正 / 负 / 中 / 混合。混合仅用于正负双方都强且拉扯的日子 |
| **事件等级** | 大 / 小 / 无。与浓度**正交**：平静商量重要事是大事件但浓度可能只有 2；日常拌嘴浓度可能有 3 却只是小事件 |

判读内敛型对话的信号表：

- 负向信号：回复变短变慢、"嗯/哦/好"占比上升、只谈事务不闲聊、深夜异常沉默
- 正向信号：分享的细节变多、颜文字与昵称密度上升、消息节奏变快、主动延续话题
- 反向注意：纯刷屏、表情包连发是低信号，浓度封顶 2 分

**标尺由锚点决定，不由规则文本长度决定。** 规则写得再细，模型没见过某档实例时依然不敢用那一档，所以每个分数档都要配真实确认过的样例。校准流程（怎么挑候选日、怎么让当事人定分、怎么验证）见 [`docs/评分规则与校准方法.md`](docs/评分规则与校准方法.md)。

内置 prompt 的锚点是**泛化版**（去掉具体日期，改为结构示范），目的是让工具包可公开分发。实测两版标尺对分布的影响：

| 对比 | 样本 | 完全一致 | 平均偏差 | 相差 >=2 分 |
|------|------|---------|---------|------------|
| 同一 prompt、同一环境重跑 | 60 天 | 93.3% | 0.067 | 0 天 |
| 同一 prompt、跨环境复跑 | 60 天 | 100.0% | 0.000 | 0 天 |
| **不同 prompt 版本**（泛化锚点 vs 真实锚点） | 1200 天 | 84.9% | 0.151 | 0 天 |

结论：**模型层面很稳，偏移几乎全部来自 prompt 版本**，且是系统性单边偏移而非随机噪声。因此同一批结果必须使用同一版 prompt；趋势与区间判断可以放心用，但事件计数类统计不要混版本。

## 成本与耗时

以 4 年 2 个月、约 30 万条消息、1200 个活跃日的真实项目实测：

| 指标 | 实测值 |
|------|--------|
| 模型 | `deepseek-flash`（1M 上下文，支持 JSON 输出） |
| 输入 token | 约 500 万 |
| 输出 token | 约 50 万 |
| 并发 | 5 |
| 耗时 | 约 20 分钟 |
| **总成本** | **约 6 元人民币** |

结论：**全量重跑很便宜，不要怕重跑**。校准后整段重跑，比局部修补安全得多——局部修补会造成同批数据标准不一致。

> 高峰时段价格约为空闲时段的两倍。其他模型的成本请套用其自身价目。

## 常见坑

1. `ts` 是毫秒，不是秒
2. 图片只有哈希占位符，模型看不到内容，必须在 prompt 里声明这个盲区
3. 系统消息与 `[自动回复]` 必须剔除，否则污染词面与判断
4. 刷屏连发必须折叠，否则虚增消息量与情绪强度
5. 超长日（实测最大 3,880 条）在 1M 上下文下仍可单次处理，无需分窗
6. 改 prompt 后必须用已知答案的日子复跑验证，不要改完直接放全量

## 常见问题

**能换成别的模型吗？**

可以，只要支持 JSON 输出。用 `--model` 与 `--base-url` 指定；但换模型等于换标尺，需要重新校准并用已知答案的日子验证。

**数据会被上传到哪里？**

对话内容会发送给你指定的模型提供方（默认 DeepSeek）。本工具不上传任何数据到第三方服务器，没有遥测。敏感数据请自行评估是否适合走 API。

**为什么我跑出来的分数和别人不一样？**

先确认是不是同一版 prompt。实测同一版 prompt 跨环境复跑 60 天 100% 一致；不一致基本都是 prompt 版本差异带来的系统性偏移。见 [评分规则与标尺](#评分规则与标尺)。

**换成另一份聊天记录要改什么？**

改字段映射（见 [输入要求](#输入要求)），然后用文档里的方法重新校准锚点。规则文本可以沿用，锚点不可沿用。

**图片里的内容分析不了怎么办？**

这是数据源的限制，无法绕过。模型只能靠前后文本推断，信号不足时会置 `low_confidence: true`，建议统计时单独看这类天的占比。

**跑完发现某天分数不对？**

给出具体日期和正确分数，在锚点里补上该案例并整段重跑。单点修补会造成标准不一致，不建议。

## 文档

| 文档 | 内容 |
|------|------|
| [`AGENTS.md`](AGENTS.md) | 给接手 agent 的速查：最短路径、硬约束、验收方式 |
| [`docs/评分规则与校准方法.md`](docs/评分规则与校准方法.md) | 方法论核心：锚点设计、校准流程、防漂移、实测稳定性数据 |
| [`docs/输入数据格式.md`](docs/输入数据格式.md) | 字段规范、换数据源的映射方法、规模参考 |
| [`docs/产出物说明.md`](docs/产出物说明.md) | 四类产出物的字段定义与常见用途 |
| [`config.example.json`](config.example.json) | 参数备忘 |

目录结构：

```
run_all.py                  一键串起三阶段
pipeline/
  config.py                 参数解析（各阶段共用）
  clean_split.py            Stage 1 清洗 + 按天切分
  prompt_template.py        Stage 2 评分规则（改这里 = 改标准）
  run_analysis.py           Stage 2 逐日评分（N 并发 + 断点）
  build_outputs.py          Stage 3 汇总产出
examples/
  sample.db                 合成样本数据（可公开分发）
  make_sample_db.py         样本生成脚本
docs/                       三份文档
```

## Star 历史

<a href="https://www.star-history.com/#rainanow/CLA&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=rainanow/CLA&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=rainanow/CLA&type=Date" />
    <img alt="CLA Star 历史" src="https://api.star-history.com/svg?repos=rainanow/CLA&type=Date" />
  </picture>
</a>

## 免责与隐私

本项目用于分析**你自己拥有或已获授权**的聊天记录。聊天记录通常包含第三方（对话另一方及被提及的人）的隐私信息：

- 请确认你对数据有处置权，并注意他人隐私与当地法律要求
- 分析过程会把对话内容发送给所选模型提供方，敏感数据请自行评估
- 工具包本身不含任何真实聊天数据，`examples/sample.db` 为完全合成的样本
- 本工具输出的是主观评分，不构成心理学或医学判断

## 贡献

欢迎提 Issue 与 PR。改动评分规则时，请一并说明验证方式；改动清洗逻辑时，请说明对已有结果的影响。

<!-- 开发环境与检查流程：待补（如 CONTRIBUTING.md） -->

## License

[MIT](LICENSE)

<!-- 第三方声明：待补（当前仅依赖 httpx） -->
