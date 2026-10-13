#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键运行：清洗切分 -> 逐日评分 -> 汇总产出。

用法:
  python run_all.py --db examples/sample.db --out /tmp/smoke --api-key sk-xxx
  python run_all.py --db /data/chat.db  --out /data/out  --workers 5
  python run_all.py --out /data/out --only stage3        # 只重跑汇总

环境变量: DEEPSEEK_API_KEY
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pipeline'))

from config import get_config
from clean_split import run as stage1
from run_analysis import run as stage2
from build_outputs import run as stage3


def main():
    ap = argparse.ArgumentParser(description='chatlog 分析工具包 - 一键运行')
    ap.add_argument('--db')
    ap.add_argument('--out', required=True)
    ap.add_argument('--api-key', default=os.environ.get('DEEPSEEK_API_KEY'))
    ap.add_argument('--base-url', default='https://api.deepseek.com')
    ap.add_argument('--model', default='deepseek-flash')
    ap.add_argument('--workers', type=int, default=5)
    ap.add_argument('--only', choices=['stage1', 'stage2', 'stage3'],
                    help='只运行指定阶段（默认全部）')
    ap.add_argument('--prompt-file',
                    help='外部 system prompt 文本文件；不指定则用内置 prompt_template.py')
    ap.add_argument('--dry-run', action='store_true',
                    help='阶段2 只构建载荷不调用 API（零成本验证）')
    args = ap.parse_args()

    # 统一转成 config 命名空间，供各阶段复用
    cfg = argparse.Namespace(db=args.db, out=args.out, api_key=args.api_key,
                             base_url=args.base_url, model=args.model,
                             workers=args.workers, days=None, all=True,
                             prompt_file=args.prompt_file, dry_run=args.dry_run)

    stages = [args.only] if args.only else ['stage1', 'stage2', 'stage3']
    if 'stage1' in stages:
        if not args.db:
            raise SystemExit('Stage1 需要 --db')
        stage1(args.db, args.out)
    if 'stage2' in stages:
        if not args.api_key and not args.dry_run:
            raise SystemExit('Stage2 需要 --api-key 或环境变量 DEEPSEEK_API_KEY')
        stage2(cfg)
    if 'stage3' in stages:
        stage3(cfg)

    print('\n完成。产出目录结构：')
    print(f'  {args.out}/data/days/      清洗后的每日数据')
    print(f'  {args.out}/results/        每日评分 JSON')
    print(f'  {args.out}/输出/           索引表 / 事件文档 / 可视化.html')


if __name__ == '__main__':
    main()
