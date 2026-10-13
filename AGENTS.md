# AGENTS.md — 给接手 agent 的速查

本目录是一个可独立运行的工具包，用于对双人长期聊天记录做逐日情绪/事件分析。**先读 `README.md`，本文件只给最短路径与硬约束。**

## 最短路径

```bash
pip install -r requirements.txt
export DEEPSEEK_API_KEY=sk-xxx
python run_all.py --db examples/sample.db --out /tmp/smoke --dry-run   # 零成本验证，不花钱
python run_all.py --db examples/sample.db --out /tmp/smoke             # 冒烟测试，约 1 分钱
python run_all.py --db <真实库> --out <输出目录> --workers 5 \
  --prompt-file <校准版prompt.txt>                                     # 正式运行
```

## 硬约束（违反会出错或污染结果）

1. 输入必须是 SQLite，含 `msg` 表；`ts` 是**毫秒**时间戳。字段不一致时参考 `docs/输入数据格式.md` 做映射，不要直接改清洗逻辑。
2. 评分规则只改 `pipeline/prompt_template.py` 一处，**不要**在调用处拼规则文本。
3. 换数据集时必须重做锚点校准，流程见 `docs/评分规则与校准方法.md`。规则文本可沿用，锚点不可沿用。
4. **prompt 版本即标尺**：默认内置模板的锚点是泛化版；具体数据集应有一份独立的校准版 prompt 文件，用 `--prompt-file` 加载。**同一批结果必须同版本**，不要混用不同 prompt 版本的输出做统计。改动 prompt 后必须复跑已知答案的日子验证。
5. 零成本自检用 `--dry-run`：构建载荷但不调用 API，验证 prompt 加载与切分结果是否正确。用户预算有限时优先用这个。
6. 模型需支持 JSON 输出；默认 `deepseek-flash`，请求体已设 `temperature=0` 与关闭思考模式，不要改这两项（会破坏可复现性）。
7. 每完成一天落盘一个 `results/<日期>.json`，重跑自动跳过已完成的天。**不要手动删除 results 目录**，除非你有意整体重跑。

## 判断动作前先暴露，不要静默决策

- 改评分标尺（prompt 文件）属于"改标准"，必须让用户确认
- 分数与用户手感冲突时，先展示该日的证据与理由，由用户裁定，不要自行调分
- 全量重跑前先报预估耗时与成本
- 不要擅自动用用户的 API 额度；能零成本验证就先零成本验证

## 验收方式

- 冒烟测试：`examples/sample.db` 跑通，产出 4 类文件（结果 JSON / 索引表 / 年度文档 / 可视化 HTML）
- 标尺验证：用 3-10 个已知答案的日子复跑，分数应落位
