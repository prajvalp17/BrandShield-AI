# Integration checklist (Member 1 runs at H13–16, re-runs at H16–19)
Mark a hosted-build item only after someone *other than its author* verifies it on the deployed URL (counter starts 0 of 16).

## Before running
- [ ] Everyone is on the latest main; `pip install -r requirements.txt` works on a clean environment
- [ ] `python make_data.py` output matches committed data files
- [ ] `python evaluation.py` runs with REAL engines (header says Engines: REAL)

## Contract conformance
- [ ] Every result has all fields from CONTRACT.md section 4, no extras
- [ ] Statuses are only CLEARED / NOT_FLAGGED / FLAGGED
- [ ] Missing account age / phone / URL never raises risk (spot-check soc_03, soc_30–31)
- [ ] Official assets: 0 FLAGGED (evaluation asserts this)
- [ ] Every FLAGGED record has ≥ 2 independent evidence categories in `reasons`
- [ ] `review_required` follows CONTRACT section 5 (borderline cases such as soc_31, soc_32 should land in the 0.50–0.70 band or be blocked flags; if not, check the rule, not the data)

## Dashboard (hosted URL)
- [ ] Brand selector, platform/status/risk filters work
- [ ] Table values equal evaluation output for the same records
- [ ] "Why not flagged" shown for benign lookalikes
- [ ] Report content matches the displayed decisions
- [ ] Download works; SHA-256 reproducible by re-hashing the downloaded file
- [ ] Runs offline from local data (local fallback)

## Clustering (only if go at H13/H16)
- [ ] Ring A (5 records, social + app) found; Ring B (3, redirect-only) found
- [ ] 0 false connections: near-miss phone, shared benign phone, linkhub.example paths, official records
- [ ] Wording says "possible connection", never "same owner"
