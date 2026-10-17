"""调分测试：区间 75-98、目标 92±1、平移后再夹区间。"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import calibrate  # noqa: E402

FLOOR, CAP, TARGET = 75.0, 98.0, 92.0


class CalibrateTest(unittest.TestCase):
    def test_inside_band_does_not_move(self):
        totals = [98, 98, 95, 95, 87.5, 80]
        shift, adj = calibrate.calibrate(totals, TARGET, FLOOR, CAP)
        self.assertEqual(shift, 0.0)
        self.assertEqual(adj, totals)

    def test_mean_above_target_shifts_down(self):
        totals = [98, 98, 98, 98, 98, 98, 95]  # 均分 97.57，远高于目标
        shift, adj = calibrate.calibrate(totals, TARGET, FLOOR, CAP)
        self.assertLess(shift, 0)
        self.assertAlmostEqual(sum(adj) / len(adj), TARGET, delta=1.0)
        for v in adj:
            self.assertGreaterEqual(v, FLOOR)
            self.assertLessEqual(v, CAP)

    def test_real_class_data_is_left_alone(self):
        """本次第3章：均分 92.45，落在 92±1 内，一分都不用动。"""
        totals = [98, 98, 98, 98, 95, 95, 95, 87.5, 80, 80]
        shift, adj = calibrate.calibrate(totals, TARGET, FLOOR, CAP)
        self.assertEqual(shift, 0.0)
        self.assertEqual(adj, totals)

    def test_mean_below_target_shifts_up_but_never_past_cap(self):
        totals = [60, 60, 60, 60]
        shift, adj = calibrate.calibrate(totals, TARGET, FLOOR, CAP)
        self.assertGreater(shift, 0)
        for v in adj:
            self.assertGreaterEqual(v, FLOOR)
            self.assertLessEqual(v, CAP)

    def test_empty_input(self):
        self.assertEqual(calibrate.calibrate([], TARGET, FLOOR, CAP), (0.0, []))

    def test_to_range_clamps_both_ends(self):
        self.assertEqual(calibrate.to_range(100, FLOOR, CAP), CAP)
        self.assertEqual(calibrate.to_range(50, FLOOR, CAP), FLOOR)
        self.assertEqual(calibrate.to_range(87.5, FLOOR, CAP), 87.5)


if __name__ == '__main__':
    unittest.main()
