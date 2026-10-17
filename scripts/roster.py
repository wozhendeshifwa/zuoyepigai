"""谁真的交了作业：以「学生答案里有没有附件」为准，不认页面上的计数。

教训：作业列表写着「10 已交」、批阅列表默认只回 10 行、成绩表里 35 人有提交时间，
三个数字各不相同。以附件为准才对得上真实提交数。
"""
import re

from client import Client, mark_list_url, review_url

ROW_RE = re.compile(r'<ul class="dataBody_td" id="(\d+)"(.*?)</ul>', re.S)
CELL_RE = re.compile(r'<li class="taskBody_con wid_bf_\d+">\s*(.*?)\s*</li>', re.S)
NAME_RE = re.compile(r'id="name\d+">([^<]+)</div>')


def parse_mark_list(html):
    """解析批阅列表片段。返回 [{answerId, name, stuNo, submitTime, ip}]。"""
    rows = []
    for m in ROW_RE.finditer(html):
        block = m.group(2)
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in CELL_RE.findall(block)]
        stu_no = next((c for c in cells if re.fullmatch(r'\d{8,}', c)), '')
        name = NAME_RE.search(block)
        rows.append({
            'answerId': m.group(1),
            'name': name.group(1).strip() if name else '',
            'stuNo': stu_no,
            'submitTime': cells[1] if len(cells) > 1 else '',
            'ip': cells[2] if len(cells) > 2 else '',
        })
    return rows


def answer_objectid(client, work_id, answer_id):
    """学生答案那一段里的附件 objectid；只在 stuAnswerWords 到 </dl> 之间找，
    否则会越过边界抓到下面「正确答案」的附件（踩过一次）。"""
    text = client.get_text(review_url(work_id, answer_id))
    block = re.search(r'class="stuAnswerWords.*?(?:</dl>|</dd>)', text, re.S)
    if not block:
        return None
    m = re.search(r'objectid="([0-9a-f]{32})"', block.group(0))
    return m.group(1) if m else None


def collect(client, work_id, check_attachment=True, log=print):
    """返回 (all_rows, submitted_rows)。submitted = 有提交时间且答案里真有附件。"""
    html = client.get_text(mark_list_url(work_id))
    rows = parse_mark_list(html)
    if not rows:
        raise SystemExit('批阅列表为空——workid 或 Cookie 可能不对')
    log(f'批阅列表 {len(rows)} 人，其中有提交时间的 {sum(1 for r in rows if r["submitTime"])} 人')

    if not check_attachment:
        for r in rows:
            r['objectid'] = None
            r['submitted'] = bool(r['submitTime'])
        return rows, [r for r in rows if r['submitted']]

    for r in rows:
        r['objectid'] = None
        r['submitted'] = False
        if not r['submitTime']:
            continue
        oid = answer_objectid(client, work_id, r['answerId'])
        if oid:
            r['objectid'] = oid
            r['submitted'] = True
            log(f'  交了：{r["stuNo"]} {r["name"]}')
        else:
            log(f'  只点了提交、没传文件：{r["stuNo"]} {r["name"]}')
    return rows, [r for r in rows if r['submitted']]
