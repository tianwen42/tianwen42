# -*- coding: utf-8 -*-
"""ONE·一个 每日「一张图 + 一句话」抓取，按日期写入 one.txt

数据文件 one.txt：每行一条记录，制表符分隔，无表头
    20261016 <TAB> https://image.wufazhuce.com/xxx <TAB> 我不想成为任何东西的象征。我只做我自己。

设计要点
1. 日期以页面自带日期为准（VOL.xxx 16 Oct 2026），不依赖运行机器的时区，
   因此在 GitHub Actions 的 UTC 环境里也能写对北京时间的日期。
2. 幂等 upsert：同一天重复运行不会产生重复行；当天内容若变化会被覆盖。
3. 抓取/解析失败直接非 0 退出，让 Action 的失败可见，且不写入脏数据。

用法
    python update.py             # 抓取并写入 one.txt
    python update.py --dry-run   # 只打印抓取结果，不写文件
"""

import argparse
import datetime
import re
import sys
import time
from pathlib import Path

import requests
from lxml import etree

# ==================== 配置（集中在此处） ====================
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / 'one.txt'          # 输出数据文件
URL = 'https://wufazhuce.com/'            # 数据源：ONE 首页，第一个轮播项即当天
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
TIMEOUT = 20                              # 单次请求超时（秒）
RETRY_TIMES = 3                           # 请求重试次数
RETRY_WAIT = 5                            # 重试间隔（秒）
TIMEZONE_HOURS = 8                        # 页面取不到日期时的兜底时区（北京时间）
SEP = '\t'                                # 字段分隔符
# ==========================================================

MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
          'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
DATE_RE = re.compile(r'(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})')


def clean(text):
    """压缩空白、去掉制表符，保证一条记录只占一行。"""
    return ' '.join(str(text or '').replace(SEP, ' ').split())


def today_bj():
    """北京时间当天，形如 20261016。"""
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=TIMEZONE_HOURS)
    return now.strftime('%Y%m%d')


def parse_page_date(text):
    """从 'VOL.5123 16 Oct 2026 ...' 中解析出 20261016；解析不到返回 None。"""
    m = DATE_RE.search(text or '')
    if not m:
        return None
    day, mon, year = m.group(1), m.group(2)[:3].lower(), m.group(3)
    if mon not in MONTHS:
        return None
    try:
        return datetime.date(int(year), MONTHS[mon], int(day)).strftime('%Y%m%d')
    except ValueError:
        return None


def fetch_html(url):
    """抓取页面，失败按 RETRY_TIMES 重试。"""
    headers = {'User-Agent': UA, 'Referer': 'https://wufazhuce.com/'}
    last_err = None
    for i in range(1, RETRY_TIMES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            if not resp.encoding:
                resp.encoding = 'utf-8'
            return resp.text
        except Exception as ex:                      # noqa: BLE001
            last_err = ex
            print('[warn] 第 %d/%d 次请求失败: %s' % (i, RETRY_TIMES, ex))
            if i < RETRY_TIMES:
                time.sleep(RETRY_WAIT)
    raise RuntimeError('请求 %s 失败: %s' % (url, last_err))


def parse_today(html):
    """解析出当天记录，返回 (日期, 图片URL, 文案)。"""
    tree = etree.HTML(html)
    if tree is None:
        raise RuntimeError('页面解析失败，HTML 结构异常')

    # 第一个轮播项 = 当天；取不到就退回整页（兼容老的页面结构）
    items = tree.xpath("//*[contains(@class,'carousel-inner')]/*[contains(@class,'item')]")
    node = items[0] if items else tree

    imgs = node.xpath(".//img/@src")
    cita_nodes = (node.xpath(".//*[@class='fp-one-cita']")
                  or node.xpath(".//*[contains(@class,'fp-one-cita')]"))
    wrap_nodes = (node.xpath(".//*[contains(@class,'fp-one-cita-wrapper')]")
                  or node.xpath(".//*[contains(@class,'fp-one')]"))

    img = clean(imgs[0]) if imgs else ''
    title = clean(' '.join(t for e in cita_nodes for t in e.itertext()))
    date_text = clean(' '.join(t for e in wrap_nodes for t in e.itertext()))

    if not img or not title:
        raise RuntimeError('未解析到图片或文案，页面结构可能已改版')

    date = parse_page_date(date_text)
    if not date:
        date = today_bj()
        print('[warn] 页面未取到日期，改用北京时间当天 %s' % date)
    return date, img, title


def read_rows(path):
    """读取 one.txt，返回 [(日期, 图片, 文案)]，保持原有顺序。"""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        parts = line.split(SEP)
        rows.append((parts[0].strip(),
                     parts[1].strip() if len(parts) > 1 else '',
                     clean(SEP.join(parts[2:])) if len(parts) > 2 else ''))
    return rows


def save_rows(path, rows):
    """整文件写回：UTF-8 + LF，按日期升序。"""
    text = ''.join('%s%s%s%s%s\n' % (d, SEP, i, SEP, t) for d, i, t in rows)
    path.write_text(text, encoding='utf-8', newline='\n')


def upsert(rows, row):
    """按日期写入：同日期只保留本条，其余记录保序，最后按日期升序排列。"""
    date = row[0]
    old = [r for r in rows if r[0] == date]
    rest = [r for r in rows if r[0] != date]
    if old == [row]:
        return rows, '当天记录已是最新，无需写入'
    action = '覆盖当天 %d 条旧记录' % len(old) if old else '新增'
    return sorted(rest + [row], key=lambda r: r[0]), action


def main():
    parser = argparse.ArgumentParser(description='抓取 ONE 每日一句并写入 one.txt')
    parser.add_argument('--dry-run', action='store_true', help='只打印抓取结果，不写文件')
    args = parser.parse_args()

    try:
        html = fetch_html(URL)
        date, img, title = parse_today(html)
    except Exception as ex:                          # noqa: BLE001
        print('[error] 抓取/解析失败: %s' % ex)
        return 1

    print('日期: %s' % date)
    print('图片: %s' % img)
    print('文案: %s' % title)

    rows = read_rows(DATA_FILE)
    merged, action = upsert(rows, (date, img, title))
    print('动作: %s' % action)

    if action.startswith('当天记录已是最新'):
        return 0
    if args.dry_run:
        print('[dry-run] 未写入 %s' % DATA_FILE)
        return 0

    save_rows(DATA_FILE, merged)
    print('已写入 %s，共 %d 条记录' % (DATA_FILE, len(merged)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
