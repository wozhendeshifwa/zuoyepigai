"""学习通作业批改的统一入口。

    python scripts/cx.py check                     跑守卫与调分的单元测试
    python scripts/cx.py roster                    谁真交了作业（以附件为准）
    python scripts/cx.py export   -o out/tpl.xls   下载当前成绩模板
    python scripts/cx.py emit     --scores s.json --template t.xls -o out/导入.xls
    python scripts/cx.py score    202415000233 80  给单个学生改分
    python scripts/cx.py back     out/未交名单.csv "批改失误"

设计约束：emit 在写文件之前必须让「行数 == 提交人数」这个断言通过，
因为学习通导入是按行全量写，多一行就等于给没交作业的人写了个分。
"""
import argparse
import csv
import json
import os
import sys
import time

import config
import emit
import roster as roster_mod
import template as template_mod
from client import Client, mark_list_url, mark_url, MOOC2


def cmd_check(_args):
    import unittest
    here = os.path.dirname(os.path.abspath(__file__))
    suite = unittest.defaultTestLoader.discover(os.path.join(here, '..', 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def cmd_roster(args):
    client = Client()
    rows, submitted = roster_mod.collect(
        client, args.work_id or config.DEFAULT_WORK_ID,
        check_attachment=not args.no_attachment_check)
    print(f'\n共 {len(rows)} 人，真交了的 {len(submitted)} 人')
    for r in submitted:
        print(f"  {r['stuNo']}  {r['name']:<8} {r['submitTime']}")
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump({'all': rows, 'submitted': submitted}, f,
                      ensure_ascii=False, indent=1)
        print(f'\n写入 {args.json}')
    return 0


def cmd_export(args):
    client = Client()
    out = args.out or os.path.join(config.OUT, '成绩模板.xls')
    path = client.download_grade_template(args.task_id or config.DEFAULT_TASK_ID, out)
    print(f'已导出 {path}  {os.path.getsize(path)}B')
    return 0


def cmd_emit(args):
    scores = json.load(open(args.scores, encoding='utf-8'))
    score_map = {str(s['stuNo']).strip(): float(s.get('final', s.get('total')))
                 for s in scores}
    tpl = template_mod.load_template(args.template)
    print(f'模板：{tpl["sheet"]}  学生 {len(tpl["rows"])} 人')
    print(f'给分：{len(score_map)} 人')

    rows, report = emit.select_rows(tpl['rows'], score_map,
                                    args.floor, args.cap)
    print(f"守卫通过：文件 {report['rows']} 行 = 提交 {report['submitters']} 人"
          f"（模板里其余 {report['dropped']} 人不进文件）")

    out = args.out
    emit.write_xls(rows, tpl['headers'], tpl['score_index'], score_map, out,
                   tpl['sheet'], title_rows=tpl['title_rows'])
    print(f'写出 {out}')
    for no in sorted(score_map):
        print(f'  {no} -> {score_map[no]:g}')
    return 0


def _answer_id_of(client, work_id, stu_no):
    html = client.get_text(mark_list_url(work_id))
    for r in roster_mod.parse_mark_list(html):
        if r['stuNo'] == stu_no:
            return r['answerId']
    return ''


def cmd_score(args):
    client = Client()
    work_id = args.work_id or config.DEFAULT_WORK_ID
    answer_id = _answer_id_of(client, work_id, args.stu_no)
    if not answer_id:
        raise SystemExit(f'批阅列表里找不到 {args.stu_no}')
    score = float(args.score)
    if not (config.SCORE_FLOOR <= score <= config.SCORE_CAP):
        raise SystemExit(f'分数必须落在 {config.SCORE_FLOOR:g}-{config.SCORE_CAP:g}')
    url = (f'{MOOC2}/mooc2-ans/work/markscore?markScore={args.score}'
           f'&markAnswerIds={answer_id}&markType=0')
    status, raw, _ = client.post_form(url, {
        'courseid': config.COURSE_ID, 'clazzid': config.CLAZZ_ID,
        'cpi': config.CPI, 'workid': work_id, 'answerIds': answer_id,
        'type': '0', 'score': str(args.score),
    }, referer=mark_url(args.task_id or config.DEFAULT_TASK_ID))
    print(f'{args.stu_no} answerId={answer_id} -> {status} {raw.decode("utf-8", "ignore")[:200]}')
    return 0


def cmd_back(args):
    client = Client()
    work_id = args.work_id or config.DEFAULT_WORK_ID
    rows = list(csv.DictReader(open(args.csv, encoding='utf-8-sig')))
    ids = [r['answerId'].strip() for r in rows if r.get('answerId', '').strip()]
    print(f'待打回 {len(ids)} 人，理由={args.reason!r}')
    if not args.yes:
        raise SystemExit('这是写操作，加 --yes 确认')
    for start in range(0, len(ids), 30):
        part = ids[start:start + 30]
        url = f'{MOOC2}/mooc2-ans/work/batchBack?backAnswerIdsStr=' + ','.join(part)
        status, raw, _ = client.post_form(url, {
            'courseid': config.COURSE_ID, 'clazzid': config.CLAZZ_ID,
            'cpi': config.CPI, 'workid': work_id, 'answerIds': ','.join(part),
            'jobid': '', 'reason': args.reason, 'extraTime': '',
        }, referer=mark_url(args.task_id or config.DEFAULT_TASK_ID))
        print(f'  {start + 1}-{start + len(part)}: {status} {raw.decode("utf-8", "ignore")[:160]}')
        time.sleep(1.5)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='cx.py', description='学习通作业批改')
    sub = ap.add_subparsers(dest='cmd', required=True)

    sub.add_parser('check').set_defaults(fn=cmd_check)

    p = sub.add_parser('roster', help='谁真交了作业')
    p.add_argument('--work-id')
    p.add_argument('--no-attachment-check', action='store_true')
    p.add_argument('--json')
    p.set_defaults(fn=cmd_roster)

    p = sub.add_parser('export', help='下载当前成绩模板')
    p.add_argument('--task-id')
    p.add_argument('-o', '--out')
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser('emit', help='生成导入文件（带行数守卫）')
    p.add_argument('--scores', required=True)
    p.add_argument('--template', required=True)
    p.add_argument('-o', '--out', required=True)
    p.add_argument('--floor', type=float, default=config.SCORE_FLOOR)
    p.add_argument('--cap', type=float, default=config.SCORE_CAP)
    p.set_defaults(fn=cmd_emit)

    p = sub.add_parser('score', help='给单个学生改分')
    p.add_argument('stu_no')
    p.add_argument('score', type=float)
    p.add_argument('--task-id')
    p.add_argument('--work-id')
    p.set_defaults(fn=cmd_score)

    p = sub.add_parser('back', help='批量打回（写操作，需 --yes）')
    p.add_argument('csv')
    p.add_argument('reason')
    p.add_argument('--yes', action='store_true')
    p.add_argument('--task-id')
    p.add_argument('--work-id')
    p.set_defaults(fn=cmd_back)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
