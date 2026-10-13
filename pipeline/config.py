# -*- coding: utf-8 -*-
"""统一参数解析。所有阶段共用，支持 CLI 参数与环境变量。"""
import argparse
import os


def get_config(description, argv=None):
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument('--db', help='输入 SQLite 数据库路径')
    ap.add_argument('--out', help='输出根目录（结构: data/ results/ 输出/）')
    ap.add_argument('--api-key', default=os.environ.get('DEEPSEEK_API_KEY'),
                    help='模型 API Key，也可用环境变量 DEEPSEEK_API_KEY')
    ap.add_argument('--base-url', default='https://api.deepseek.com',
                    help='API Base URL')
    ap.add_argument('--model', default='deepseek-flash')
    ap.add_argument('--workers', type=int, default=5, help='并发窗口数')
    ap.add_argument('--days', help='仅处理指定日期，逗号分隔')
    ap.add_argument('--all', action='store_true', help='处理全部天')
    ap.add_argument('--prompt-file',
                    help='外部 system prompt 文本文件；不指定则用内置 prompt_template.py。'
                         '用于加载已校准的 prompt（同一套代码跑不同标尺）')
    ap.add_argument('--dry-run', action='store_true',
                    help='只构建请求并打印载荷统计，不调用 API（零成本验证）')
    return ap.parse_args(argv)


def paths(out_dir):
    """返回各阶段使用的标准路径。"""
    base = os.path.abspath(out_dir)
    return {
        'base': base,
        'days': os.path.join(base, 'data', 'days'),
        'tasks': os.path.join(base, 'data', 'tasks.json'),
        'results': os.path.join(base, 'results'),
        'output': os.path.join(base, '输出'),
    }
