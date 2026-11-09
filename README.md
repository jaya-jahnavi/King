# King — automatic live screen card counting

A Python desktop tool for a visible browser video or screen stream. The local OCR reader detects mostly exposed white cards with RapidOCR and performs inference locally. The optional OpenAI reader sends selected table images to the OpenAI API for recognition. Both update a Hi-Lo running count and estimated true count; the OpenAI path is implemented but has not yet been validated with a live account on the supplied recording.

## Run on Windows

Requires Python 3.11 or newer with Tkinter (included in the standard python.org Windows installer).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## OpenAI reader — set your key in the app

1. Restart `app.py`. Click **Set API key** and enter your key into the masked dialog in King. Never paste the key into chat or source code. The key stays in memory for this app session; it is not saved in calibration, logs or GitHub. Alternatively, set `OPENAI_API_KEY` in the environment before launching. Local OCR remains the startup default and makes no OpenAI calls.
2. Click **Test recording (1 call)**, choose a recording or image, choose a timestamp (60 seconds for the supplied recording), and select only the MAIN tabletop in the frame. Exclude the duplicate digital dealer overlay, account information, browser controls and other tables. This makes one paid API request and shows ranks, a visible-set Hi-Lo total and measured request time. It does not change the shoe count. For the supplied frame near 60 seconds, the manually read reference is 11 exposed cards with visible-set Hi-Lo −3. Compare every card rather than checking only the total. An identical total can hide errors.
3. The initial model is `gpt-6.1-terra`; choose another listed vision/structured-output model if your account does not support it. The key is not validated until a request succeeds. A successful request does not establish recognition accuracy on other images.
4. For live use after validation, choose **OpenAI**, keep **Automatic card reading** checked, select the video display and **Select table**. If a region was already selected, press **Start / Pause**. Enter starting decks and reset at each shuffle. Start from the beginning of a shoe for a meaningful count.
5. **Min seconds** defaults to 2 (range 1–30). This is a minimum time between request starts, not a promised response time. Only one recognition request runs at once. The app shows measured latency, image age, token usage and requests started. Preview continues while a request is running. Results more than 30 seconds old pause live counting without applying that result.
6. **Call limit** defaults to 60 requests per app session. Recording tests, failed requests and live reads all consume this local limit. The app pauses at the limit; increasing it explicitly allows more paid requests. Calls are not automatically retried. This is a request-count limit, not a dollar budget. Stopping capture does not cancel a request already sent; that request may finish and incur charges. Closing/restarting King starts a fresh local request counter.

OpenAI mode compares complete rank multisets, rather than trusting model coordinates as card identities. Two successive agreeing complete observations are needed before adding the new cards. Repeated sightings, including equal-rank cards, are handled by multiplicity: a second `K` increases the count of kings from one to two; an unchanged pair does not add again. Previously counted ranks disappearing or changing blocks additions until the table clearly clears or the user intervenes. Two or more complete empty-table reads spanning at least three seconds rearm the hand while retaining the shoe count. An unclear or incomplete read never acts as an empty table.

This assumes dealt cards remain on the table until the round is cleared. Removing cards early, camera cuts, the model claiming an incorrect reading is complete, or missing a full clear-table interval can still cause counting errors. **Next round** rearms tracking manually; use it only after old cards clear. Reader/model changes pause and reset hand tracking, so resume on a fresh round if cards have already been counted. Manual cards can duplicate automatic detections; use them carefully when correcting an error. The display is an observed count, not a guarantee that every card was recognized. There is no established live accuracy or latency yet for your account and stream.

Only the selected crop is uploaded as a JPEG (downscaled to a maximum side of 2048 pixels). Requests go to `https://api.openai.com/v1/responses`, use structured JSON outputs and `store=false`. That flag disables response storage for retrieval; it is not a promise of zero retention by the API provider. No API key or uploaded image is persisted by this integration. Model scores are not shown as probabilities. Authentication, quota, refusal, incomplete output and malformed responses pause or reject observations without changing the count.

Official implementation references: [image inputs](https://developers.openai.com/api/docs/guides/images-vision), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), and [GPT-6.1 Terra capabilities](https://developers.openai.com/api/docs/models/gpt-6.1-terra).

Integration checks passed with mocked network responses: masked-key setup without key persistence, extracting the actual recording's 60-second frame and selected crop, one-call test without count mutation, two-observation confirmation, duplicate prevention, incomplete observations, request caps and stale results. The latest unit run passed 25 tests and skipped one opt-in local OCR test. **No live OpenAI requests were made during development because an API key was not configured.** Recognition accuracy, account access and end-to-end API latency must be checked using Test recording before live use.

## Extended desktop / second monitor

1. Set Windows projection to **Extend** (Win+P → Extend). Put the visible browser video on the external monitor and keep King on your laptop or other monitor.
2. Choose that monitor in King's **Screen** dropdown. Entries include physical resolution and desktop coordinates, so equal-resolution screens are distinguishable. King's display numbers reflect its capture list and may differ from Windows Settings' numbers.
3. Switching the dropdown immediately switches the full-screen preview, pauses recognition and clears the old crop. Click **Select table** and select the video area in the screenshot. Capture uses that monitor's physical pixels, including negative desktop coordinates for monitors placed left of or above the main display.
4. If no cards have been counted yet, selecting a table starts automatic mode. If the shoe already has recorded cards, it stays paused and retains the shoe count: resume on a fresh round so old visible cards are not recounted. Moving or resizing the browser within the same monitor also requires selecting its table area again.
5. King remembers the selected display and crop. Display connections, resolution or arrangement changes are checked every three seconds while the app is visible. A changed layout pauses recognition and clears the stale crop; choose the video display and select its table again. **Refresh screens** rescans immediately after connecting an external monitor.

Windows per-monitor DPI awareness is requested at startup; selection coordinates map from the actual resized screenshot back to source pixels rather than applying the laptop's scaling to another display. Capture and preview were checked on an actual second 1920 × 1080 display to the right of the main display, including a 600 × 400 crop. Geometry and source-switching checks cover simulated layouts, including left/above monitors, saved selection, stale worker results and unplugging; mixed-DPI capture across physical monitors still needs hardware verification. Source selection does not resolve the documented card-recognition failure on the supplied stream.

Implementation references: [Microsoft per-monitor DPI awareness](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setprocessdpiawarenesscontext) and [MSS capture coordinates](https://python-mss.readthedocs.io/stable/examples.html).

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

The supplied live-dealer recording exposed a real-stream failure: the current pipeline recognized no ranks in six sampled frames, using both the complete screen and a main-table crop. Synthetic tests passing does **not** establish that this reader works on live-dealer footage. The app now explicitly warns when no ranks are recognized. Do not interpret an unchanged displayed count as a verified zero.

To reproduce recognition on a local recording without opening the live screen:

```powershell
python audit_video.py recording.mp4 --samples 12 --output recognition-audit.json
# Optional main-table crop: X Y WIDTH HEIGHT in recording pixels
python audit_video.py recording.mp4 --region 680 680 640 210 --output recognition-audit.json
```

The audit samples frames and records candidate shapes and readable ranks. It does not add repeated sightings to a shoe count, measure accuracy without ground truth, or upload footage. Keep the dealer's duplicate digital overlay outside the selected table region. The current reader remains unsuitable for a reliable count on the supplied stream; a validated replacement detector is still required.

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
