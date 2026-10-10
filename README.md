# BrandShield AI

AI-powered Digital Risk Protection Platform.

## Features
- Social profile impersonation detection
- Suspicious mobile app detection
- Explainable risk scoring
- Evidence report export with SHA-256 hashing

## Tech Stack
- Python
- Streamlit
- RapidFuzz
- JSON

Known limitations
Known limitation (Ruling 27, closed as no change). A strong name match combined with a publisher mismatch does not, by itself, guarantee a FLAGGED outcome. If the content category scores low (for example an original description with no credential-bait phrase), the candidate scores in the 0.50 to 0.70 band, comes out NOT_FLAGGED, and is surfaced with review_required = true for a human to check. We did not change the scoring formula to avoid false positives on legitimate third-party apps. On the development data, 5 app candidates are marked review_required. All figures are prototype results on simulated data.
Evaluation
All results are prototype figures on simulated data. They are not real-world accuracy.
Method. Candidates are scored with ground-truth fields removed. Expected status comes from ground truth: official → CLEARED, impersonator → FLAGGED, benign → NOT_FLAGGED. Run python evaluation.py to reproduce.
Dataset. 33 social profiles and 19 app listings (52 records: 15 official, 19 impersonators, 18 benign; development set). Hold-out: not run yet on the final engines.
Results (development set)
Metric	Value
Official assets wrongly FLAGGED	0 of 15
Benign candidates wrongly FLAGGED	0 of 18
Impersonators missed (not FLAGGED)	1 of 19
Precision / Recall / F1	1.000 / 0.947 / 0.973
Candidates marked review_required	7 (social 2, apps 5)
False cluster connections (if clustering ships)	0 (13 of 13 true links found)
Confusion matrix (rows: ground truth, columns: returned status):
Truth \ Status	CLEARED	NOT_FLAGGED	FLAGGED
official	15	0	0
impersonator	0	1	18
benign	0	18	0
Notes
Official assets are cleared before scoring and are never FLAGGED.
Missing data never raises risk.
See Known limitations for the strong name match / publisher mismatch case routed to review.
The scam-phrase and credential-bait rules were adjusted while looking at this development set, so these figures are optimistic. They should be read together with the hold-out result once it has been run.
