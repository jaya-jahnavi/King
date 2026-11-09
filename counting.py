"""Counting state independent of screen capture and recognition."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

RANKS = ('2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A')


def card_value(rank):
    return 1 if rank in RANKS[:5] else -1 if rank in RANKS[8:] else 0


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@dataclass
class Event:
    rank: str
    source: str
    round_number: int = 1
    recorded_at: str = field(default_factory=utc_now)


class Counter:
    def __init__(self, decks=6):
        if not 1 <= decks <= 12:
            raise ValueError('Deck count must be between 1 and 12')
        self.decks = decks
        self.events = []
        self.round_number = 1
        self.shoe_number = 1
        self.archives = []

    def add(self, rank, source='manual'):
        return self.add_to_round(self.shoe_number, self.round_number, rank, source)

    def add_to_round(self, shoe_number, round_number, rank, source='manual missed card'):
        if not isinstance(rank, str):
            raise ValueError('Unknown card rank')
        rank = rank.strip().upper()
        if rank not in RANKS:
            raise ValueError('Unknown card rank')
        if type(shoe_number) is not int or type(round_number) is not int:
            raise ValueError('Choose an existing shoe and round')
        current = shoe_number == self.shoe_number
        shoe = self._shoe_data() if current else next((s for s in self.archives if s['shoe_number'] == shoe_number), None)
        if shoe is None or not 1 <= round_number <= shoe['round_number']:
            raise ValueError('Choose an existing shoe and round')
        if not (current and round_number == self.round_number) and not any(e['round_number'] == round_number for e in shoe['events']):
            raise ValueError('That round is not in the saved history')
        if len(shoe['events']) >= shoe['decks'] * 52:
            raise ValueError('That shoe already contains its maximum number of cards')
        event = Event(rank, source, round_number)
        if current:
            position = next((i for i,e in enumerate(self.events) if e.round_number > round_number), len(self.events))
            self.events.insert(position, event)
        else:
            position = next((i for i,e in enumerate(shoe['events']) if e['round_number'] > round_number), len(shoe['events']))
            shoe['events'].insert(position, asdict(event))
        return event

    @property
    def round_cards(self):
        return [event.rank for event in self.events if event.round_number == self.round_number]

    @property
    def round_count(self):
        return sum(card_value(rank) for rank in self.round_cards)

    def finish_round(self):
        if not self.round_cards:
            return False
        self.round_number += 1
        return True

    def _shoe_data(self):
        return dict(shoe_number=self.shoe_number, decks=self.decks, round_number=self.round_number,
                    events=[asdict(event) for event in self.events])

    def new_shoe(self, decks):
        if not 1 <= decks <= 12:
            raise ValueError('Deck count must be between 1 and 12')
        if self.events:
            self.archives.append(self._shoe_data())
        self.shoe_number += 1
        self.decks, self.events, self.round_number = decks, [], 1

    def summaries(self):
        rows = []
        for shoe in [*self.archives, self._shoe_data()]:
            running = 0
            for number in range(1, shoe['round_number']+1):
                events = [event for event in shoe['events'] if event['round_number'] == number]
                current = shoe['shoe_number'] == self.shoe_number and number == self.round_number
                if not events and not current:
                    continue
                cards = [event['rank'] for event in events]
                delta = sum(card_value(rank) for rank in cards)
                running += delta
                rows.append(dict(shoe=shoe['shoe_number'], round=number, cards=cards,
                                 card_count=len(cards), round_count=delta, running_count=running,
                                 state=('In progress' if cards else 'Waiting') if current else 'Saved',
                                 first_card_at=events[0]['recorded_at'] if events else '',
                                 last_card_at=events[-1]['recorded_at'] if events else ''))
        return rows

    def to_dict(self):
        return dict(version=1, current=self._shoe_data(), archives=self.archives)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError('Unsupported history format')
        def validate(shoe):
            if not isinstance(shoe, dict):
                raise ValueError('Invalid shoe history')
            for key in ('shoe_number', 'decks', 'round_number'):
                if type(shoe.get(key)) is not int or shoe[key] < 1:
                    raise ValueError('Invalid shoe/round number')
            if shoe['decks'] > 12 or shoe['round_number'] > 1000:
                raise ValueError('Invalid shoe size or round count')
            events = shoe.get('events')
            if not isinstance(events, list) or len(events) > shoe['decks']*52:
                raise ValueError('Invalid card history')
            previous = 1
            for event in events:
                if (not isinstance(event, dict) or event.get('rank') not in RANKS
                    or not isinstance(event.get('source'), str) or not isinstance(event.get('recorded_at'), str)
                    or type(event.get('round_number')) is not int
                    or not previous <= event['round_number'] <= shoe['round_number']):
                    raise ValueError('Invalid card event')
                previous = event['round_number']
            return shoe
        current = validate(data.get('current'))
        archives = data.get('archives')
        if not isinstance(archives, list):
            raise ValueError('Invalid archived history')
        previous = 0
        for shoe in archives:
            validate(shoe)
            if not previous < shoe['shoe_number'] < current['shoe_number']:
                raise ValueError('Invalid archived shoe order')
            previous = shoe['shoe_number']
        result = cls(current['decks'])
        result.shoe_number, result.round_number = current['shoe_number'], current['round_number']
        result.events = [Event(**event) for event in current['events']]
        result.archives = archives
        return result

    @property
    def running(self):
        return sum(card_value(event.rank) for event in self.events)

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
