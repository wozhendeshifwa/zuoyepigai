"""多采样合并：同一份作业跑多次，逐题取多数，分歧降为低把握。"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import config  # noqa: E402
import judge  # noqa: E402


def run(**scores):
    return [{'no': no, 'score': s, 'conf': '高', 'transcript': ''}
            for no, s in scores.items()]


class MergeVotesTest(unittest.TestCase):
    def test_majority_wins(self):
        runs = [run(**{'18': 5}), run(**{'18': 10}), run(**{'18': 10})]
        merged = judge.merge_votes(runs, [('18', '简答', 10)])
        self.assertEqual(merged[0]['score'], 10)
        self.assertEqual(merged[0]['conf'], '低')
        self.assertIn('不一致', merged[0]['note'])

    def test_agreement_keeps_confidence(self):
        runs = [run(**{'18': 5}), run(**{'18': 5}), run(**{'18': 5})]
        merged = judge.merge_votes(runs, [('18', '简答', 10)])
        self.assertEqual(merged[0]['score'], 5)
        self.assertEqual(merged[0]['conf'], '高')
        self.assertNotIn('note', merged[0])

    def test_missing_question_skipped(self):
        merged = judge.merge_votes([run(**{'2': 5})], [('2', '选择', 5),
                                                       ('8', '简答', 10)])
        self.assertEqual([m['no'] for m in merged], ['2'])

    def test_still_covers_every_question(self):
        runs = [run(**{no: 0 for no, _, _ in config.QUESTIONS}),
                run(**{no: 0 for no, _, _ in config.QUESTIONS})]
        merged = judge.merge_votes(runs, config.QUESTIONS)
        self.assertEqual(len(merged), len(config.QUESTIONS))


if __name__ == '__main__':
    unittest.main()
