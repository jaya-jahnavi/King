import json
import unittest
from counting import Counter
from automatic import AutoTracker, Detection
from openai_vision import Observation, VisionGate


class RoundHistoryTests(unittest.TestCase):
    def test_round_counts_and_running_totals_are_separate(self):
        counter = Counter()
        for rank in ['2', '3', 'K']:
            counter.add(rank)
        self.assertTrue(counter.finish_round())
        self.assertFalse(counter.finish_round())
        for rank in ['A', '6']:
            counter.add(rank)
        rows = counter.summaries()
        self.assertEqual([r['round'] for r in rows], [1, 2])
        self.assertEqual([r['round_count'] for r in rows], [1, 0])
        self.assertEqual([r['running_count'] for r in rows], [1, 1])
        self.assertEqual(counter.round_cards, ['A', '6'])

    def test_save_restore_and_undo_recompute_history(self):
        counter = Counter()
        counter.add('2', 'OpenAI Fast, one read')
        counter.finish_round()
        counter.add('K')
        restored = Counter.from_dict(json.loads(json.dumps(counter.to_dict())))
        self.assertEqual(restored.summaries(), counter.summaries())
        self.assertEqual(restored.round_number, 2)
        restored.events.pop()
        self.assertEqual(restored.running, 1)
        self.assertEqual(restored.round_count, 0)

    def test_new_shoe_preserves_old_rounds(self):
        counter = Counter()
        counter.add('K')
        counter.new_shoe(8)
        counter.add('2')
        self.assertEqual(counter.running, 1)
        rows = Counter.from_dict(counter.to_dict()).summaries()
        self.assertEqual([(r['shoe'],r['round'],r['running_count']) for r in rows], [(1,1,-1),(2,1,1)])
        self.assertEqual(rows[0]['state'], 'Saved')

    def test_corrupt_event_round_rejected(self):
        counter = Counter()
        counter.add('2')
        saved = counter.to_dict()
        saved['current']['events'][0]['round_number'] = 5
        with self.assertRaises(ValueError):
            Counter.from_dict(saved)

    def test_cloud_clear_emits_one_round_boundary(self):
        gate = VisionGate(confirmations=1)
        self.assertEqual(gate.update(Observation('cards',True,[Detection((0,0,0,0),'2')]), 0), ['2'])
        self.assertFalse(gate.round_ended)
        gate.update(Observation('empty',True,[]), 1)
        self.assertFalse(gate.round_ended)
        gate.update(Observation('empty',True,[]), 5)
        self.assertTrue(gate.round_ended)
        gate.update(Observation('empty',True,[]), 7)
        self.assertFalse(gate.round_ended)

    def test_local_clear_emits_one_round_boundary(self):
        tracker = AutoTracker(stable=1)
        tracker.update([Detection((0,0,20,40),'2')], 0)
        tracker.update([], 1)
        tracker.update([], 5)
        self.assertTrue(tracker.round_ended)
        tracker.update([], 8)
        self.assertFalse(tracker.round_ended)
