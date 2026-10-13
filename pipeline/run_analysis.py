#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 2: 逐日评分（N 并发 + 断点续跑）。

用法:
  python run_analysis.py --db x.db --out <目录> --days 2025-01-01,2025-01-02
  python run_analysis.py --db x.db --out <目录> --all --workers 5

设计要点（不要改）:
  - system prompt 来自 prompt_template.py，所有 worker 一字不差
  - temperature=0、关闭思考模式 -> 压随机性，保证可复现
  - response_format=json_object -> 强制结构化输出
  - 每天落盘 results/<日期>.json，存在即跳过（断点续跑）
  - 失败重试 3 次，指数退避
"""
import asyncio
import json
import os
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import get_config, paths
from prompt_template import SYSTEM_PROMPT as DEFAULT_PROMPT, build_user_prompt

MAX_RETRY = 3
TIMEOUT_SEC = 300


def load_system_prompt(prompt_file=None):
    """system prompt 来源：外部文件优先，否则用内置模板。
    外部文件为纯文本（整份内容即 system prompt）。"""
    if prompt_file:
        with open(prompt_file, encoding='utf-8') as f:
            text = f.read().strip()
        if not text:
            raise SystemExit(f'prompt 文件为空: {prompt_file}')
        print(f'[Stage2] 使用外部 prompt: {prompt_file} ({len(text)} 字符)')
        return text
    return DEFAULT_PROMPT


async def analyze_day(client, day, sem, stats, cfg, p, system_prompt):
    out_path = os.path.join(p['results'], day + '.json')
    if os.path.exists(out_path):
        stats['skipped'] += 1
        return
    msgs = json.load(open(os.path.join(p['days'], day + '.json'), encoding='utf-8'))
    body = {
        'model': cfg.model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': build_user_prompt(day, msgs)},
        ],
        'temperature': 0,
        'response_format': {'type': 'json_object'},
        'thinking': {'type': 'disabled'},
    }
    async with sem:
        for attempt in range(MAX_RETRY):
            try:
                t0 = time.time()
                r = await client.post(
                    f'{cfg.base_url}/chat/completions', json=body,
                    headers={'Authorization': f'Bearer {cfg.api_key}'},
                    timeout=TIMEOUT_SEC)
                r.raise_for_status()
                data = r.json()
                usage = data['usage']
                result = json.loads(data['choices'][0]['message']['content'])
                result['_usage'] = {
                    'in': usage['prompt_tokens'],
                    'out': usage['completion_tokens'],
                    'cache_hit': usage.get('prompt_cache_hit_tokens', 0),
                    'sec': round(time.time() - t0, 1),
                }
                result['_day_msgs'] = len(msgs)
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=1)
                stats['done'] += 1
                stats['tokens_in'] += usage['prompt_tokens']
                stats['tokens_out'] += usage['completion_tokens']
                print(f"[{day}] 浓度{result.get('intensity')} {result.get('polarity')} "
                      f"事件{len(result.get('events', []))} in={usage['prompt_tokens']} "
                      f"out={usage['completion_tokens']} {result['_usage']['sec']}s")
                return
            except Exception as e:
                if attempt < MAX_RETRY - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    stats['failed'] += 1
                    print(f'[{day}] 失败: {e}', file=sys.stderr)


async def run_async(cfg, p):
    if cfg.all:
        tasks = json.load(open(p['tasks'], encoding='utf-8'))
        days = [t['day'] for t in tasks
                if not os.path.exists(os.path.join(p['results'], t['day'] + '.json'))]
    elif cfg.days:
        days = cfg.days.split(',')
    else:
        raise SystemExit('需指定 --all 或 --days')

    os.makedirs(p['results'], exist_ok=True)
    system_prompt = load_system_prompt(getattr(cfg, 'prompt_file', None))

    if getattr(cfg, 'dry_run', False):
        print('[Stage2] dry-run 模式：只构建载荷，不调用 API')
        for d in days[:3]:
            msgs = json.load(open(os.path.join(p['days'], d + '.json'), encoding='utf-8'))
            up = build_user_prompt(d, msgs)
            print(f'  {d}: {len(msgs)} 条消息, system {len(system_prompt)} 字符, '
                  f'user {len(up)} 字符, 约 {(len(system_prompt)+len(up))//3} token')
        print(f'  (共 {len(days)} 天待处理)')
        return

    sem = asyncio.Semaphore(cfg.workers)
    stats = {'done': 0, 'failed': 0, 'skipped': 0, 'tokens_in': 0, 'tokens_out': 0}
    print(f'[Stage2] {len(days)} 天待处理，并发 {cfg.workers}，模型 {cfg.model}')
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*[analyze_day(client, d, sem, stats, cfg, p, system_prompt)
                               for d in days])

    print(f"\n[Stage2] 完成 {stats['done']} 失败 {stats['failed']} 跳过 {stats['skipped']} "
          f"token: in={stats['tokens_in']} out={stats['tokens_out']}")
    # 按 deepseek-flash 空闲时段价格粗估: 输入未命中 1 元/M, 输出 4 元/M
    cost = stats['tokens_in'] / 1e6 * 1 + stats['tokens_out'] / 1e6 * 4
    print(f'[Stage2] 成本估算(空闲时段): ¥{cost:.2f}  '
          f'（高峰时段价格翻倍；其他模型请自行套用其价目）')


def run(cfg):
    p = paths(cfg.out)
    asyncio.run(run_async(cfg, p))


if __name__ == '__main__':
    cfg = get_config('Stage2 逐日评分')
    if not cfg.db and not cfg.out:
        raise SystemExit('需指定 --out；--db 仅 Stage1 使用')
    run(cfg)
