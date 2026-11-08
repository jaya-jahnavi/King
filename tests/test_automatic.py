import unittest
from automatic import AutoTracker, Detection, parse_rank


class AutomaticTests(unittest.TestCase):
    def test_rank_filter(self):
        self.assertEqual(parse_rank(' 10♠ '), '10')
        self.assertIsNone(parse_rank('BLACKJACK'))
        self.assertIsNone(parse_rank('21'))

    def test_moving_card_counts_once(self):
        tracker = AutoTracker(stable=2)
        self.assertFalse(tracker.update([Detection((10, 10, 60, 90), 'K')], 0))
        self.assertEqual(len(tracker.update([Detection((15, 12, 60, 90), 'K')], 1)), 1)
        self.assertFalse(tracker.update([], 2))
        self.assertFalse(tracker.update([Detection((20, 12, 60, 90), 'K')], 3))

    def test_equal_ranks_are_distinct_cards(self):
        tracker = AutoTracker(stable=2)
        cards = [Detection((10, 10, 60, 90), 'A'), Detection((90, 10, 60, 90), 'A')]
        tracker.update(cards, 0)
        self.assertEqual(len(tracker.update(cards[::-1], 1)), 2)

    def test_unreadable_card_does_not_reset_round(self):
        tracker = AutoTracker(stable=1)
        tracker.update([Detection((0, 0, 60, 90), '2')], 0)
        tracker.update([Detection((0, 0, 60, 90), None)], 5)
        self.assertFalse(tracker.update([Detection((0, 0, 60, 90), '2')], 8))
        tracker.update([], 9)
        tracker.update([], 13)
        self.assertEqual(len(tracker.update([Detection((0, 0, 60, 90), '2')], 14)), 1)

    def test_disagreement_requires_new_consensus(self):
        tracker = AutoTracker(stable=2)
        for i, rank in enumerate(['2', 'A', None, '2']):
            self.assertFalse(tracker.update([Detection((0, 0, 60, 90), rank)], i))
        self.assertEqual(len(tracker.update([Detection((0, 0, 60, 90), '2')], 5)), 1)
