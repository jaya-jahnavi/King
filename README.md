# King — live screen card-counting prototype

A local Python desktop tool for a visible browser video or screen stream. Captures only the selected table region, recognizes calibrated ranks in fixed positions, and displays a Hi-Lo running count and estimated true count. No video is uploaded.

## Run on Windows

Requires Python 3.11 or newer with Tkinter (included in the standard python.org Windows installer).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## Calibrate your stream

1. Open the stream at a fixed browser zoom and video size. Keep it visible, with the King window outside the table region. Screen capture cannot see a hidden or minimized tab.
2. Click **Select table**. Drag around the video table on the captured desktop image, then press Enter. Escape cancels.
3. Click **Add card position** for each possible dealt-card location, including dealer cards. Select a tight box containing only the upright rank, excluding its suit. Each position represents one physical card in that round. Configure enough positions for extra cards, splits and hits if the layout allows it.
4. Click **Save rank template**. Select a visible rank with the same padding as the position boxes and label it. Repeat for all 13 ranks, including 10. Calibration is saved locally. Use sample footage or paused frames to obtain all ranks.
5. Click **Shuffle / New shoe** and enter the starting number of decks. Start at the beginning of a shoe for a meaningful count.
6. Click **Start / Pause**. Recognition requires four consecutive matching observations (nominally about 0.8 seconds; processing can increase this). Green positions have already counted; orange positions are waiting. Scores show image similarity, not calibrated probabilities.
7. After each round, click **Next round**, wait until all old cards clear, then press **Start**. This retains the shoe count and rearms positions. Resetting while old cards remain would count them again.
8. At a shuffle, use **Shuffle / New shoe**. Correct a recent error with **Undo last**, then the correct manual rank. Undo pauses capture and keeps that position locked. Manual rank buttons add a card; do not add cards already recognized automatically.

Running count: 2–6 = +1; 7–9 = 0; 10/J/Q/K/A = −1. Estimated decks remaining = starting decks − observed cards / 52. True count = running count / estimated decks remaining; N/A at exhaustion. Counts and history are held in memory until closing; export CSV to preserve card history. Calibration survives restarts.

## Scope and limitations

This is a calibrated fixed-layout prototype, not a trained general-purpose card detector. It does not automatically locate cards, follow moving cards, detect rounds or shuffles, or recognize hidden cards. Rank templates are grayscale and normalized; rotated cards, changing fonts, camera cuts, overlapping cards, rank positions moving within a hand, and compression can cause errors. A slot can emit once per round, so positions must not be reused for different cards during that round. If your stream moves cards around, a detector and identity tracker are the next development step.

All exposed cards need to be observed exactly once, including dealer cards. Unseen burns, joining mid-shoe, missed cards, manual duplicates, or continuous shuffling make the true-count estimate unreliable. No betting recommendations or game automation are included. No accuracy has been established on a real stream yet; validate on recorded footage with a manually annotated card sequence first. Browser video protected from capture may appear black.

To replace the layout, reset the shoe and select the table again. Existing templates remain available; recapture them when appearance changes. Local calibration images and CSV exports are excluded from Git.

## Checks

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app.py counting.py
```

These check count arithmetic, exhausted shoes, temporal agreement and duplicate prevention. They do not establish real-stream recognition accuracy.

Capture and image matching follow the [MSS examples](https://python-mss.readthedocs.io/stable/examples.html) and [OpenCV template matching documentation](https://docs.opencv.org/3.4.19/d4/dc6/tutorial_py_template_matching.html).
