"""学习通作业批改的统一入口。

    cx.py check                                   跑守卫与调分的单元测试
    cx.py roster  [--json f]                      谁真交了作业（以附件为准）
    cx.py export  [-o tpl.xls]                    下载当前成绩模板
    cx.py collect [--sub ch3]                     下载作答并渲染页图
    cx.py grade   --stu-no X [--img-dir d]        判一份（写 research_src/grade/X.json）
    cx.py review  [--sub ch3] [-o 复核表.xlsx]    生成复核表 + _final.json
    cx.py emit    --scores s.json --template t.xls -o 导入.xls
    cx.py score   <学号> <分数>                    给单个学生改分
    cx.py back    <csv> <理由> --yes               批量打回（可撤销）
    cx.py inspect xls|grep|slice|crop|pdf ...     只读排查工具

守卫：emit 写文件前必须让「行数 == 提交人数」通过。学习通导入是按行全量写，
多一行就等于给没交作业的人写了个分——2026-10-17 就是这样写错 87 人的。
"""
import argparse
import glob
import json
import os
import sys
import time

import calibrate
import collect as collect_mod
import config
import emit
import judge
import review as review_mod
import roster as roster_mod
import template as template_mod
import toolbox as toolbox_mod
from client import Client, MOOC2, mark_list_url, mark_url


def _work_id(args):
    return getattr(args, 'work_id', None) or config.DEFAULT_WORK_ID


def _task_id(args):
    return getattr(args, 'task_id', None) or config.DEFAULT_TASK_ID


