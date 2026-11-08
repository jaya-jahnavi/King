import unittest
from counting import Counter, RoundGate


class CountingTests(unittest.TestCase):
    def test_complete_deck_balances(self):
        c = Counter(1)
        for rank in ('2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'):
            for _ in range(4):
                c.add(rank)
        self.assertEqual(c.running, 0)
        self.assertIsNone(c.true)
        with self.assertRaises(ValueError):
            c.add('2')

    def test_true_count_and_undo(self):
        c = Counter(6)
        c.add('2')
        c.add('A')
        c.add('6')
        self.assertEqual(c.running, 1)
        self.assertAlmostEqual(c.true, 1 / (6 - 3 / 52))
        c.events.pop()
        self.assertEqual(c.running, 0)

    def test_occlusion_does_not_recount(self):
        gate = RoundGate(2)
        self.assertIsNone(gate.observe(0, 'K'))
        self.assertEqual(gate.observe(0, 'K'), 'K')
        for rank in (None, None, 'K', 'K', 'Q', 'Q'):
            self.assertIsNone(gate.observe(0, rank))
        gate.reset()
        self.assertIsNone(gate.observe(0, 'K'))
        self.assertEqual(gate.observe(0, 'K'), 'K')

    def test_uncertain_frames_break_consensus(self):
        gate = RoundGate(2)
        for rank in ('2', '3', None, '3'):
            self.assertIsNone(gate.observe(1, rank))
        self.assertEqual(gate.observe(1, '3'), '3')
        self.assertIsNone(gate.observe(2, '3'))
        self.assertEqual(gate.observe(2, '3'), '3')


if __name__ == '__main__':
    unittest.main()
