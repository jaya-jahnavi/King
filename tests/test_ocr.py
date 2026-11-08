"""Opt-in integration check. First execution may download OCR models."""
import os
import unittest


@unittest.skipUnless(os.environ.get('KING_TEST_OCR') == '1', 'Set KING_TEST_OCR=1 to run model inference')
class OCRIntegrationTest(unittest.TestCase):
    def test_all_ranks_on_generated_white_cards(self):
        import cv2
        import numpy as np
        from automatic import AutoReader, AutoTracker
        from counting import Counter, RANKS
        frame = np.full((600, 1200, 3), (40, 110, 40), np.uint8)
        expected = {}
        for i, rank in enumerate(RANKS):
            x, y = 20+(i % 7)*165, 20+(i // 7)*270
            cv2.rectangle(frame, (x, y), (x+120, y+180), (255, 255, 255), -1)
            cv2.putText(frame, rank, (x+7, y+40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            expected[(x, y)] = rank
        detections = AutoReader().detect(frame)
        self.assertEqual({d.box[:2]: d.rank for d in detections}, expected)
        tracker, counter = AutoTracker(), Counter()
        for now in range(5):
            for detection in tracker.update(detections, now):
                counter.add(detection.rank)
        self.assertEqual(len(counter.events), 13)
        self.assertEqual(counter.running, 0)
