#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成完全合成的样本数据（examples/sample.db），用于冒烟测试。
样本不含任何真实聊天内容，可公开分发。

表结构与真实导出一致（msg 表，ts 为毫秒时间戳）。
样本包含 3 天：
  2024-01-05  低浓度日常（少量图片与晚安）—— 预期低分
  2024-01-06  常规闲聊 —— 预期 2 分
  2024-01-07  含冲突与和解 —— 预期高分
"""
import sqlite3
import os
from datetime import datetime

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample.db')

SCHEMA = """
CREATE TABLE msg (
    id TEXT, seq INTEGER, ts INTEGER, tstr TEXT, sender TEXT,
    mtype TEXT, text TEXT, recalled INTEGER, system INTEGER,
    hasres INTEGER, restype TEXT
);
"""

# (日期, 时间, 发送者, 文本, 类型, 是否资源, 资源类型)
ROWS = [
    # 2024-01-05 低浓度：只有图片和晚安
    ('2024-01-05', '12:30', '小明', '[图片: aaa.png]', 'type_1', 1, 'image'),
    ('2024-01-05', '12:31', '小红', '[图]', 'type_1', 1, 'image'),
    ('2024-01-05', '23:20', '小明', '晚安', 'type_1', 0, ''),
    # 2024-01-06 常规闲聊
    ('2024-01-06', '08:10', '小红', '早', 'type_1', 0, ''),
    ('2024-01-06', '08:12', '小明', '早呀', 'type_1', 0, ''),
    ('2024-01-06', '08:15', '小红', '今天好冷', 'type_1', 0, ''),
    ('2024-01-06', '12:40', '小明', '[图]', 'type_1', 1, 'image'),
    ('2024-01-06', '12:41', '小明', '食堂新出的', 'type_1', 0, ''),
    ('2024-01-06', '12:45', '小红', '看着还行', 'type_1', 0, ''),
    ('2024-01-06', '19:02', '小明', '在哪', 'type_1', 0, ''),
    ('2024-01-06', '19:03', '小红', '图书馆', 'type_1', 0, ''),
    ('2024-01-06', '21:30', '小红', '回去啦', 'type_1', 0, ''),
    ('2024-01-06', '23:00', '小明', '晚安', 'type_1', 0, ''),
    # 2024-01-07 冲突与和解
    ('2024-01-07', '09:20', '小红', '你昨天怎么没回我', 'type_1', 0, ''),
    ('2024-01-07', '09:41', '小明', '在忙', 'type_1', 0, ''),
    ('2024-01-07', '09:42', '小红', '哦', 'type_1', 0, ''),
    ('2024-01-07', '09:43', '小红', '算了', 'type_1', 0, ''),
    ('2024-01-07', '11:20', '小明', '你生气了', 'type_1', 0, ''),
    ('2024-01-07', '11:35', '小红', '没有', 'type_1', 0, ''),
    ('2024-01-07', '15:10', '小明', '对不起，昨天确实没顾上', 'type_1', 0, ''),
    ('2024-01-07', '15:12', '小红', '我不是气这个', 'type_1', 0, ''),
    ('2024-01-07', '15:20', '小红', '我是觉得你什么都不跟我说', 'type_1', 0, ''),
    ('2024-01-07', '15:40', '小明', '以后有事我先跟你说一声', 'type_1', 0, ''),
    ('2024-01-07', '16:05', '小红', '好', 'type_1', 0, ''),
    ('2024-01-07', '16:06', '小红', '我也有不对的地方', 'type_1', 0, ''),
    ('2024-01-07', '20:30', '小明', '晚上一起看那个电影吧', 'type_1', 0, ''),
    ('2024-01-07', '20:35', '小红', '好啊', 'type_1', 0, ''),
    ('2024-01-07', '23:40', '小明', '晚安', 'type_1', 0, ''),
    ('2024-01-07', '23:41', '小红', '晚安', 'type_1', 0, ''),
]


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.executescript(SCHEMA)
    for i, (d, hm, sender, text, mtype, hasres, restype) in enumerate(ROWS):
        tstr = f'{d} {hm}:00'
        ts = int(datetime.strptime(tstr, '%Y-%m-%d %H:%M:%S').timestamp() * 1000)
        db.execute(
            'INSERT INTO msg (id, seq, ts, tstr, sender, mtype, text, recalled, '
            'system, hasres, restype) VALUES (?,?,?,?,?,?,?,0,0,?,?)',
            (f's{i}', i, ts, tstr, sender, mtype, text, hasres, restype))
    # 混入一条系统消息与一条自动回复，验证清洗会剔除
    tstr = '2024-01-06 10:00:00'
    ts = int(datetime.strptime(tstr, '%Y-%m-%d %H:%M:%S').timestamp() * 1000)
    db.execute('INSERT INTO msg VALUES (?,?,?,?,?,?,?,0,1,0,"")',
               ('sys1', 999, ts, tstr, '0', 'type_1', '[12]'))
    db.execute('INSERT INTO msg VALUES (?,?,?,?,?,?,?,0,0,0,"")',
               ('auto1', 1000, ts, tstr, '小明', 'type_1',
                '[自动回复]对不起，没能及时回你消息，不过我看到会马上回复的'))
    db.commit()
    n = db.execute('SELECT COUNT(*) FROM msg').fetchone()[0]
    print(f'已生成 {OUT}，共 {n} 条消息（含 1 条系统消息、1 条自动回复用于验证清洗）')


if __name__ == '__main__':
    main()
