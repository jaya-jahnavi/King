"""King: calibrated screen capture card-counting prototype. Run: python app.py."""
import csv
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

import cv2
import mss
import numpy as np
from PIL import Image, ImageTk

from counting import Counter, RoundGate, RANKS
from automatic import AutoReader, AutoTracker
from displays import bounds, contains, physical_selection, capture_region, enable_dpi_awareness
from openai_vision import OpenAIReader, VisionGate, VisionError, DEFAULT_MODEL

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'calibration'


def normalized(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    return cv2.resize(gray, (40, 56), interpolation=cv2.INTER_AREA).astype(np.float32)


def recognize(crop, templates, threshold):
    sample = normalized(crop)
    # A near-uniform patch contains too little information for recognition.
    if sample.std() < 12:
        return None, 0.0
    scores = []
    for rank, template in templates.items():
        score = float(cv2.matchTemplate(sample, template, cv2.TM_CCOEFF_NORMED)[0, 0])
        scores.append((score, rank))
    scores.sort(reverse=True)
    if not scores:
        return None, 0.0
    best, rank = scores[0]
    margin = best - scores[1][0] if len(scores) > 1 else 0
    return (rank if best >= threshold and margin >= 0.08 else None), best


class App:
    def __init__(self, window):
        self.window = window
        self.capture = mss.mss()
        self.monitors = [bounds(m) for m in self.capture.monitors[1:]]
        self.region = None
        self.slots = []
        self.templates = {}
        self.counter = Counter()
        self.gate = RoundGate()
        self.running = False
        self.auto = tk.BooleanVar(value=True)
        self.tracker = AutoTracker()
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.reader = None
        self.future = None
        self.generation = 0
        self.detections = []
        self.backend = tk.StringVar(value='Local OCR')
        self.api_model = tk.StringVar(value=DEFAULT_MODEL)
        self.api_key = os.environ.get('OPENAI_API_KEY', '').strip()
        self.api_interval = tk.DoubleVar(value=2)
        self.api_limit = tk.IntVar(value=60)
        self.api_calls = 0
        self.api_tokens = [0, 0]
        self.next_api_at = 0
        self.vision_gate = VisionGate()
        self.test_frame = None
        self.api_info = tk.StringVar(value='Local OCR selected. OpenAI mode sends the selected table crop to OpenAI and incurs API charges.')
        self.status = tk.StringVar(value='Screen preview is live. Select the screen containing your browser, then click Select table.')
        self.stats = tk.StringVar()
        self.threshold = tk.DoubleVar(value=0.90)
        window.title('King • Live card count prototype')
        window.geometry('1060x820')
        source = ttk.Frame(window, padding=8)
        source.pack(fill='x')
        ttk.Label(source, text='Screen:').pack(side='left')
        self.monitor_names = self.display_names()
        self.monitor_choice = ttk.Combobox(source, values=self.monitor_names, state='readonly', width=38)
        self.monitor_choice.current(0)
        self.monitor_choice.pack(side='left', padx=8)
        self.monitor_choice.bind('<<ComboboxSelected>>', self.change_display)
        ttk.Button(source, text='Refresh screens', command=self.refresh_displays).pack(side='left', padx=4)
        self.capture_info = tk.StringVar()
        ttk.Label(window, textvariable=self.capture_info, padding=4, wraplength=1000).pack(fill='x')
        ttk.Checkbutton(source, text='Automatic card reading', variable=self.auto, command=self.change_mode).pack(side='left')
        ttk.Label(source, text='Select table to start automatic counting.').pack(side='left', padx=8)
        cloud = ttk.Frame(window, padding=6)
        cloud.pack(fill='x')
        ttk.Label(cloud, text='Reader:').pack(side='left')
        provider = ttk.Combobox(cloud, textvariable=self.backend, values=['Local OCR', 'OpenAI'], state='readonly', width=11)
        provider.pack(side='left', padx=4)
        provider.bind('<<ComboboxSelected>>', self.change_mode)
        model = ttk.Combobox(cloud, textvariable=self.api_model, values=[DEFAULT_MODEL, 'gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna'], state='readonly', width=18)
        model.pack(side='left', padx=4)
        model.bind('<<ComboboxSelected>>', self.change_mode)
        ttk.Button(cloud, text='Set API key', command=self.set_api_key).pack(side='left', padx=3)
        ttk.Button(cloud, text='Test recording (1 call)', command=self.test_recording).pack(side='left', padx=3)
        ttk.Label(cloud, text=' Min seconds:').pack(side='left')
        ttk.Spinbox(cloud, from_=1, to=30, textvariable=self.api_interval, width=4).pack(side='left')
        ttk.Label(cloud, text=' Call limit:').pack(side='left')
        ttk.Spinbox(cloud, from_=1, to=1000, textvariable=self.api_limit, width=5).pack(side='left')
        ttk.Label(window, textvariable=self.api_info, wraplength=1000, padding=4).pack(fill='x')
        bar = ttk.Frame(window, padding=10)
        bar.pack(fill='x')
        for label, command in [('Select table', self.select_table), ('Add card position', self.add_slot),
                               ('Save rank template', self.template), ('Start / Pause', self.toggle),
                               ('Next round', self.next_round), ('Shuffle / New shoe', self.shuffle)]:
            ttk.Button(bar, text=label, command=command).pack(side='left', padx=3)
        ttk.Label(window, textvariable=self.stats, font=('Segoe UI', 19)).pack(pady=8)
        ttk.Label(window, textvariable=self.status, wraplength=1000).pack(padx=12, pady=6)
        self.preview = ttk.Label(window)
        self.preview.pack(pady=6)
        controls = ttk.Frame(window, padding=8)
        controls.pack(fill='x')
        ttk.Label(controls, text='Manual card:').pack(side='left')
        for rank in RANKS:
            ttk.Button(controls, text=rank, width=3, command=lambda r=rank: self.manual(r)).pack(side='left', padx=1)
        ttk.Button(controls, text='Undo last', command=self.undo).pack(side='left', padx=6)
        ttk.Button(controls, text='Export CSV', command=self.export).pack(side='left')
        ttk.Label(controls, text=' Manual match:').pack(side='left')
        ttk.Spinbox(controls, from_=0.7, to=0.99, increment=0.01, width=5, textvariable=self.threshold).pack(side='left')
        self.log = tk.Listbox(window, height=8, font=('Consolas', 10))
        self.log.pack(fill='both', expand=True, padx=12, pady=8)
        ttk.Label(window, text='Automatic: visible white cards • Three matching reads • Clear table for 3 seconds between hands • Reset at shuffle',
                  padding=8).pack()
        self.load()
        if self.region:
            self.running = True
            self.status.set('Starting automatic reader for saved table region. Keep King outside the captured area.')
        self.refresh()
        self.update_capture_info()
        window.protocol('WM_DELETE_WINDOW', self.close)
        window.after(200, self.tick)
        window.after(3000, self.check_displays)

    def grab(self):
        return np.array(self.capture.grab(self.region))[:, :, :3].copy()

    def select(self, frame, title):
        # Fit the selection image onto the display, including on 4K/multi-screen setups.
        height, width = frame.shape[:2]
        scale = min(1.0, 1200 / width, 650 / height,
                    self.window.winfo_screenwidth() * 0.85 / width,
                    self.window.winfo_screenheight() * 0.75 / height)
        shown = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))))
        dialog = tk.Toplevel(self.window)
        dialog.title(title)
        dialog.attributes('-topmost', True)
        ttk.Label(dialog, text='Drag to select • Enter accepts • Escape cancels', padding=8).pack()
        canvas = tk.Canvas(dialog, width=shown.shape[1], height=shown.shape[0], highlightthickness=0)
        canvas.pack()
        picture = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(shown, cv2.COLOR_BGR2RGB)))
        canvas.create_image(0, 0, anchor='nw', image=picture)
        state = {'start': None, 'box': None, 'rectangle': None, 'accepted': False}

        def press(event):
            state['start'] = (max(0, min(shown.shape[1], event.x)), max(0, min(shown.shape[0], event.y)))

        def drag(event):
            if state['start'] is None:
                return
            x0, y0 = state['start']
            x1, y1 = max(0, min(shown.shape[1], event.x)), max(0, min(shown.shape[0], event.y))
            state['box'] = (min(x0, x1), min(y0, y1), abs(x1-x0), abs(y1-y0))
            if state['rectangle'] is not None:
                canvas.delete(state['rectangle'])
            state['rectangle'] = canvas.create_rectangle(x0, y0, x1, y1, outline='#00ff88', width=2)

        def accept(event=None):
            if state['box'] and min(state['box'][2:]) > 2:
                state['accepted'] = True
                dialog.destroy()

        canvas.bind('<ButtonPress-1>', press)
        canvas.bind('<B1-Motion>', drag)
        canvas.bind('<ButtonRelease-1>', drag)
        dialog.bind('<Return>', accept)
        dialog.bind('<Escape>', lambda event: dialog.destroy())
        ttk.Button(dialog, text='Use selected area', command=accept).pack(pady=8)
        dialog.grab_set()
        dialog.focus_force()
        self.selecting = True
        try:
            self.window.wait_window(dialog)
        finally:
            self.selecting = False
        if not state['accepted']:
            return None
        return physical_selection(width, height, shown.shape[1], shown.shape[0], state['box'])

    def display_names(self):
        return [f'Display {i}: {m["width"]} × {m["height"]} at ({m["left"]}, {m["top"]})'
                for i, m in enumerate(self.monitors, 1)]

    def selected_monitor(self):
        index = self.monitor_choice.current()
        if not 0 <= index < len(self.monitors):
            raise ValueError('Choose a connected screen, or click Refresh screens')
        return self.monitors[index]

    def update_capture_info(self):
        monitor = self.selected_monitor()
        if self.region:
            self.capture_info.set(f'Capturing table on {self.monitor_choice.get()}: '
                                  f'{self.region["width"]} × {self.region["height"]} pixels. '
                                  'Keep the video visible on that display; King can stay on another display.')
        else:
            self.capture_info.set(f'Previewing {self.monitor_choice.get()}. Click Select table to choose the video area.')

    def reset_capture_source(self):
        self.running = False
        self.invalidate()
        self.region = None
        self.slots = []
        self.gate.reset()
        self.tracker.reset()
        self.detections = []
        self.vision_gate.reset()
        self.test_frame = None

    def change_display(self, event=None):
        self.reset_capture_source()
        self.update_capture_info()
        self.save()
        self.status.set('Screen changed; preview now shows the chosen display. Select table again. '
                        'Shoe count retained; resume on a fresh round to avoid recounting old cards.')

    def refresh_displays(self, quiet=False):
        replacement = None
        try:
            replacement = mss.mss()
            monitors = [bounds(m) for m in replacement.monitors[1:]]
            if not monitors:
                raise OSError('No connected displays detected')
            previous = self.selected_monitor()
            changed = monitors != self.monitors
            self.capture.close()
            self.capture, replacement = replacement, None
            if changed:
                self.monitors = monitors
                self.monitor_names = self.display_names()
                self.monitor_choice.configure(values=self.monitor_names)
                self.monitor_choice.current(monitors.index(previous) if previous in monitors else 0)
                self.reset_capture_source()
                self.update_capture_info()
                self.save()
                self.status.set('Display layout changed. Capture paused and old crop cleared. '
                                'Choose the video screen and Select table again. Shoe count retained; resume on a fresh round.')
            elif not quiet:
                self.status.set('Screens refreshed. Choose the display containing the video, then Select table.')
        except Exception as exc:
            self.running = False
            self.invalidate()
            self.status.set(f'Cannot refresh screens: {exc}')
        finally:
            if replacement is not None:
                replacement.close()

    def check_displays(self):
        if self.window.state() != 'withdrawn' and not getattr(self, 'selecting', False):
            self.refresh_displays(quiet=True)
        self.window.after(3000, self.check_displays)

    def invalidate(self):
        self.generation += 1

    def change_mode(self, event=None):
        self.running = False
        self.invalidate()
        self.vision_gate.reset()
        self.tracker.reset()
        self.detections = []
        self.test_frame = None
        self.next_api_at = 0
        self.status.set('Reader changed; paused. Test OpenAI on a recording first. If cards were already counted, resume on a fresh round to avoid recounting.')
        self.api_info.set(f'OpenAI uploads cropped images and incurs charges. {self.api_calls} requests started this session; key is kept in memory.'
                          if self.backend.get() == 'OpenAI' else 'Local OCR selected. No new OpenAI requests; any in-flight request may still finish.')

    def set_api_key(self):
        self.running = False
        self.invalidate()
        key = simpledialog.askstring('OpenAI API key — local session only',
                                     'Enter your API key here, not in chat. It stays in memory until King closes.\n'
                                     'OpenAI mode uploads the selected table crop and incurs API charges.',
                                     show='*', parent=self.window)
        if key is None or not key.strip():
            return False
        self.api_key = key.strip()
        self.backend.set('OpenAI')
        self.auto.set(True)
        self.change_mode()
        self.api_info.set('Key set for this session; not yet validated. Test recording makes one paid image request. No key is saved to disk.')
        return True

    def ensure_api_key(self):
        return bool(self.api_key) or self.set_api_key()

    def cloud_settings(self):
        try:
            interval, limit = float(self.api_interval.get()), int(self.api_limit.get())
        except (ValueError, tk.TclError):
            raise VisionError('Enter a request interval (1–30 seconds) and call limit (1–1000).') from None
        if not 1 <= interval <= 30 or not 1 <= limit <= 1000:
            raise VisionError('Enter a request interval (1–30 seconds) and call limit (1–1000).')
        if self.api_calls >= limit:
            raise VisionError('OpenAI call limit reached. Counting paused. Increase Call limit only if you want more paid requests.')
        return interval, limit

    def submit_cloud(self, frame, task='live'):
        interval, limit = self.cloud_settings()
        reader = OpenAIReader(self.api_key, self.api_model.get())
        self.pending_generation, self.pending_time = self.generation, time.monotonic()
        self.pending_backend, self.pending_task = 'OpenAI', task
        self.api_calls += 1
        self.next_api_at = self.pending_time+interval
        self.api_info.set(f'OpenAI {self.api_calls}/{limit} requests started; image processing. Selected table crop sent to OpenAI. Pause stops new requests.')
        self.future = self.worker.submit(reader.read, frame.copy())

    def test_recording(self):
        self.running = False
        self.invalidate()
        if self.future is not None:
            return self.status.set('Wait for the current reader request to finish, then click Test recording again.')
        if not self.ensure_api_key():
            return
        self.backend.set('OpenAI')
        self.auto.set(True)
        self.change_mode()
        filename = filedialog.askopenfilename(title='Choose a recording or image — one paid OpenAI request',
                                              filetypes=[('Video or image', '*.mp4 *.mkv *.avi *.mov *.png *.jpg *.jpeg'), ('All files', '*.*')])
        if not filename:
            return
        try:
            if Path(filename).suffix.lower() in ('.png', '.jpg', '.jpeg'):
                frame = cv2.imread(filename)
            else:
                video = cv2.VideoCapture(filename)
                try:
                    fps, frames = video.get(cv2.CAP_PROP_FPS), video.get(cv2.CAP_PROP_FRAME_COUNT)
                    duration = max(0, (frames-1)/fps) if fps > 0 else 0
                    seconds = simpledialog.askfloat('Choose test frame', f'Seconds into recording (0–{duration:.1f}):',
                                                    initialvalue=min(60, duration), minvalue=0, maxvalue=duration, parent=self.window)
                    if seconds is None:
                        return
                    video.set(cv2.CAP_PROP_POS_MSEC, seconds*1000)
                    ok, frame = video.read()
                    if not ok:
                        frame = None
                finally:
                    video.release()
            if frame is None:
                raise VisionError('Could not read that recording or image.')
            box = self.select(frame, 'Select MAIN tabletop only; exclude duplicate dealer overlay')
            if not box:
                return
            x, y, w, h = box
            self.test_frame = frame[y:y+h, x:x+w].copy()
            self.detections = []
            self.submit_cloud(self.test_frame, task='test')
            self.status.set('Testing one cropped frame with OpenAI. This test does not change the shoe count.')
        except (VisionError, cv2.error) as exc:
            self.status.set(str(exc) if isinstance(exc, VisionError) else 'Could not decode the selected frame.')

    def consume_cloud(self, observation, task, captured_at):
        age = time.monotonic()-captured_at
        self.api_tokens[0] += observation.input_tokens
        self.api_tokens[1] += observation.output_tokens
        self.api_info.set(f'OpenAI: {self.api_calls} requests started | last request {observation.latency:.1f}s | '
                          f'image age {age:.1f}s | tokens used {self.api_tokens[0]} input / {self.api_tokens[1]} output. API charges apply.')
        self.detections = observation.cards
        if task == 'test':
            ranks = [d.rank for d in observation.cards if d.rank]
            total = sum(1 if r in RANKS[:5] else -1 if r in RANKS[8:] else 0 for r in ranks)
            self.status.set(f'Test only: {len(ranks)} readable cards, visible-set Hi-Lo {total:+d}; '
                            f'table {observation.table_state}, complete={observation.complete}. Shoe count unchanged.')
            messagebox.showinfo('OpenAI frame test — verify against the recording',
                                f'Readable cards: {len(ranks)}\nRanks: {", ".join(ranks) or "none"}\n'
                                f'Visible-set Hi-Lo: {total:+d}\nModel reports complete: {observation.complete}\n'
                                f'Request time: {observation.latency:.1f}s\n\n'
                                'This is one frame, not the shoe count. Check every card and duplicate corner before live use.', parent=self.window)
            return
        if age > 30:
            self.running = False
            self.detections = []
            self.status.set('OpenAI result is over 30 seconds old; live counting paused without applying it.')
            return
        added = self.vision_gate.update(observation, captured_at)
        if len(self.counter.events)+len(added) > self.counter.decks*52:
            raise VisionError('Shoe exhausted; reset after the shuffle. No cards from this observation were added.')
        for rank in added:
            self.counter.add(rank, f'OpenAI ({age:.1f}s image age)')
        if added:
            self.refresh()
        self.status.set(self.vision_gate.note)

    def read_auto(self, frame):
        if self.reader is None:
            self.reader = AutoReader()
        return self.reader.detect(frame)

    def select_table(self):
        self.refresh_displays(quiet=True)
        self.running = False
        self.invalidate()
        # Let Windows reveal the browser before taking the selection screenshot.
        self.window.withdraw()
        self.window.after(400, self.finish_table_selection)

    def finish_table_selection(self):
        try:
            monitor = self.selected_monitor()
            frame = np.array(self.capture.grab(monitor))[:, :, :3].copy()
            box = self.select(frame, 'Drag around browser video; Enter accepts, Esc cancels')
            if box:
                x, y, w, h = box
                self.region = capture_region(monitor, box)
                self.slots = []
                self.gate.reset()
                self.tracker.reset()
                self.vision_gate.reset()
                self.test_frame = None
                self.detections = []
                self.save()
                self.running = self.auto.get() and not self.counter.events and (self.backend.get() != 'OpenAI' or bool(self.api_key))
                self.update_capture_info()
                if self.counter.events:
                    self.status.set('Table selected; shoe count retained. Wait for a fresh round before pressing Start to avoid recounting existing cards.')
                elif self.auto.get() and self.backend.get() == 'OpenAI' and not self.api_key:
                    self.status.set('Table selected. Click Set API key, then Test recording or Start for OpenAI image recognition.')
                else:
                    self.status.set('Automatic reader starting. Keep King outside the table crop.' if self.running else 'Table selected. Configure manual positions or enable automatic reading.')
        except Exception as exc:
            self.status.set(f'Could not select screen: {exc}')
        finally:
            self.window.deiconify()

    def add_slot(self):
        self.running = False
        if not self.region:
            return self.status.set('Select a table first.')
        box = self.select(self.grab(), 'Select a tight upright rank-only box; exclude suit; Enter accepts')
        if box:
            self.slots.append(box)
            self.save()
            self.status.set(f'Added position {len(self.slots)}. Keep every position tightly aligned to its rank.')

    def template(self):
        self.running = False
        if not self.region:
            return self.status.set('Select a table first.')
        frame = self.grab()
        box = self.select(frame, 'Select a visible upright rank only, same padding as card positions')
        if not box:
            return
        rank = simpledialog.askstring('Rank', 'Rank: 2–10, J, Q, K, A', parent=self.window)
        if rank is None:
            return
        rank = rank.strip().upper()
        if rank not in RANKS:
            return messagebox.showerror('Invalid rank', 'Enter 2–10, J, Q, K, or A.')
        x, y, w, h = box
        patch = frame[y:y+h, x:x+w]
        if normalized(patch).std() < 12:
            return messagebox.showerror('Empty template', 'Select a clearly visible rank with contrasting strokes.')
        DATA.mkdir(exist_ok=True)
        if not cv2.imwrite(str(DATA / f'{rank}.png'), patch):
            raise OSError('Could not save template')
        self.templates[rank] = normalized(patch)
        self.status.set(f'Saved {rank}. Templates: {len(self.templates)}/13. Capture every rank before Start.')

    def toggle(self):
        if not self.running:
            if not self.region:
                return self.status.set('Click Select table and select the browser video first.')
            if not self.auto.get():
                if not self.slots:
                    return self.status.set('Add card positions for manual mode, or enable Automatic card reading.')
                missing = set(RANKS) - self.templates.keys()
                if missing:
                    return self.status.set('Missing templates: ' + ', '.join(r for r in RANKS if r in missing))
            elif self.backend.get() == 'OpenAI':
                if not self.ensure_api_key():
                    return
                try:
                    self.cloud_settings()
                except VisionError as exc:
                    return self.status.set(str(exc))
            self.test_frame = None
            self.detections = []
        self.running = not self.running
        self.invalidate()
        self.status.set('Capturing. Keep the stream visible and this app outside the captured region.' if self.running else 'Paused.')
        if not self.running and self.backend.get() == 'OpenAI':
            self.api_info.set(f'Paused after {self.api_calls} requests started. No new image requests; an in-flight request may finish and incur charges.')

    def next_round(self):
        self.running = False
        self.gate.reset()
        self.tracker.reset()
        self.vision_gate.reset()
        self.invalidate()
        self.status.set('Card tracking reset; shoe count retained. Wait for old cards to clear, then press Start.')

    def shuffle(self):
        decks = simpledialog.askinteger('New shoe', 'Starting decks (1–12):', initialvalue=self.counter.decks,
                                        minvalue=1, maxvalue=12, parent=self.window)
        if decks is not None:
            self.running = False
            self.counter = Counter(decks)
            self.gate.reset()
            self.tracker.reset()
            self.vision_gate.reset()
            self.invalidate()
            self.refresh()
            self.status.set('New shoe ready. Start counting from the beginning of the shoe.')

    def manual(self, rank):
        try:
            self.counter.add(rank)
            self.refresh()
        except ValueError as exc:
            self.status.set(str(exc))

    def undo(self):
        self.running = False
        self.invalidate()
        if self.counter.events:
            self.counter.events.pop()
        self.refresh()
        self.status.set('Paused. Last card removed; its track stays counted. Add its correct rank manually if needed.')

    def refresh(self):
        true = 'N/A' if self.counter.true is None else f'{self.counter.true:+.2f}'
        self.stats.set(f'Running {self.counter.running:+d}     True ≈ {true}     Cards {len(self.counter.events)}'
                       f'     Decks left ≈ {self.counter.remaining:.2f}')
        self.log.delete(0, tk.END)
        for i, event in enumerate(self.counter.events, 1):
            self.log.insert(tk.END, f'{i:3}  {event.rank:>2}  {event.source}')
        self.log.see(tk.END)

    def tick(self):
        try:
            if self.window.state() != 'withdrawn':
                if self.test_frame is not None and not self.running:
                    frame = self.test_frame.copy()
                else:
                    frame = self.grab() if self.region else np.array(self.capture.grab(self.selected_monitor()))[:, :, :3].copy()
                if self.future is not None and self.future.done():
                    pending, generation, captured_at = self.future, self.pending_generation, self.pending_time
                    backend = getattr(self, 'pending_backend', 'Local OCR')
                    task = getattr(self, 'pending_task', 'live')
                    self.future = None
                    try:
                        detected = pending.result()
                    except Exception as exc:
                        if generation == self.generation and (self.running or task == 'test'):
                            self.running = False
                            if backend == 'OpenAI':
                                self.status.set(str(exc) if isinstance(exc, VisionError) else 'OpenAI reader failed. No count changed; check setup and try again.')
                                self.api_info.set(f'OpenAI: {self.api_calls} requests started. Last request failed; no automatic retry. API usage may still be billed.')
                            else:
                                self.status.set(f'Automatic reader unavailable: {exc}. Run pip install -r requirements.txt, then restart.')
                    else:
                        if backend == 'OpenAI' and generation == self.generation and (task == 'test' or (self.running and self.auto.get())):
                            self.consume_cloud(detected, task, captured_at)
                        elif backend != 'OpenAI' and self.running and self.auto.get() and generation == self.generation:
                            self.detections = detected
                            for detection in self.tracker.update(detected, captured_at):
                                self.counter.add(detection.rank, f'auto OCR ({detection.score:.2f})')
                                self.refresh()
                            readable = sum(bool(d.rank) for d in detected)
                            if not readable:
                                self.status.set(f'No card ranks recognized ({len(detected)} candidate shapes). The displayed count is unverified and may be incomplete. Crop to the main tabletop; small, tilted or overlapping cards may require a different detector.')
                            else:
                                self.status.set(f'Tracking {readable} readable ranks in {len(detected)} candidate shapes. Count includes recognized cards only; verify that every exposed card is labeled. Reset at shuffle.')
                if self.running and self.auto.get() and self.region and self.future is None:
                    if self.backend.get() == 'OpenAI':
                        if time.monotonic() >= self.next_api_at:
                            self.submit_cloud(frame)
                    else:
                        self.pending_generation, self.pending_time = self.generation, time.monotonic()
                        self.pending_backend, self.pending_task = 'Local OCR', 'live'
                        self.future = self.worker.submit(self.read_auto, frame.copy())
                if self.auto.get() and (self.region or self.test_frame is not None):
                    for detection in self.detections:
                        x, y, w, h = detection.box
                        color = (50, 200, 50) if detection.rank else (0, 180, 255)
                        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                        label = f'{detection.rank or "?"} AI' if self.backend.get() == 'OpenAI' else f'{detection.rank or "?"} {detection.score:.2f}'
                        cv2.putText(frame, label, (x, max(16, y-5)),
                                    cv2.FONT_HERSHEY_SIMPLEX, .6, color, 2)
                try:
                    threshold = float(self.threshold.get())
                    if not 0.7 <= threshold <= 0.99:
                        raise ValueError('Match threshold must be 0.70–0.99')
                except (ValueError, tk.TclError):
                    self.running = False
                    threshold = 0.90
                    self.status.set('Enter a match threshold from 0.70 to 0.99.')
                for i, (x, y, w, h) in enumerate(self.slots if self.region and not self.auto.get() else []):
                    rank, score = recognize(frame[y:y+h, x:x+w], self.templates, threshold)
                    if self.running:
                        emitted = self.gate.observe(i, rank)
                        if emitted:
                            self.counter.add(emitted, f'position {i+1} ({score:.2f})')
                            self.refresh()
                    color = (70, 210, 70) if i in self.gate.locked else (0, 180, 255)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                    cv2.putText(frame, f'{i+1}:{rank or "?"} {score:.2f}', (x, max(15, y-5)),
                                cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1)
                rgb = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                rgb.thumbnail((1000, 420))
                self.photo = ImageTk.PhotoImage(rgb)
                self.preview.configure(image=self.photo)
        except Exception as exc:
            self.running = False
            self.status.set(str(exc) if isinstance(exc, VisionError) else f'Capture paused: {exc}')
        self.window.after(200, self.tick)

    def save(self):
        DATA.mkdir(exist_ok=True)
        (DATA / 'layout.json').write_text(json.dumps(dict(region=self.region, slots=self.slots,
                                                       monitor=self.selected_monitor(), monitor_layout=self.monitors)), encoding='utf-8')

    def load(self):
        path = DATA / 'layout.json'
        try:
            if path.exists():
                layout = json.loads(path.read_text(encoding='utf-8'))
                region = layout['region']
                slots = layout['slots']
                saved_monitor = layout.get('monitor')
                if layout.get('monitor_layout', self.monitors) != self.monitors:
                    raise ValueError('Display arrangement changed; choose the video screen and Select table again')
                if saved_monitor is None and region:
                    saved_monitor = next((m for m in self.monitors if contains(m, region)), None)
                if saved_monitor is not None:
                    if saved_monitor not in self.monitors:
                        raise ValueError('Saved screen is disconnected; select another screen')
                    self.monitor_choice.current(self.monitors.index(saved_monitor))
                if region:
                    if not contains(self.selected_monitor(), region):
                        raise ValueError('Saved crop is outside the selected screen')
                    for x, y, w, h in slots:
                        if min(x, y) < 0 or min(w, h) <= 0 or x+w > region['width'] or y+h > region['height']:
                            raise ValueError('Invalid card position')
                    self.region, self.slots = region, slots
            for rank in RANKS:
                template = cv2.imread(str(DATA / f'{rank}.png')) if (DATA / f'{rank}.png').exists() else None
                if template is not None:
                    self.templates[rank] = normalized(template)
        except (ValueError, KeyError, TypeError) as exc:
            self.region, self.slots = None, []
            self.status.set(f'Calibration must be recreated: {exc}')

    def export(self):
        filename = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if filename:
            with open(filename, 'w', newline='', encoding='utf-8') as output:
                writer = csv.writer(output)
                writer.writerow(['card', 'rank', 'source'])
                writer.writerows((i, e.rank, e.source) for i, e in enumerate(self.counter.events, 1))

    def close(self):
        self.running = False
        self.api_key = ''
        self.worker.shutdown(wait=False, cancel_futures=True)
        self.capture.close()
        self.window.destroy()


if __name__ == '__main__':
    enable_dpi_awareness()
    App(tk.Tk()).window.mainloop()
