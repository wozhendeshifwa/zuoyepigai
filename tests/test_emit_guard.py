"""导入文件的守卫测试：2026-10-17 那次把 87 个未交的人写成 0 分，必须被拦住。"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import emit  # noqa: E402

FLOOR, CAP = 75.0, 98.0
HEADERS = ['学号/工号', '学生姓名', '分数', '状态']


def make_template(n=97):
    rows = []
    for i in range(n):
        rows.append({'stuNo': f'2024150{i:05d}',
                     'cells': [f'2024150{i:05d}', f'学生{i}', 0, '未交']})
    return rows


class SelectRowsTest(unittest.TestCase):
    def test_only_submitters_survive(self):
        """97 人模板 + 3 人交 → 只能出 3 行。这就是事故的根因。"""
        rows, report = emit.select_rows(
            make_template(97), {'202415000001': 90, '202415000002': 85,
                                '202415000003': 80}, FLOOR, CAP)
        self.assertEqual(len(rows), 3)
        self.assertEqual(report['rows'], 3)
        self.assertEqual(report['submitters'], 3)
        self.assertEqual(report['dropped'], 94)

    def test_score_above_cap_rejected(self):
        with self.assertRaises(emit.GuardError):
            emit.select_rows(make_template(5), {'202415000000': 100}, FLOOR, CAP)

    def test_score_below_floor_rejected(self):
        with self.assertRaises(emit.GuardError):
            emit.select_rows(make_template(5), {'202415000000': 60}, FLOOR, CAP)

    def test_unknown_student_rejected(self):
        with self.assertRaises(emit.GuardError):
            emit.select_rows(make_template(5), {'99999999': 90}, FLOOR, CAP)

    def test_empty_scores_rejected(self):
        with self.assertRaises(emit.GuardError):
            emit.select_rows(make_template(5), {}, FLOOR, CAP)

    def test_float_score_inside_range_ok(self):
        rows, _ = emit.select_rows(make_template(5), {'202415000000': 87.5},
                                   FLOOR, CAP)
        self.assertEqual(len(rows), 1)


class FindHeaderTest(unittest.TestCase):
    def test_skips_title_row(self):
        rows = [['作业名称：第3章第1次作业', '', '', ''],
                HEADERS]
        idx, labels = emit.find_header(rows)
        self.assertEqual(idx, 1)
        self.assertIn('分数', labels)

    def test_missing_header_raises(self):
        with self.assertRaises(emit.GuardError):
            emit.find_header([['随便', '什么']])


class WriteXlsTest(unittest.TestCase):
    def test_roundtrip_has_exactly_the_submitters(self):
        import xlrd

        template = make_template(97)
        scores = {'202415000001': 90.0, '202415000002': 87.5}
        rows, _ = emit.select_rows(template, scores, FLOOR, CAP)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'out.xls')
            n = emit.write_xls(rows, HEADERS, 2, scores, path, '第3章第1次作业',
                               title_rows=[['作业名称：第3章第1次作业']])
            self.assertEqual(n, 1 + 1 + 2)  # 标题 + 表头 + 2 人
            sh = xlrd.open_workbook(path).sheet_by_index(0)
            self.assertEqual(sh.nrows, 4)
            self.assertEqual(str(sh.cell_value(2, 2)), '90.0')
            self.assertEqual(str(sh.cell_value(3, 2)), '87.5')
            nos = {str(sh.cell_value(r, 0)) for r in (2, 3)}
            self.assertEqual(nos, {'202415000001', '202415000002'})


if __name__ == '__main__':
    unittest.main()
