"""读学习通导出的成绩表，切成「表头 + 学生行」，交给 emit 的守卫挑行。"""
import xlrd

from emit import SCORE_HEADER, STUNO_HEADER, find_header


def load_template(path):
    sh = xlrd.open_workbook(path).sheet_by_index(0)
    rows = [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
    header_row, headers = find_header(rows)
    c_stuno = headers.index(STUNO_HEADER)
    c_score = headers.index(SCORE_HEADER)
    data = []
    for row in rows[header_row + 1:]:
        stu_no = str(row[c_stuno]).strip()
        if stu_no:
            data.append({'stuNo': stu_no, 'cells': row})
    return {
        'sheet': sh.name,
        'title_rows': rows[:header_row],
        'headers': headers,
        'score_index': c_score,
        'rows': data,
    }
