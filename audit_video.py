"""Reproduce recognition failures on a recording without a live screen.

python audit_video.py recording.mp4 --region 680 680 640 210 --output audit.json
The report lists observations, not a verified shoe count.
"""
import argparse
import json
from pathlib import Path
import cv2
from automatic import AutoReader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--region', nargs=4, type=int, metavar=('X', 'Y', 'WIDTH', 'HEIGHT'))
    parser.add_argument('--samples', type=int, default=12)
    parser.add_argument('--output', type=Path, default=Path('recognition-audit.json'))
    args = parser.parse_args()
    if args.samples < 2:
        parser.error('--samples must be at least 2')
    capture = cv2.VideoCapture(str(args.video))
    try:
        if not capture.isOpened():
            parser.error('Cannot open video')
        fps, frames = capture.get(cv2.CAP_PROP_FPS), capture.get(cv2.CAP_PROP_FRAME_COUNT)
        width, height = int(capture.get(3)), int(capture.get(4))
        if fps <= 0 or frames <= 0:
            parser.error('Video has no usable timing metadata')
        if args.region:
            x, y, w, h = args.region
            if min(x, y) < 0 or min(w, h) <= 0 or x+w > width or y+h > height:
                parser.error('--region must be inside the recording')
        duration = frames/fps
        reader = AutoReader()
        rows = []
        for i in range(args.samples):
            seconds = max(0, duration-1/fps)*i/(args.samples-1)
            capture.set(cv2.CAP_PROP_POS_MSEC, seconds*1000)
            ok, frame = capture.read()
            if not ok:
                rows.append({'seconds': round(seconds, 3), 'error': 'Frame unavailable'})
                continue
            if args.region:
                frame = frame[y:y+h, x:x+w]
            detections = reader.detect(frame)
            row = {'seconds': round(seconds, 3), 'candidate_shapes': len(detections),
                   'readable_ranks': [{'rank': d.rank, 'score': round(d.score, 4), 'box': list(d.box)}
                                      for d in detections if d.rank]}
            rows.append(row)
            print(f'{seconds:6.1f}s: {len(detections)} shapes, {len(row["readable_ranks"])} readable ranks', flush=True)
        report = {'duration_seconds': duration, 'resolution': [width, height], 'region': args.region,
                  'warning': 'Sampled observations only. Repeated frames can contain the same cards. This is not a shoe count or an accuracy score.',
                  'samples': rows}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f'Saved {args.output}')
    finally:
        capture.release()


if __name__ == '__main__':
    main()
