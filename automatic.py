"""Local card-shaped region detection, OCR and temporal tracking."""
from dataclasses import dataclass
import math

RANKS = {'2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'}


def parse_rank(text):
    text = str(text).strip().upper().replace(' ', '')
    for suit in '♠♥♦♣':
        text = text.replace(suit, '')
    return text if text in RANKS else None


@dataclass
class Detection:
    box: tuple
    rank: str | None
    score: float = 0.0


@dataclass
class Track:
    box: tuple
    rank: str | None = None
    hits: int = 0
    counted: bool = False


class AutoTracker:
    def __init__(self, stable=3, clear_seconds=3.0):
        self.stable = stable
        self.clear_seconds = clear_seconds
        self.reset()

    def reset(self):
        self.tracks = []
        self.empty_since = None
        self.round_ended = False
        self.clear_confirmed = False

    def update(self, detections, now):
        self.round_ended = False
        if not detections:
            for track in self.tracks:
                if not track.counted:
                    track.hits = 0
            if self.empty_since is None:
                self.empty_since = now
            if now - self.empty_since >= self.clear_seconds:
                self.tracks.clear()
                self.round_ended = not self.clear_confirmed
                self.clear_confirmed = True
            return []
        self.empty_since = None
        self.clear_confirmed = False
        # One-to-one nearest association: two identical ranks are distinct cards.
        pairs = []
        for di, detection in enumerate(detections):
            x, y, w, h = detection.box
            for ti, track in enumerate(self.tracks):
                tx, ty, tw, th = track.box
                distance = math.hypot(x+w/2-tx-tw/2, y+h/2-ty-th/2)
                limit = max(w, h, tw, th) * 0.75
                if distance < limit and 0.5 < (w*h)/(tw*th) < 2:
                    pairs.append((distance, di, ti))
        assigned, used = {}, set()
        for _, di, ti in sorted(pairs):
            if di not in assigned and ti not in used:
                assigned[di] = ti
                used.add(ti)
        for ti, track in enumerate(self.tracks):
            if ti not in used and not track.counted:
                track.hits = 0
        emitted = []
        for di, detection in enumerate(detections):
            if di not in assigned:
                self.tracks.append(Track(detection.box))
                assigned[di] = len(self.tracks)-1
            track = self.tracks[assigned[di]]
            track.box = detection.box
            if track.counted:
                continue
            track.hits = track.hits+1 if detection.rank and track.rank == detection.rank else int(bool(detection.rank))
            track.rank = detection.rank
            if track.hits >= self.stable:
                track.counted = True
                emitted.append(detection)
        return emitted


class AutoReader:
    def __init__(self):
        from rapidocr import RapidOCR
        from pathlib import Path
        self.ocr = RapidOCR(params={
            'Global.model_root_dir': str(Path(__file__).resolve().parent / 'models'),
            'EngineConfig.onnxruntime.intra_op_num_threads': 2,
            'EngineConfig.onnxruntime.inter_op_num_threads': 1,
        })

    def detect(self, frame):
        import cv2
        import numpy as np
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([0, 0, 155]), np.array([179, 105, 255]))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections = []
        area = frame.shape[0]*frame.shape[1]
        for contour in sorted(contours, key=cv2.contourArea, reverse=True):
            x, y, w, h = cv2.boundingRect(contour)
            if min(w, h) < 24 or not 0.001 < w*h/area < 0.22:
                continue
            rect = cv2.minAreaRect(contour)
            rw, rh = rect[1]
            if min(rw, rh) < 20 or not 0.42 < min(rw, rh)/max(rw, rh) < 0.86:
                continue
            if cv2.contourArea(contour)/(rw*rh) < 0.75:
                continue
            # Rectify tilted, mostly exposed white cards to a common portrait crop.
            points = cv2.boxPoints(rect).astype(np.float32)
            ordered = np.zeros((4, 2), dtype=np.float32)
            sums, diffs = points.sum(axis=1), np.diff(points, axis=1).ravel()
            ordered[0], ordered[2] = points[sums.argmin()], points[sums.argmax()]
            ordered[1], ordered[3] = points[diffs.argmin()], points[diffs.argmax()]
            if len(np.unique(ordered, axis=0)) != 4:
                continue
            if np.linalg.norm(ordered[1]-ordered[0]) > np.linalg.norm(ordered[3]-ordered[0]):
                ordered = np.roll(ordered, -1, axis=0)
            target = np.float32([[0, 0], [159, 0], [159, 223], [0, 223]])
            card = cv2.warpPerspective(frame, cv2.getPerspectiveTransform(ordered, target), (160, 224))
            # Read only the upper-left rank, avoiding center pips and duplicate corners.
            corner = card[5:68, 4:65]
            result = self.ocr(corner, use_det=True, use_cls=False, use_rec=True)
            texts = result.txts if result.txts is not None else []
            scores = result.scores if result.scores is not None else []
            choices = [(parse_rank(text), float(score)) for text, score in zip(texts, scores)]
            choices = [(r, s) for r, s in choices if r and s >= 0.85]
            rank, score = max(choices, key=lambda item: item[1]) if choices else (None, 0.0)
            detections.append(Detection((x, y, w, h), rank, score))
            if len(detections) >= 32:
                break
        return detections
