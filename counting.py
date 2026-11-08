"""Counting state independent of screen capture and recognition."""
from dataclasses import dataclass

RANKS = ('2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A')


@dataclass
class Event:
    rank: str
    source: str


class Counter:
    def __init__(self, decks=6):
        if not 1 <= decks <= 12:
            raise ValueError('Deck count must be between 1 and 12')
        self.decks = decks
        self.events = []

    def add(self, rank, source='manual'):
        rank = rank.upper()
        if rank not in RANKS:
            raise ValueError('Unknown card rank')
        if len(self.events) >= self.decks * 52:
            raise ValueError('Shoe exhausted; reset after the shuffle')
        self.events.append(Event(rank, source))

    @property
    def running(self):
        return sum(1 if e.rank in RANKS[:5] else -1 if e.rank in RANKS[8:] else 0
                   for e in self.events)

    @property
    def remaining(self):
        return self.decks - len(self.events) / 52

    @property
    def true(self):
        return self.running / self.remaining if self.remaining > 0 else None


class RoundGate:
    """Each configured card position can emit once until explicit round reset.

    Missing detections never rearm a position: occlusion must not count it again.
    """
    def __init__(self, stable_frames=4):
        self.stable_frames = stable_frames
        self.reset()

    def reset(self):
        self.locked = set()
        self.pending = {}

    def observe(self, slot, rank):
        if slot in self.locked:
            return None
        if rank is None:
            self.pending.pop(slot, None)
            return None
        previous, frames = self.pending.get(slot, (None, 0))
        frames = frames + 1 if previous == rank else 1
        self.pending[slot] = (rank, frames)
        if frames >= self.stable_frames:
            self.locked.add(slot)
            return rank
        return None
