# King — automatic live screen card counting

A local Python desktop tool for a visible browser video or screen stream. Automatic mode detects mostly exposed white cards, reads their corner ranks with RapidOCR, and tracks them to display a Hi-Lo running count and estimated true count. No video is uploaded. OCR models download on first use and inference runs locally.

## Run on Windows

Requires Python 3.11 or newer with Tkinter (included in the standard python.org Windows installer).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## Automatic mode (default)

1. Run the installation command above again to install the new OCR dependencies. The first recognition may take longer while two OCR models download (about 30 MB total). Keep internet available for this first download; models are cached in `models/`.
2. Keep the browser video visible. Choose its screen and click **Select table**. Drag tightly around the playing surface, excluding browser controls, scores, labels, and the King window. Press Enter or click **Use selected area**.
3. Counting starts automatically after selection. No card positions or rank templates are required. Green boxes show readable ranks and orange boxes show card-shaped regions without a recognized rank. Three agreeing OCR observations count a track once. The status line shows how many shapes and ranks were found; OCR runs on a worker thread so the preview remains responsive.
4. Start at the beginning of a shoe. Use **Shuffle / New shoe** to enter the starting decks (default six), then **Start / Pause** to resume. A saved region resumes automatic mode at launch with a fresh count, so reset the shoe appropriately rather than treating a restarted app as continued history.
5. The tracker rearms automatically after no card-shaped regions have been seen for at least three seconds. Short occlusions retain counted tracks. If the table never clears, pause and use **Next round** after old cards disappear, then resume. Only use it when a new round actually begins.
6. At every shuffle, reset the shoe manually. **Undo last** pauses and removes the most recent event while retaining the track's counted state; use a manual rank button to replace it, then resume. CSV export preserves history; counts otherwise stay in memory only.

This automatic detector is an experimental white-card contour and OCR pipeline, not a trained playing-card object detector. It expects mostly exposed white card faces with contrasting rank markings in their upper-left corner. It rectifies moderate rotation, but overlaps, severe perspective, colored card faces, small/blurred ranks, changing camera shots, and different corner layouts can prevent recognition. Closely crossing cards or large sudden movements can confuse identity tracking. A camera cut or detection failure lasting three seconds can be mistaken for a cleared table and cause recounting. UI rectangles can be mistaken for cards, so crop to the table and verify the labeled boxes. OCR confidence is a model score, not an accuracy guarantee. Real-stream accuracy has not been established.

## Optional manual calibration mode

Disable **Automatic card reading** to use the older fixed-position template mode. Its controls remain available as an alternative for a consistent layout.

1. Open the stream at a fixed browser zoom and video size. Keep it visible, with the King window outside the table region. Screen capture cannot see a hidden or minimized tab.
2. A live screen preview appears immediately, before calibration. Choose the browser's screen in the **Screen** dropdown, then click **Select table**. King temporarily hides itself so the browser is visible in the selection screenshot. Drag around the video table on the fitted desktop image, then press Enter. Escape cancels. After selection, the preview uses that saved crop; choose Select table again to change it. Keep King outside that crop.
3. Click **Add card position** for each possible dealt-card location, including dealer cards. Select a tight box containing only the upright rank, excluding its suit. Each position represents one physical card in that round. Configure enough positions for extra cards, splits and hits if the layout allows it.
4. Click **Save rank template**. Select a visible rank with the same padding as the position boxes and label it. Repeat for all 13 ranks, including 10. Calibration is saved locally. Use sample footage or paused frames to obtain all ranks.
5. Click **Shuffle / New shoe** and enter the starting number of decks. Start at the beginning of a shoe for a meaningful count.
6. Click **Start / Pause**. Recognition requires four consecutive matching observations (nominally about 0.8 seconds; processing can increase this). Green positions have already counted; orange positions are waiting. Scores show image similarity, not calibrated probabilities.
7. After each round, click **Next round**, wait until all old cards clear, then press **Start**. This retains the shoe count and rearms positions. Resetting while old cards remain would count them again.
8. At a shuffle, use **Shuffle / New shoe**. Correct a recent error with **Undo last**, then the correct manual rank. Undo pauses capture and keeps that position locked. Manual rank buttons add a card; do not add cards already recognized automatically.

Running count: 2–6 = +1; 7–9 = 0; 10/J/Q/K/A = −1. Estimated decks remaining = starting decks − observed cards / 52. True count = running count / estimated decks remaining; N/A at exhaustion. Counts and history are held in memory until closing; export CSV to preserve card history. Calibration survives restarts.

## Scope and limitations

In manual template mode, each position can emit once per round, so positions must not be reused for different cards during that round. Templates and position selections are unnecessary in automatic mode. Neither mode recognizes hidden cards or detects shuffles.

All exposed cards need to be observed exactly once, including dealer cards. Unseen burns, joining mid-shoe, missed cards, manual duplicates, or continuous shuffling make the true-count estimate unreliable. No betting recommendations or game automation are included. No accuracy has been established on a real stream yet; validate on recorded footage with a manually annotated card sequence first. Browser video protected from capture may appear black.

To replace the layout, reset the shoe and select the table again. Existing templates remain available; recapture them when appearance changes. Local calibration images and CSV exports are excluded from Git.

## Checks

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app.py counting.py
```

To also test actual OCR inference on all 13 generated upright white cards:

```powershell
$env:KING_TEST_OCR='1'
python -m unittest discover -s tests -v
```

Validation during development: all nine logic tests passed, all 13 generated ranks were recognized, and the background OCR-to-GUI flow counted a generated three-card scene correctly without duplicates. These synthetic checks do not measure performance on your stream.

These check count arithmetic, exhausted shoes, temporal agreement, moving-card duplicate prevention, independent identical ranks and round rearming. They do not establish real-stream recognition accuracy.

Capture and image matching follow the [MSS examples](https://python-mss.readthedocs.io/stable/examples.html) and [OpenCV template matching documentation](https://docs.opencv.org/3.4.19/d4/dc6/tutorial_py_template_matching.html).

Automatic OCR uses [RapidOCR](https://github.com/RapidAI/RapidOCR) with ONNX Runtime on the CPU.
