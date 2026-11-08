"""King: calibrated screen capture card-counting prototype. Run: python app.py."""
import csv
import ctypes
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

import cv2
import mss
import numpy as np
from PIL import Image, ImageTk

from counting import Counter, RoundGate, RANKS

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
        self.region = None
        self.slots = []
        self.templates = {}
        self.counter = Counter()
        self.gate = RoundGate()
        self.running = False
        self.status = tk.StringVar(value='Select table, add card positions, then calibrate rank templates.')
        self.stats = tk.StringVar()
        self.threshold = tk.DoubleVar(value=0.90)
        window.title('King • Live card count prototype')
        window.geometry('1060x820')
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
        ttk.Label(controls, text=' Match threshold:').pack(side='left')
        ttk.Spinbox(controls, from_=0.7, to=0.99, increment=0.01, width=5, textvariable=self.threshold).pack(side='left')
        self.log = tk.Listbox(window, height=8, font=('Consolas', 10))
        self.log.pack(fill='both', expand=True, padx=12, pady=8)
        ttk.Label(window, text='Fixed layout prototype • Pause before calibration • Next round only after old cards clear',
                  padding=8).pack()
        self.load()
        self.refresh()
        window.protocol('WM_DELETE_WINDOW', self.close)
        window.after(200, self.tick)

    def grab(self):
        return np.array(self.capture.grab(self.region))[:, :, :3].copy()

    def select(self, frame, title):
        box = cv2.selectROI(title, frame, showCrosshair=True, fromCenter=False)
        cv2.destroyAllWindows()
        return tuple(map(int, box)) if box[2] and box[3] else None

    def select_table(self):
        if self.counter.events:
            messagebox.showinfo('New shoe needed', 'Use Shuffle / New shoe before changing the table region.')
            return
        self.running = False
        monitor = self.capture.monitors[0]
        frame = np.array(self.capture.grab(monitor))[:, :, :3].copy()
        box = self.select(frame, 'Select only the video table; Enter accepts, Esc cancels')
        if box:
            x, y, w, h = box
            self.region = dict(left=monitor['left'] + x, top=monitor['top'] + y, width=w, height=h)
            self.slots = []
            self.gate.reset()
            self.save()
            self.status.set('Table selected. Add one tight rank-only position for each possible card location.')

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
            if not self.region or not self.slots:
                return self.status.set('Select a table and at least one card position first.')
            missing = set(RANKS) - self.templates.keys()
            if missing:
                return self.status.set('Missing templates: ' + ', '.join(r for r in RANKS if r in missing))
        self.running = not self.running
        self.status.set('Capturing. Keep the stream visible and this app outside the captured region.' if self.running else 'Paused.')

    def next_round(self):
        self.running = False
        self.gate.reset()
        self.status.set('Round positions reset; count retained. Wait for old cards to clear, then press Start.')

    def shuffle(self):
        decks = simpledialog.askinteger('New shoe', 'Starting decks (1–12):', initialvalue=self.counter.decks,
                                        minvalue=1, maxvalue=12, parent=self.window)
        if decks is not None:
            self.running = False
            self.counter = Counter(decks)
            self.gate.reset()
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
        if self.counter.events:
            self.counter.events.pop()
        self.refresh()
        self.status.set('Paused. Last card removed; position stays locked. Add its correct rank manually if needed.')

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
            if self.region:
                frame = self.grab()
                try:
                    threshold = float(self.threshold.get())
                    if not 0.7 <= threshold <= 0.99:
                        raise ValueError('Match threshold must be 0.70–0.99')
                except (ValueError, tk.TclError):
                    self.running = False
                    threshold = 0.90
                    self.status.set('Enter a match threshold from 0.70 to 0.99.')
                for i, (x, y, w, h) in enumerate(self.slots):
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
            self.status.set(f'Capture paused: {exc}')
        self.window.after(200, self.tick)

    def save(self):
        DATA.mkdir(exist_ok=True)
        (DATA / 'layout.json').write_text(json.dumps(dict(region=self.region, slots=self.slots)), encoding='utf-8')

    def load(self):
        path = DATA / 'layout.json'
        try:
            if path.exists():
                layout = json.loads(path.read_text(encoding='utf-8'))
                region = layout['region']
                slots = layout['slots']
                if not region or region['width'] <= 0 or region['height'] <= 0:
                    raise ValueError('Invalid region')
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
        self.capture.close()
        self.window.destroy()


if __name__ == '__main__':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass
    App(tk.Tk()).window.mainloop()