def cmd_check(_args):
    import unittest
    here = os.path.dirname(os.path.abspath(__file__))
    suite = unittest.defaultTestLoader.discover(
        os.path.join(here, '..', 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def cmd_roster(args):
    client = Client()
    rows, submitted = roster_mod.collect(
        client, _work_id(args), check_attachment=not args.no_attachment_check)
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
    path = client.download_grade_template(_task_id(args), out)
    print(f'已导出 {path}  {os.path.getsize(path)}B')
    return 0


def cmd_collect(args):
    out_dir = args.sub if os.path.isabs(args.sub) else os.path.join(
        config.RESEARCH, 'sub', args.sub)
    client = Client()
    rows, submitted, done = collect_mod.collect(
        client, _work_id(args), out_dir, scale=args.scale)
    print(f'\n提交 {len(submitted)} 人，成功下载 {len(done)} 份')
    return 0


def cmd_grade(args):
    cfg = config.load_vision()
    key = judge.load_key(args.key)
    img_dir = args.img_dir or os.path.join(config.RESEARCH, 'sub', args.sub, 'img')
    pattern = os.path.join(img_dir, f'{args.stu_no}_*.png')
    images = sorted(glob.glob(pattern))
    if not images:
        raise SystemExit(f'{img_dir} 里没有 {args.stu_no} 的页图')

    runs, tokens = [], 0
    for k in range(max(1, args.samples)):
        items, usage = judge.grade_images(cfg, images, key, args.model)
        tokens += usage.get('total_tokens', 0)
        runs.append(items)
        print(f'  第 {k + 1}/{max(1, args.samples)} 次：'
              f'{judge.total_of(items):g} 分')
    items = runs[0] if len(runs) == 1 else judge.merge_votes(runs)
    usage = {'total_tokens': tokens}
    total = judge.total_of(items)
    print(f'学号 {args.stu_no}  页数 {len(images)}  model={args.model or cfg["model"]}')
    print(f'\n{"题":>3} {"满分":>4} {"得分":>4} {"把握":>2}  学生写了什么')
    for it in items:
        no = str(it.get('no'))
        print(f'{no:>3} {config.FULL.get(no, "?"):>4} '
              f'{float(it.get("score") or 0):>4g} {str(it.get("conf", "")):>2}  '
              f'{str(it.get("transcript", ""))[:44]}')
    print(f'\n合计 {total:g} / 100   tokens={usage.get("total_tokens")}')

    out = os.path.join(config.GRADE, f'{args.stu_no}.json')
    os.makedirs(config.GRADE, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'stuNo': args.stu_no, 'score': total, 'items': items,
                   'usage': usage}, f, ensure_ascii=False, indent=1)
    print(f'写入 {out}')
    return 0


def cmd_review(args):
    sub_dir = args.sub if os.path.isabs(args.sub) else os.path.join(
        config.RESEARCH, 'sub', args.sub)
    out = args.out or os.path.join(config.OUT, '复核表.xlsx')
    info = review_mod.build(config.GRADE, sub_dir, out,
                            target=args.target, floor=args.floor, cap=args.cap)
    print(f'已写入 {info["out"]}')
    print(f'人数 {len(info["rows"])}  计入区间均分 {info["mean_raw"]:.2f}  '
          f'调分 {"不动" if info["shift"] == 0 else f"{info["shift"]:+.2f}"}  '
          f'调分后 {info["mean_adj"]:.2f}')
    print(f'总 tokens {info["tokens"]}')
    return 0


def cmd_emit(args):
    scores = json.load(open(args.scores, encoding='utf-8'))
    score_map = {str(s['stuNo']).strip(): float(s.get('final', s.get('total')))
                 for s in scores}
    tpl = template_mod.load_template(args.template)
    print(f'模板：{tpl["sheet"]}  学生 {len(tpl["rows"])} 人')
    print(f'给分：{len(score_map)} 人')

    rows, report = emit.select_rows(tpl['rows'], score_map, args.floor, args.cap)
    print(f"守卫通过：文件 {report['rows']} 行 = 提交 {report['submitters']} 人"
          f"（模板里其余 {report['dropped']} 人不进文件）")

    emit.write_xls(rows, tpl['headers'], tpl['score_index'], score_map, args.out,
                   tpl['sheet'], title_rows=tpl['title_rows'])
    print(f'写出 {args.out}')
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
    work_id = _work_id(args)
    answer_id = _answer_id_of(client, work_id, args.stu_no)
    if not answer_id:
        raise SystemExit(f'批阅列表里找不到 {args.stu_no}')
    if not (config.SCORE_FLOOR <= args.score <= config.SCORE_CAP):
        raise SystemExit(f'分数必须落在 {config.SCORE_FLOOR:g}-{config.SCORE_CAP:g}')
    url = (f'{MOOC2}/mooc2-ans/work/markscore?markScore={args.score}'
           f'&markAnswerIds={answer_id}&markType=0')
    status, raw, _ = client.post_form(url, {
        'courseid': config.COURSE_ID, 'clazzid': config.CLAZZ_ID,
        'cpi': config.CPI, 'workid': work_id, 'answerIds': answer_id,
        'type': '0', 'score': str(args.score),
    }, referer=mark_url(_task_id(args)))
    print(f'{args.stu_no} answerId={answer_id} -> {status} '
          f'{raw.decode("utf-8", "ignore")[:200]}')
    return 0


def cmd_back(args):
    import csv
    client = Client()
    rows = list(csv.DictReader(open(args.csv, encoding='utf-8-sig')))
    ids = [r['answerId'].strip() for r in rows if r.get('answerId', '').strip()]
    print(f'待打回 {len(ids)} 人，理由={args.reason!r}')
    if not args.yes:
        raise SystemExit('这是写操作，确认后加 --yes 重跑')
    for start in range(0, len(ids), 30):
        part = ids[start:start + 30]
        url = f'{MOOC2}/mooc2-ans/work/batchBack?backAnswerIdsStr=' + ','.join(part)
        status, raw, _ = client.post_form(url, {
            'courseid': config.COURSE_ID, 'clazzid': config.CLAZZ_ID,
            'cpi': config.CPI, 'workid': _work_id(args),
            'answerIds': ','.join(part), 'jobid': '', 'reason': args.reason,
            'extraTime': '',
        }, referer=mark_url(_task_id(args)))
        print(f'  {start + 1}-{start + len(part)}: {status} '
              f'{raw.decode("utf-8", "ignore")[:160]}')
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

    p = sub.add_parser('collect', help='下载作答并渲染页图')
    p.add_argument('--sub', default='ch3')
    p.add_argument('--work-id')
    p.add_argument('--scale', type=float, default=2.0)
    p.set_defaults(fn=cmd_collect)

    p = sub.add_parser('grade', help='判一份作业')
    p.add_argument('--stu-no', required=True)
    p.add_argument('--sub', default='ch3')
    p.add_argument('--img-dir')
    p.add_argument('--key', default=os.path.join(config.KEY, 'ch3_key.json'))
    p.add_argument('--model')
    p.add_argument('--samples', type=int, default=1,
                   help='同一份跑几次并取多数；>1 时分歧题自动降为低把握')
    p.set_defaults(fn=cmd_grade)

    p = sub.add_parser('review', help='生成复核表')
    p.add_argument('--sub', default='ch3')
    p.add_argument('-o', '--out')
    p.add_argument('--target', type=float)
    p.add_argument('--floor', type=float)
    p.add_argument('--cap', type=float)
    p.set_defaults(fn=cmd_review)

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

    p = sub.add_parser('inspect', help='只读排查工具')
    p.set_defaults(fn=None)
    args, rest = ap.parse_known_args(argv)
    if args.cmd == 'inspect':
        return toolbox_mod.main(rest)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
