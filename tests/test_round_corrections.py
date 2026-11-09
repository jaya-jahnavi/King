import unittest
from counting import Counter


class RoundCorrectionTests(unittest.TestCase):
    def example(self):
        counter = Counter()
        counter.add('2')
        counter.add('K')
        counter.finish_round()
        counter.add('3')
        return counter

    def test_missed_previous_card_updates_later_running_totals(self):
        counter = self.example()
        counter.add_to_round(1,1,'6')
        rows = counter.summaries()
        self.assertEqual(rows[0]['cards'],['2','K','6'])
        self.assertEqual([r['round_count'] for r in rows],[1,1])
        self.assertEqual([r['running_count'] for r in rows],[1,2])
        self.assertEqual(counter.running,2)
        self.assertEqual(counter.round_cards,['3'])
        self.assertEqual([e.round_number for e in counter.events],[1,1,1,2])
        self.assertEqual(Counter.from_dict(counter.to_dict()).summaries(), rows)

    def test_old_shoe_correction_does_not_change_current_shoe(self):
        counter = self.example()
        counter.new_shoe(6)
        counter.add('A')
        counter.add_to_round(1,1,'6')
        rows = counter.summaries()
        self.assertEqual([r['running_count'] for r in rows],[1,2,-1])
        self.assertEqual(counter.running,-1)
        self.assertEqual(counter.round_number,1)
        self.assertEqual(Counter.from_dict(counter.to_dict()).summaries(), rows)

    def test_neutral_card_changes_card_count_only(self):
        counter = self.example()
        counter.add_to_round(1,1,'8')
        row = counter.summaries()[0]
        self.assertEqual(row['card_count'],3)
        self.assertEqual(row['round_count'],0)

    def test_bad_target_or_rank_cannot_mutate_history(self):
        counter = self.example()
        before = counter.to_dict()
        for shoe,round_number,rank in [(99,1,'2'),(1,3,'2'),(1,0,'2'),(1,1,'Z'),(1,1,None)]:
            with self.assertRaises(ValueError):
                counter.add_to_round(shoe,round_number,rank)
            self.assertEqual(counter.to_dict(),before)

    def test_full_archived_shoe_cannot_accept_an_extra_card(self):
        counter = Counter(1)
        for _ in range(52):
            counter.add('2')
        counter.new_shoe(6)
        before = counter.to_dict()
        with self.assertRaises(ValueError):
            counter.add_to_round(1,1,'K')
        self.assertEqual(counter.to_dict(), before)
