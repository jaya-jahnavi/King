import json
import unittest
from unittest.mock import patch
import urllib.error

from automatic import Detection
from openai_vision import OpenAIReader, Observation, VisionError, VisionGate, validate_observation, ENDPOINT


def observation(ranks=(), state='cards', complete=True):
    return Observation(state, complete, [Detection((10+i*20, 10, 15, 30), rank) for i, rank in enumerate(ranks)])


class VisionGateTests(unittest.TestCase):
    def test_two_reads_add_each_physical_rank_once(self):
        gate = VisionGate()
        frame = observation(['2', '2', 'A'])
        self.assertEqual(gate.update(frame, 0), [])
        self.assertCountEqual(gate.update(frame, 2), ['2', '2', 'A'])
        self.assertEqual(gate.update(frame, 4), [])
        frame.cards.reverse()
        self.assertEqual(gate.update(frame, 6), [])

    def test_hit_adds_only_new_card(self):
        gate = VisionGate()
        for now in (0, 2):
            gate.update(observation(['K', '6']), now)
        self.assertFalse(gate.update(observation(['K', '6', '2']), 4))
        self.assertEqual(gate.update(observation(['K', '6', '2']), 6), ['2'])

    def test_uncertainty_cannot_clear_or_add(self):
        gate = VisionGate()
        for now in (0, 2):
            gate.update(observation(['K']), now)
        gate.update(observation([], state='unclear', complete=False), 10)
        gate.update(observation([None], complete=False), 20)
        self.assertEqual(gate.update(observation(['K']), 30), [])
        self.assertEqual(gate.counted['K'], 1)

    def test_rank_correction_does_not_add_a_phantom_card(self):
        gate = VisionGate()
        for now in (0, 2):
            gate.update(observation(['K', '2']), now)
        for now in (4, 6, 8):
            self.assertFalse(gate.update(observation(['6', '2']), now))
        self.assertIn('disappeared or changed', gate.note)

    def test_clear_table_requires_repeated_observations_and_time(self):
        gate = VisionGate()
        for now in (0, 2):
            gate.update(observation(['K']), now)
        gate.update(observation([], 'empty'), 3)
        gate.update(observation([], 'empty'), 5)
        self.assertTrue(gate.counted)
        gate.update(observation([], 'empty'), 7)
        self.assertFalse(gate.counted)
        gate.update(observation(['K']), 9)
        self.assertEqual(gate.update(observation(['K']), 11), ['K'])


class ValidationTests(unittest.TestCase):
    def card(self, rank='K'):
        return dict(rank=rank, suit='S', box=dict(x=100, y=200, width=200, height=300))

    def test_normalized_box_maps_to_original_frame(self):
        result = validate_observation(dict(table_state='cards', complete=True, cards=[self.card()]), 1000, 500)
        self.assertEqual(result.cards[0].box, (100, 100, 200, 150))

    def test_unknown_cards_must_be_incomplete(self):
        data = dict(table_state='cards', complete=True, cards=[self.card(None)])
        with self.assertRaises(VisionError):
            validate_observation(data, 1000, 500)
        data['complete'] = False
        self.assertIsNone(validate_observation(data, 1000, 500).cards[0].rank)

    def test_contradictory_empty_or_bad_boxes_are_rejected(self):
        data = dict(table_state='empty', complete=True, cards=[self.card()])
        with self.assertRaises(VisionError):
            validate_observation(data, 1000, 500)
        data['table_state'] = 'cards'
        data['cards'][0]['box']['x'] = 950
        with self.assertRaises(VisionError):
            validate_observation(data, 1000, 500)


class TransportTests(unittest.TestCase):
    def frame(self):
        import numpy as np
        return np.zeros((100, 200, 3), dtype=np.uint8)

    @patch('openai_vision.urllib.request.urlopen')
    def test_request_is_official_cropped_image_and_strict_json(self, urlopen):
        data = dict(table_state='empty', complete=True, cards=[])
        response = dict(status='completed', output=[dict(type='message', content=[dict(type='output_text', text=json.dumps(data))])],
                        usage=dict(input_tokens=100, output_tokens=30))
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(response).encode()
        result = OpenAIReader('unit-test-key').read(self.frame())
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertFalse(payload['store'])
        self.assertTrue(payload['text']['format']['strict'])
        self.assertNotIn('unit-test-key', request.data.decode())
        self.assertTrue(payload['input'][1]['content'][1]['image_url'].startswith('data:image/jpeg;base64,'))
        self.assertEqual((result.input_tokens, result.output_tokens), (100, 30))
        self.assertEqual(urlopen.call_count, 1)

    @patch('openai_vision.urllib.request.urlopen')
    def test_auth_error_never_exposes_key_or_auto_retries(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(ENDPOINT, 401, 'unit-test-key in upstream error', None, None)
        with self.assertRaises(VisionError) as error:
            OpenAIReader('unit-test-key').read(self.frame())
        self.assertNotIn('unit-test-key', str(error.exception))
        self.assertIn('key rejected', str(error.exception))
        self.assertEqual(urlopen.call_count, 1)

    @patch('openai_vision.urllib.request.urlopen')
    def test_refusal_never_becomes_an_empty_table(self, urlopen):
        response = dict(status='completed', output=[dict(type='message', content=[dict(type='refusal', refusal='declined')])])
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(response).encode()
        with self.assertRaises(VisionError):
            OpenAIReader('unit-test-key').read(self.frame())
