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

#Known limitations
Known limitation (Ruling 27, closed as no change). A strong name match combined with a publisher mismatch does not, by itself, guarantee a FLAGGED outcome. If the content category scores low (for example an original description with no credential-bait phrase), the candidate scores in the 0.50 to 0.70 band, comes out NOT_FLAGGED, and is surfaced with review_required = true for a human to check. We did not change the scoring formula to avoid false positives on legitimate third-party apps. On the development data, [N] app candidates fall in this review band. All figures are prototype results on simulated data.

## Evaluation

All results are prototype figures on **simulated data**. They are not real-world accuracy.

**Method.** Candidates are scored with ground-truth fields removed. Expected status comes from ground truth: official → CLEARED, impersonator → FLAGGED, benign → NOT_FLAGGED. Run `python evaluation.py` to reproduce.

**Dataset.** [N] social profiles and [N] app listings (development set). Hold-out: [not run yet / run on DATE, before any later engine change].

**Results (development set)**

| Metric | Value |
|---|---|
| Official assets wrongly FLAGGED | [0] |
| Benign candidates wrongly FLAGGED | [N] |
| Impersonators missed (not FLAGGED) | [N] |
| Precision / Recall / F1 | [ ] / [ ] / [ ] |
| Candidates marked `review_required` | [N] |
| False cluster connections (if clustering ships) | [N] |

The 3×3 confusion matrix is printed by the script. [Paste it or link to it.]

**Notes**
- Official assets are cleared before scoring and are never FLAGGED.
- Missing data never raises risk.
- See Known limitations for the strong name match / publisher mismatch case routed to review.

  
