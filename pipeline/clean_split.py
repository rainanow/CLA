#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1: 清洗 + 按天切分。

输入:  SQLite 数据库（msg 表）
输出:  <out>/data/days/<日期>.json   每天清洗后的消息
       <out>/data/tasks.json         任务清单

清洗规则:
  - 剔除 system=1 / sender='0' / 空文本 / type_19
  - [图片: hash] -> [图] ; [视频: 路径] -> [视频] ; [文件: 路径] -> [文件: 名]
  - 剔除 [自动回复] 消息（机器生成，非本人发言）
  - 同一人连续发相同文本 >= 5 条 -> 折叠为 "文本 xN"

换数据源时注意 ts 字段必须是毫秒时间戳。
"""
import sqlite3
import json
import re
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import get_config, paths

SPAM_THRESHOLD = 5
MESSAGE_TABLE = 'msg'


def clean_text(text, restype):
    if text is None:
        return None
    t = text.strip()
    if not t:
        return None
    if t.startswith('[自动回复]'):
        return None
    if restype == 'image' or t.startswith('[图片:'):
        return '[图]'
    if restype == 'video' or t.startswith('[视频:'):
        return '[视频]'
    if restype == 'file':
        m = re.match(r'\[文件: (.+?)\]', t)
        return f'[文件: {m.group(1)}]' if m else '[文件]'
    return t


def run(db_path, out_dir):
    p = paths(out_dir)
    os.makedirs(p['days'], exist_ok=True)

    db = sqlite3.connect(db_path)
    cur = db.cursor()
    cur.execute(f"""
        SELECT tstr, sender, text, mtype, restype FROM {MESSAGE_TABLE}
        WHERE system=0 AND sender!='0' AND (text IS NOT NULL AND TRIM(text)!='')
        ORDER BY ts
    """)

    days = defaultdict(list)
    n_total = n_kept = 0
    for tstr, sender, text, mtype, restype in cur.fetchall():
        n_total += 1
        if mtype == 'type_19':
            continue
        t = clean_text(text, restype)
        if not t:
            continue
        n_kept += 1
        days[tstr[:10]].append({'hm': tstr[11:16], 's': sender, 't': t})

    # 折叠刷屏
    n_folded = 0
    for day, msgs in days.items():
        out, i = [], 0
        while i < len(msgs):
            j = i
            while (j + 1 < len(msgs) and msgs[j + 1]['s'] == msgs[i]['s']
                   and msgs[j + 1]['t'] == msgs[i]['t']):
                j += 1
            run_len = j - i + 1
            if run_len >= SPAM_THRESHOLD:
                out.append({'hm': msgs[i]['hm'], 's': msgs[i]['s'],
                            't': f"{msgs[i]['t']} x{run_len}"})
                n_folded += run_len
            else:
                out.extend(msgs[i:j + 1])
            i = j + 1
        days[day] = out

    tasks = []
    for day in sorted(days):
        with open(os.path.join(p['days'], day + '.json'), 'w', encoding='utf-8') as f:
            json.dump(days[day], f, ensure_ascii=False)
        tasks.append({'day': day, 'n': len(days[day])})

    with open(p['tasks'], 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=0)

    print(f'[Stage1] 原始 {n_total} 条 -> 保留 {n_kept} 条，折叠刷屏 {n_folded} 条')
    print(f'[Stage1] {len(tasks)} 天，最大日 {max(tasks, key=lambda x: x["n"])}')


if __name__ == '__main__':
    args = get_config('Stage1 清洗切分')
    run(args.db, args.out)
