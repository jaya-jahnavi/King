# King — live count and saved rounds

A desktop tool that reads exposed blackjack cards from a selected screen region. It displays the observed running count, the current round's count and cards, and a saved history of Round 1, Round 2 and later rounds. OpenAI recognition is optional and uploads cropped images; local OCR also remains available.

**Recognition accuracy and live API latency have not been established on the supplied stream.** The local OCR reader failed on sampled frames of that stream. The OpenAI connection and counting logic have been exercised with mocked network responses; test your recording with your account before relying on live observations.

## Start

Python 3.11 or newer with Tkinter is required. In the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

The Live count tab has three steps:

1. **Connect OpenAI:** enter the API key into King's masked dialog. It stays in memory for the app session, never in source, calibration or GitHub. Alternatively set `OPENAI_API_KEY` in the environment before launching. Do not paste your key into chat. A key being set does not mean account access has been validated.
2. **Choose video area:** pick the video screen in the dropdown, then select only the main playing surface. Exclude browser controls, other tables, hand totals, chips where possible, and the duplicate digital dealer overlay. Keep the browser visible, with King outside the captured area or on another screen.
3. **Start counting:** the app stays paused until this explicit step, including after loading a saved region. Start at the beginning of a shoe and set the number of decks with **New shoe**. Entering mid-shoe cannot reconstruct cards dealt earlier.

Settings contains model choice, connection diagnostics, request limits, screen refresh, the recording test and advanced local template tools. Corrections contains manual rank buttons, Undo last card and the card event log. These tools are separate from the main dashboard so the live count is easy to follow.

## Understand the dashboard

| Display | Meaning |
| --- | --- |
| Running count | Sum of all recognized cards in the current shoe |
| This round | Hi-Lo contribution of cards recognized in the current round |
| Current round | Local round number, beginning at Round 1 |
| Cards this round | Number of card events recorded in the current round |
| Round history | Cards, round count and running count after each round |

Example: Round 1 has `2 3 K`, so its round count is +1 and running count is +1. Round 2 adds `6 6 10`, so its round count is +1 and running count becomes +2. A neutral card remains in the card list even though it contributes zero.

Hi-Lo values: 2–6 = +1; 7–9 = 0; 10/J/Q/K/A = −1. Estimated true count (shown in Settings) divides the running count by estimated decks remaining: starting decks minus observed cards / 52. Unseen burns, missed cards and joining mid-shoe make that estimate unreliable.

The activity line distinguishes a request currently processing from the last finished count. The preview and timer remain responsive while inference runs; a displayed running count is not a claim that the current video frame has already been analyzed.

## Rounds and automatic saving

- OpenAI mode ends a round only after two or more complete empty-table observations spanning at least three seconds. An unreadable image or a facedown dealer card is not an empty table. Local OCR uses an empty-detection interval and is less reliable. A confirmed boundary saves the current round and advances once; repeated empty frames do not create extra rounds.
- **Next round** manually ends a round after its old cards clear. It pauses, retains the shoe count and opens the next round. Clicking repeatedly without new card events does not add empty rounds. Round numbers are King's local history, not official casino hand IDs. If a camera never shows an empty table, use this manual boundary.
- History saves automatically after card additions, corrections, round changes and shoe changes to `calibration/session.json`. It contains round-tagged card events and timestamps, not screenshots or API keys. The original calibration folder remains ignored by Git.
- Restarting restores cards, round numbers and running count but stays paused. If the restored round has cards, wait for the physical cards to clear, then use **Next round** before starting. This prevents a cold recognizer from silently recounting an unfinished hand. Use only one King app instance with this history folder at a time.
- **New shoe** archives the previous shoe's observed rounds, resets running count, and begins Round 1 for the next shoe. Previous rounds remain in the history table. It does not reset the API request counter.
- **Clear data / Start Round 1** (top right) is for starting over or moving to another table. It asks for confirmation, then removes the app's active saved round/card history, resets shoe and round numbering to 1, resets count to 0 and clears the old video crop. Choose the new table area before starting. API key, deck setting, other settings and session request usage are retained; exported CSV files are not deleted. Cancel leaves counts/history unchanged and paused. An old in-flight read cannot repopulate cleared data.
- **Export rounds CSV** writes one row per round: shoe, round number, recognized cards, number of cards, round count, running count, status and first/last card timestamps. Select a round row to review its cards in the side panel. Lists reflect observation order, not guaranteed physical dealing order.
- Undo pauses and removes the most recent card only from the current round. It cannot silently alter a previously saved round. Manual additions can duplicate automatic reads; use them carefully. If history cannot be read or saved, the app shows a separate history warning and preserves the existing file; New shoe backs up an unreadable file before starting fresh.

## Add a missed card to an older round

Use the two buttons just above the round history:

1. **Add to previous round** targets the last saved round before the current one. The popup identifies its shoe and round. If no previous round exists, the app says so without changing data.
2. **Add to selected round** targets the row you clicked in the history table, including saved rounds from earlier shoes. With no row selected it targets the current round.
3. Choose the missed rank (2–10, J, Q, K or A) in the popup. One click adds one card, recalculates that round's count and every later running total in the same shoe, then saves the corrected history. Other shoes keep their own independent counts. CSV export includes the corrected values. Cancel adds nothing.

Example: Round 1 had `2 K` (round count 0), and Round 2 had `3` (running +1). Add a missed `6` to Round 1: Round 1 becomes +1, Round 2 remains +1 for that round, and the running count after Round 2 becomes +2.

Counting pauses while correcting, and pending reads from before the correction cannot alter the updated count. Correcting the active OpenAI round also updates duplicate tracking, so a later successful read of that manually counted card is not automatically added again. This cannot tell whether a manually entered card was actually missed: check the recorded list before adding it. For active local/template rounds, resume on a fresh round after old cards clear because the missing card cannot be associated with a particular local position reliably. Older-round corrections leave current-round recognition tracking intact.

