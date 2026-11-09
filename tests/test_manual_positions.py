"""Opt-in GUI workflow checks: set KING_TEST_GUI=1 on a desktop session."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('KING_TEST_GUI') == '1', 'Set KING_TEST_GUI=1 for desktop workflow tests')
class ManualPositionTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import cv2
        import numpy as np
        import app
        self.app_module, self.cv2, self.np = app, cv2, np
        self.temporary = tempfile.TemporaryDirectory(prefix='king-gui-test-', dir=Path(__file__).resolve().parents[1])
        self.data = Path(self.temporary.name)
        self.scope = patch.object(app, 'DATA', self.data)
        self.scope.start()
        self.a = app.App(tk.Tk())
        self.a.region = dict(left=0,top=0,width=300,height=200)
        self.board = np.full((200,300,3),(30,90,30),np.uint8)
        self.box = (40,50,60,80)
        self.board[50:130,40:100] = self.rank_patch('K')
        self.a.grab = lambda: self.board.copy()

    def rank_patch(self, rank):
        image = self.np.full((80,60,3),255,self.np.uint8)
        self.cv2.putText(image,rank,(3,58),self.cv2.FONT_HERSHEY_SIMPLEX,1.5,(0,0,0),2)
        return image

    def tearDown(self):
        self.a.close()
        self.scope.stop()
        self.temporary.cleanup()

    def finish(self):
        deadline = time.monotonic()+5
        while self.a.calibrating and time.monotonic()<deadline:
            self.a.window.update()
            time.sleep(.01)
        self.assertFalse(self.a.calibrating)
        self.assertEqual(self.a.window.state(),'normal')

    def add_position(self):
        def selected(*args):
            self.assertEqual(self.a.window.state(),'withdrawn')
            return self.box
        with patch.object(self.a,'select',side_effect=selected):
            self.a.add_slot()
            self.assertEqual(self.a.window.state(),'withdrawn')
            self.finish()

    def test_real_picker_reverse_drag_and_cancel(self):
        import tkinter as tk
        def drag():
            dialog = next(w for w in self.a.window.winfo_children() if isinstance(w,tk.Toplevel))
            canvas = next(w for w in dialog.winfo_children() if isinstance(w,tk.Canvas))
            canvas.event_generate('<ButtonPress-1>',x=100,y=80)
            canvas.event_generate('<B1-Motion>',x=20,y=20)
            canvas.event_generate('<ButtonRelease-1>',x=20,y=20)
            dialog.event_generate('<Return>')
        self.a.window.after(100,drag)
        self.assertEqual(self.a.select(self.board,'GUI test picker'),(20,20,80,60))
        def cancel():
            dialog = next(w for w in self.a.window.winfo_children() if isinstance(w,tk.Toplevel))
            dialog.event_generate('<Escape>')
        self.a.window.after(100,cancel)
        self.assertIsNone(self.a.select(self.board,'Cancel test'))

    def test_add_visible_position_enters_manual_mode_and_restores(self):
        self.add_position()
        self.assertEqual(self.a.slots,[self.box])
        self.assertFalse(self.a.auto.get())
        self.assertEqual(self.a.backend.get(),'Local OCR')
        self.assertEqual(len(self.a.position_table.get_children()),1)
        self.assertIn('Position 1 saved',self.a.calibration_message.get())
        self.a.slots=[]
        self.a.auto.set(True)
        self.a.load()
        self.assertEqual([tuple(box) for box in self.a.slots],[self.box])
        self.assertFalse(self.a.auto.get())

    def test_return_to_automatic_openai_persists_without_deleting_positions(self):
        self.add_position()
        self.a.backend.set('OpenAI')
        self.a.change_provider()
        self.assertTrue(self.a.auto.get())
        self.assertEqual(self.a.slots,[self.box])
        self.a.auto.set(False)
        self.a.load()
        self.assertTrue(self.a.auto.get())
        self.assertEqual(self.a.backend.get(),'OpenAI')

    def test_cancel_no_region_and_remove_are_explicit(self):
        with patch.object(self.a,'select',return_value=None):
            self.a.add_slot()
            self.finish()
        self.assertTrue(self.a.auto.get())
        self.assertFalse(self.a.slots)
        self.assertIn('canceled',self.a.calibration_message.get())
        self.add_position()
        self.a.position_table.selection_set('0')
        self.a.remove_slot()
        self.assertFalse(self.a.slots)
        self.a.region=None
        self.a.add_slot()
        self.assertFalse(self.a.calibrating)
        self.assertIn('video area first',self.a.calibration_message.get())

    def test_template_save_and_manual_count_once_per_round(self):
        self.add_position()
        with patch.object(self.a,'select',return_value=self.box),patch.object(self.app_module.simpledialog,'askstring',return_value='K'):
            self.a.template()
            self.finish()
        self.assertTrue((self.data/'K.png').exists())
        self.assertIn('K',self.a.templates)
        self.a.toggle()
        self.assertFalse(self.a.running)
        self.assertIn('Missing templates',self.a.status.get())
        for rank in self.app_module.RANKS:
            self.a.templates[rank] = self.app_module.normalized(self.rank_patch(rank))
        self.a.toggle()
        self.assertTrue(self.a.running)
        for _ in range(8):
            self.a.tick()
        self.assertEqual([e.rank for e in self.a.counter.events],['K'])
        self.assertEqual(self.a.counter.running,-1)
        self.assertIsNotNone(self.a.last_read_at)
        self.a.next_round()
        self.a.toggle()
        for _ in range(4):
            self.a.tick()
        self.assertEqual([e.rank for e in self.a.counter.events],['K','K'])
        self.assertEqual(self.a.counter.round_number,2)

    def test_invalid_manual_threshold_does_not_stop_automatic_reader(self):
        self.a.threshold.set('invalid')
        self.a.auto.set(True)
        self.a.running=True
        self.a.next_api_at=time.monotonic()+1000
        self.a.tick()
        self.assertTrue(self.a.running)
        self.a.auto.set(False)
        self.a.tick()
        self.assertFalse(self.a.running)
        self.assertIn('threshold',self.a.calibration_message.get())
