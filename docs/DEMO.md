# 🎬 Demo video — how to record & where it lives

Expected file: `docs/demo.mp4` (referenced by `preview.html` / `docs/index.html`).
Poster: `preview-poster.png` + `docs/preview.png` (already captured with an automated
full-page screenshot, 1666×3425 — see README visual tour).

## Option A — automated browser capture (recommended, reproducible)
```bash
npx playwright install chromium
# record core flow first (≤15s): pipeline run → open preview.html → answer 1 quiz Q
npx playwright codegen file://$PWD/preview.html
# or Python:
python - <<'EOF'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(record_video_dir="docs/", viewport={"width":1280,"height":800})
    pg = ctx.new_page(); pg.goto("file:///home/md/src/price-action-investigator/preview.html")
    pg.wait_for_timeout(1500); pg.click("text=Buyers are stronger right now")
    pg.wait_for_timeout(800); ctx.close(); b.close()
print("video in docs/")
EOF
# trim to <2min, export docs/demo.mp4 (h264, 720p), re-run preview check
```

## Option B — Loom / OBS (human walkthrough)
1. 0–15s: the one core flow (run → results → quiz answer). 2. Then full run.
3. Export 720p mp4 → `docs/demo.mp4`. 4. Optional GIF ≤5MB → `docs/demo.gif`.

## Checklist before push
- [ ] `docs/demo.mp4` plays in the preview `<video>` tag
- [ ] Poster `preview-poster.png` matches current preview
- [ ] README 🎬 section + Pages link updated
