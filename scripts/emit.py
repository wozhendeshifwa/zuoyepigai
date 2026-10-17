"""生成成绩导入文件，以及那个本该早点存在的守卫。

学习通的导入是**按行全量写**：文件里有一行，它就当成这个人已批并写分。
所以文件里的学生必须恰好是「真的交了作业的人」——多一行，就等于给一个
没交作业的人写了个分（2026-10-17 就是这样把 87 个人写成 0 分的）。

这里把「选哪些行、能不能写」做成纯函数，测试直接打它们，不碰网络。
"""
import xlwt

SCORE_HEADER = '分数'
STUNO_HEADER = '学号/工号'
STATE_HEADER = '状态'


class GuardError(ValueError):
    """守卫拦下了不该生成的导入文件。"""


def find_header(rows):
    """rows: [[cell, ...], ...]；返回 (header_row_index, headers)。"""
    for i, row in enumerate(rows[:6]):
        labels = [str(c).strip() for c in row]
        if STUNO_HEADER in labels and SCORE_HEADER in labels:
            return i, labels
    raise GuardError(f'模板里找不到同时含「{STUNO_HEADER}」与「{SCORE_HEADER}」的表头行')


def select_rows(template_rows, scores, floor, cap):
    """挑出要写进导入文件的行，并做完全部守卫。

    template_rows: [{'stuNo': str, 'cells': [...]}, ...]（模板里的学生行）
    scores: {stuNo: 最终分}
    返回 (header_free_rows, report)，header_free_rows 只含提交者，顺序随 scores。
    """
    if not scores:
        raise GuardError('没有任何分数可写')

    bad = {no: s for no, s in scores.items() if not (floor <= float(s) <= cap)}
    if bad:
        detail = ', '.join(f'{k}={v:g}' for k, v in sorted(bad.items())[:5])
        raise GuardError(f'分数超出 {floor:g}-{cap:g} 区间：{detail}')

    by_no = {r['stuNo']: r for r in template_rows}
    missing = [no for no in scores if no not in by_no]
    if missing:
        raise GuardError(f'这些学号不在模板里：{missing[:5]}')

    picked = [by_no[no] for no in scores]
    picked_nos = {r['stuNo'] for r in picked}
    leaked = picked_nos - set(scores)
    if leaked:
        raise GuardError(f'文件里出现了没给分的人：{sorted(leaked)[:5]}')
    if len(picked) != len(scores):
        raise GuardError(f'行数 {len(picked)} 与给分人数 {len(scores)} 不一致')

    return picked, {
        'rows': len(picked),
        'submitters': len(scores),
        'template_students': len(template_rows),
        'dropped': len(template_rows) - len(picked),
    }


def write_xls(rows, headers, score_index, scores, out_path, sheet_name,
              title_rows=()):
    """把选出来的行写成 .xls（xlwt 直写，值可靠；格式不保留）。"""
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet(sheet_name[:31])
    r = 0
    for tr in title_rows:
        for c, v in enumerate(tr):
            if str(v).strip():
                ws.write(r, c, v)
        r += 1
    bold = xlwt.easyxf('font: bold on')
    for c, h in enumerate(headers):
        ws.write(r, c, h, bold)
    r += 1
    for row in rows:
        for c, v in enumerate(row['cells']):
            if c == score_index:
                ws.write(r, c, float(scores[row['stuNo']]))
            elif isinstance(v, float):
                ws.write(r, c, v)
            else:
                ws.write(r, c, str(v))
        r += 1
    wb.save(out_path)
    return r