## Faster updates

**Fast (1 read)** is the default and is visibly labeled as using less verification. It applies a complete rank set from one AI read. **Verified (2 reads)** waits for two successive agreeing complete rank sets. Neither is a guarantee that the model read every card correctly, and changing modes does not retroactively verify earlier observations.

Live API responses use a compact rank-only schema. They omit suit and coordinate output that is unnecessary for counting. For an illustrative 11-card result, the compact JSON was 108 bytes versus 999 bytes in the detailed format. This is an output-size comparison, not a measured API speedup. The one-frame recording test keeps detailed boxes for visual checking.

Requests have a default one-second minimum interval between starts and run sequentially, without queuing old frames or automatically retrying failed calls. Actual model/network latency can exceed that interval. The app applies completed results on an 80 ms UI polling loop and updates the processing timer every 100 ms. It pauses live counting without applying results over 30 seconds old. No instantaneous response time is promised.

OpenAI counting uses rank multiplicities for duplicate prevention. An unchanged pair of kings does not count again; a newly visible third king adds one. Ranks disappearing or changing blocks additions rather than inventing a new card. This assumes dealt cards remain on the table until the round clears. Camera cuts, removals, missing a clear interval or a model incorrectly reporting completeness can still produce errors. Fast mode trades an additional check for earlier updates.

## Test your recording first

In **Settings**, click **Test recording — 1 paid request**, choose a video or image, choose a timestamp, and crop the main tabletop. The test shows recognized ranks, visible-set Hi-Lo and measured request time. It never changes the shoe count.

For the supplied recording around 60 seconds, the manual reference is 11 exposed cards and visible-set Hi-Lo −3. Check each card, not only the total: matching totals can hide recognition errors. This reference is one visible set, not the count of the entire shoe. The recording begins with a hand already dealt.

For a local-OCR recording audit without API use:

```powershell
python audit_video.py recording.mp4 --samples 12 --output recognition-audit.json
python audit_video.py recording.mp4 --region 680 680 640 210 --output recognition-audit.json
```

The audit lists sampled shapes and readable ranks; it does not count repeated sightings as new cards or claim an accuracy score without labeled ground truth.

## API settings and privacy

The initial model is `gpt-6.1-terra`; select another listed image/structured-output model if necessary for your account. Only the selected crop is sent as a JPEG, downscaled to a maximum side of 2048 pixels, to `https://api.openai.com/v1/responses`. Local OCR makes no OpenAI calls. The app now defaults to OpenAI but never auto-starts capture or uploads at launch.

API charges apply. The default session limit is 60 requests, counting tests, failures and live requests. Increasing the limit explicitly permits more paid requests. This is a request-count limit, not a dollar budget. Pausing stops new requests; an in-flight request may still finish and incur charges. Restarting creates a fresh local request counter. No automatic retries are made.

Requests use structured outputs and `store=false`; that flag disables response storage for retrieval and does not promise zero retention by the API provider. Authentication/quota failures, refusals, incomplete output and invalid responses cannot act as empty-table observations. No real API call was made during development because a key was not configured in the development process. Real account access, accuracy and latency remain to be tested locally.

## Extended screens

Use Win+P → Extend. Put the video on the external monitor and King on the other display. Choose the video monitor in the main dropdown, then **Choose video area**. Switching monitors immediately switches preview, pauses and clears the old crop while retaining counts. If a counted hand was interrupted, advance to a fresh round before resuming.

Display entries include physical resolution and desktop origin; app display numbers may differ from Windows Settings. Monitors left of or above the main display, including negative origins, are supported. The app requests per-monitor DPI awareness and maps selections from actual screenshot size to physical pixels. Layout changes checked every three seconds pause capture and clear stale crops. Settings → Refresh screens rescans immediately.

Capture and preview were checked on the actual second 1920 × 1080 display, including a 600 × 400 crop. Simulated tests cover negative origins, switching, persistence and unplugging. Physical mixed-DPI verification remains outstanding. Moving or resizing the browser requires selecting its video area again. Protected video may appear black.

## Local OCR and optional templates

Settings allows switching to Local OCR. That experimental white-contour/OCR pipeline failed to recognize ranks in sampled frames of the supplied live-dealer footage. Small, tilted, overlapping cards and white table markings defeat it; no reliable fix for that reader is claimed.

For a consistent close-up layout, disable automatic reading in advanced Settings, add tight rank-only card positions, then save all 13 rank templates (2–10/J/Q/K/A) from the stream. A manual position emits once per round; Next round rearms it. This mode is not a general detector and needs recalibration when appearance/layout changes. Neither reader detects shuffles automatically or reads hidden cards.

## Development checks

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app.py interface.py counting.py openai_vision.py
```

Opt-in generated-card OCR check (may download local OCR models):

```powershell
$env:KING_TEST_OCR='1'
python -m unittest discover -s tests -v
```

Tests cover count arithmetic, duplicate prevention, clear-table boundaries, per-round persistence, shoe archives, compact API results, error handling and display geometry. GUI checks cover two-round history/CSV/restore, guarded restart, screen changes, recording crop extraction and request limits with mocked API transport. Passing synthetic or mocked checks does not establish real-stream accuracy or cloud latency.

References: [OpenAI image inputs](https://developers.openai.com/api/docs/guides/images-vision), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [latency guidance](https://developers.openai.com/api/docs/guides/latency-optimization), [MSS capture examples](https://python-mss.readthedocs.io/stable/examples.html), [Windows DPI awareness](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setprocessdpiawarenesscontext).
