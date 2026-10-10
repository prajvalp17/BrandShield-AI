# CONTRACT.md — BrandShield AI
**Version:** 0.8.2-RULED  |  **Owner / tie-breaker:** Member 1  |  **Status:** SIGNED by Members 1, 2, 3, 4 and 5 (v0.8, hour 18); rulings below are in effect
Single source of truth for schemas and interfaces. If anything elsewhere disagrees, this file wins.
Rulings are recorded in section 9. Anything still marked **[OPEN]** must be closed by the date stated next to it (default: the H0–2 session).

## 1. Candidate input (what engines receive)
Engines never receive `ground_truth`, `category_note`, `expected_ring`.
**Field names are fixed as below. Draft names such as `handle` / `profile_name` / `official_social_handles` are retired.**

| Field | Social | App | Notes |
|---|---|---|---|
| entity_id | req | req | unique, `soc_01`, `app_01` |
| target_type | req | req | `social_profile` or `app_listing` |
| brand_id | req | req | key into brand_registry.json |
| platform | req | req | Instagram, X, Android |
| username | req | – | includes leading `@` |
| display_name, bio | opt | – | |
| account_age_days | opt | – | `null` = unknown |
| app_name, package_id, publisher, description | – | req/opt | publisher/description may be null |
| contact_number, redirect_url | opt | opt | raw strings; engines expose normalized forms (section 3) |
| evidence_source | req | req | `simulated` for all prototype data |

**Missing values:** absent or `null` = unknown. Unknown never raises risk, and a missing signal is excluded from scoring (not treated as 0 evidence of safety either).

## 2. Brand registry
`brands[]`: `brand_id, name, official_handles{platform:[handles]}, official_domains[], official_apps[{platform,package_id,publisher}], official_contact_numbers[]`, plus two **optional** lists (ruling 24, 26):
- `official_descriptions[]`: descriptions of the brand's official apps. App engines compare a candidate's description against these; if the list is absent or empty, `description_similarity` is `null`.
- `authorized_publishers[]`: publishers the brand authorizes besides its own (partners, resellers). `publisher_mismatch` is measured against the official publisher **plus** these; if absent, only the official publisher counts. A candidate from an authorized publisher is not a mismatch.
- Official match = exact match after normalization on a registered handle (same platform), domain, or package id.
- A handle/package may belong to only one brand; Member 1's loader asserts this.
- Official detection runs **before** scoring. A matched official asset is `CLEARED` and cannot be overridden by similarity signals.

## 3. Function signatures
```python
social_engine.evaluate(brand: dict, candidate: dict) -> dict      # Member 2
app_engine.evaluate(brand: dict, candidate: dict) -> dict         # Member 3
score_engine.combine(engine_output: dict) -> dict                  # Member 4 -> final result (section 4; input contract below)
report_builder.build_report(results: list[dict], brand: dict, candidates: list[dict],
                            engine_outputs: list[dict],
                            clusters: list[dict] | None = None) -> dict   # Member 4
normalization.*                                                    # Member 2, shared, due H6
clustering.cluster(results: list[dict], candidates: list[dict]) -> list[dict]   # Member 3, stretch
```

### Engine output (Members 2 and 3 return this; Member 4 consumes it)
```json
{
  "entity_id": "soc_04", "target_type": "social_profile",
  "platform": "Instagram", "identifier": "@example_support",
  "is_official": false, "exclusion_reason": null,
  "signals": {
    "handle_similarity": {"value": 0.92, "category": "identity", "reason": "…"},
    "account_age":       {"value": null, "category": "metadata", "reason": "unknown"}
  },
  "evidence_source": "simulated", "evidence_timestamp": null,
  "indicators": {"contact_number": "9000011111", "redirect_url": "secure-verify-login.example/auth"},
  "evidence": {}
}
```
- Signal `value` is a **float 0.0–1.0** (RapidFuzz 0–100 is divided by 100 inside the engine), or `null` if the input is missing. Higher = more suspicious.
- `category` is one of `identity`, `content`, `metadata`.
- `indicators` = normalized contact number and full redirect URL, for clustering only. They are **not scored** and are not a signal category.
- `evidence` = free-form raw details (matched phrases, compared strings). Member 4 copies it into report data only; it is not in the result record.
- **Required `score_engine.combine(engine_output)` input fields:** `entity_id`, `target_type`, `platform`, `identifier`, `is_official`, `exclusion_reason`, `signals`, and `evidence_source`. `evidence_timestamp` is required but may be `null`. `indicators` and `evidence` are present on engine outputs for downstream reporting/clustering but are not scored and are not copied into the frozen result.
- `identifier` is populated by the engine from the candidate: `username` for `social_profile`, `package_id` for `app_listing`. `platform`, `evidence_source`, and `entity_id` are copied from the candidate. `target_type` must be exactly `social_profile` or `app_listing`. Missing optional source timestamp becomes `null`; engines must not invent timestamps.
- `signals` must be a mapping of the contract signal names to `{value, category, reason}` records. `value` is a number from 0.0–1.0 or `null`; `category` is `identity`, `content`, or `metadata`; `reason` is a readable string (use an empty string if no reason is available).
- `asset_type` is dropped (`target_type` replaces it).

### Signal names (starting set; add only by logging a ruling)
| Category | Social | App |
|---|---|---|
| identity | `handle_similarity`, `name_similarity` | `app_name_similarity`, `package_similarity` |
| content | `scam_phrase` | `description_similarity`, `credential_bait` |
| metadata | `account_age` | `publisher_mismatch` |

### Normalization (shared utility, Member 2; ruling 23)
- `normalize_contact_number`: keep digits only; if there are 10 or more digits keep the **last 10**; otherwise `None`. So `+91 90000 11111`, `90000 11111` and `090000-11111` all become `9000011111`, while numbers one digit apart stay different.
- `normalize_redirect_url`: full URL compared (not just the domain). A trailing slash is **preserved**: `/a/` and `/a` are different URLs (ruling 28).

`account_age` mapping (Member 2 supplies, defaults): ≤14 days → 0.9; ≤90 days → 0.5; older → 0.0; unknown → `null`.

## 4. Frozen result schema (one per candidate, from `combine`)
```json
{
  "entity_id": "", "target_type": "", "platform": "", "identifier": "",
  "risk_score": 0.0, "status": "CLEARED|NOT_FLAGGED|FLAGGED",
  "is_official": false, "signals": {"handle_similarity": 0.92}, "reasons": [],
  "exclusion_reason": null, "review_required": false,
  "evidence_source": "simulated", "evidence_timestamp": null,
  "ring_id": null
}
```
- `identifier` = `username` for social, `package_id` for apps.
- **`signals` in the result** is a flat mapping `{signal_name: float}` containing only the non-null signals that were scored, each rounded to 3 decimals. Category and reason text are not repeated there (reasons are in `reasons`; the full signal records stay in the engine output). `signals` is `{}` for `CLEARED` records and when no signal had data.
- **Display labels:** the result record carries no brand name or display name and gets none added. The UI looks up the candidate by `entity_id` in the candidate data (social: `display_name`; app: `app_name`) and the brand by `brand_id` in the registry. Report data from Member 4 includes `brand` (id and name) and, per record, a `label` (display_name or app_name) so a report is readable on its own.
- **Null handling in the UI:** `null` is shown as "Not available" and is never replaced with a guessed value. Empty `reasons` shows "No reasons recorded".
- **Official assets:** the UI shows the returned `status` (CLEARED) and `exclusion_reason`; it never recalculates status.
- `ring_id` stays (it was in the earlier agreed schema); it is `null` in `combine` output and is filled only in the report copy if clustering ships. Linked candidates and shared-indicator reasons go **only** in report data.
- `evidence_hash` is **not** in the result record. Member 5 hashes the serialized report.

## 5. Status and review rules (owner: Member 4)
- Threshold: **0.70**.
- A category is **active** if its highest non-null signal value is ≥ **0.60**.
- `CLEARED`: `is_official` true. `risk_score` = 0.0, `exclusion_reason` set.
- `FLAGGED`: `risk_score` ≥ 0.70 **and** ≥ 2 distinct active categories.
- `NOT_FLAGGED`: everything else.
- `review_required` = true when either (a) `risk_score` ≥ 0.70 but fewer than 2 active categories (flag blocked for lack of independent evidence), or (b) `NOT_FLAGGED` and 0.50 ≤ `risk_score` < 0.70 (borderline). Otherwise false. Fully deterministic; no other triggers.
- Correlated signals (`handle_similarity` + `name_similarity`) belong to the same category and count once.
- **Scoring formula (ruling 17):** category value = the highest non-null signal in that category. `risk_score` = Σ(weight × category value) ÷ Σ(weight), summed only over categories that have at least one non-null signal. Weights: identity 0.45, content 0.35, metadata 0.20. A category with no data is excluded and its weight is redistributed, so missing data never lowers the score. If no category has data, `risk_score` = 0.0 with the reason "Insufficient evidence to calculate risk".
- **Comparisons and rounding (ruling 17):** all comparisons against 0.70, 0.60 and 0.50 use the score **rounded to 6 decimals** (this removes floating-point noise, e.g. two categories at 0.70 must score exactly 0.70). The reported `risk_score` is rounded to 3 decimals. The status and `review_required` must never contradict the reported score.
- **Input validation (ruling 19):** `combine` raises an error, and does not fill in defaults, when a required input field is missing, a signal has an unknown `category`, or a signal `value` is outside 0.0–1.0 and not null.
- The UI shows the returned status and never re-decides.

## 6. Report structure and ownership

### Frozen report-builder interface
```python
report_builder.build_report(
    results: list[dict],          # outputs of score_engine.combine
    brand: dict,                  # registry entry
    candidates: list[dict],       # candidate input records (source of `label`)
    engine_outputs: list[dict],   # outputs of social/app evaluate (source of `evidence`)
    clusters: list[dict] | None = None
) -> dict
```

**Approved signature / data flow (Member 1 ruling):** Keep the signature below. The caller passes the original candidate input records in `candidates`; the builder indexes them by `entity_id` and uses `display_name` for `social_profile` or `app_name` for `app_listing`. It must not infer labels from `identifier` or engine evidence. The caller also passes the matching raw engine outputs separately so `evidence` can be copied by `entity_id`. The `results` argument contains only frozen `combine()` results. Member 5 consumes the returned report and owns serialization, hashing, and download.

The report builder returns a JSON-serializable dictionary with these fixed top-level keys:
```json
{
  "brand": {
    "brand_id": "brand_01",
    "name": "Example Brand"
  },
  "results": [
    {
      "...": "all fields from the frozen result schema, unchanged",
      "label": "Readable candidate label",
      "evidence": {}
    }
  ],
  "clusters": []
}
```

- `brand`: always contains `brand_id` and `name`.
- `results`: each entry preserves every field from the frozen result schema and adds `label` and `evidence` to a **new report dictionary**. The builder must not mutate the original result records, and must deep-copy so that nothing in the report shares objects with its inputs (`signals`, `reasons`, `evidence`). The only frozen field it may fill in the copy is `ring_id` (see below).
- `label`: social `display_name` or app `app_name`, looked up in `candidates` by `entity_id`; `null` if missing (never guessed).
- `evidence`: the `evidence` dict from the matching entry in `engine_outputs` (by `entity_id`); `{}` when unavailable. (`combine` does not carry evidence, which is why the builder takes `engine_outputs`.)
- `ring_id`: `null` in every `combine` result. When clustering ships, the builder fills `ring_id` in its report copy from `clusters`; otherwise it stays `null`.
- **Deterministic output** (so the hash is reproducible): `results` sorted by `entity_id`, `clusters` by `ring_id`, no generated-at timestamp, only JSON-serializable values.
- `clusters`: always present. Use `[]` when clustering is unavailable. When clustering ships, use Member 3's cluster-record structure, including `ring_id`, `linked_candidate_ids`, and a reason for each link. The record structure is fixed in section 7 (ruling 25).
- **Cluster validity (ruling 22):** each candidate belongs to at most one cluster, and each `ring_id` appears once. If the `clusters` input has a candidate in more than one cluster, a duplicate `ring_id`, or a cluster without `ring_id` or `linked_candidate_ids`, `build_report` raises `ValueError` naming the offending ids. It never picks a winner and never silently drops a cluster. Clusters come from Union-Find (section 7), so they are disjoint by construction; overlap means the clustering output is wrong and must be fixed at its source (Member 3), not hidden in the report.
- The report builder only assembles report data. It must not recalculate risk scores, change statuses, serialize JSON, or calculate hashes.
- Report-only fields `label` and `evidence` must not be added to the frozen result schema returned by the scoring engine.

### Serialization and export ownership
Member 4 owns report content and explanations. Member 5 owns canonical serialization, SHA-256, and download. Canonical form: UTF-8 JSON, sorted keys, `separators=(",", ":")`, `ensure_ascii=False`. The SHA-256 is computed over the exact bytes of the downloaded file and shown beside the download. It shows the file is unchanged since export; it does not prove the source evidence is authentic.

## 7. Optional clustering ("Threat Rings") — stretch
- Gate H13: continue only if the core is stable. Gate H16: if unstable, omit the UI and document as future work.
- Only `FLAGGED` candidates can be linked. Link on equal normalized `contact_number` **or** equal normalized full `redirect_url` (domain-only matches do not link; numbers one digit apart do not link).
- **Cluster record (ruling 25):** `clustering.cluster(results, candidates)` returns a list of
  ```json
  {"ring_id": "ring_001", "linked_candidate_ids": ["app_03", "soc_04"],
   "link_reasons": [{"candidate_id_1": "app_03", "candidate_id_2": "soc_04",
                     "indicator_type": "contact_number|redirect_url", "reason": "…"}]}
  ```
  `ring_id` is `ring_` plus three digits, unique per cluster, assigned in a deterministic order. `linked_candidate_ids` is sorted and has at least two entries. A candidate belongs to at most one cluster. Only `FLAGGED` candidates are linked. Every cluster has at least one link reason.
- Output goes in report data as `linked_candidate_ids` plus a reason per link. A shared indicator is a possible connection, not proof of fraud or common ownership.

## 8. Evaluation conventions (Member 1)
Ground truth → expected status: `official→CLEARED`, `impersonator→FLAGGED`, `benign→NOT_FLAGGED`.
Counted separately: official-asset false positive (official FLAGGED), benign false positive (benign FLAGGED), missed impersonator (impersonator not FLAGGED). Also precision, recall, F1, 3×3 confusion matrix, review-flag count, and if clustering exists, false connections (links between records without a shared ground-truth ring). All figures are prototype results on simulated data.

## 9. Decision log
| # | Question (who asked) | Ruling |
|---|---|---|
| 1 | Risk threshold (M5) | 0.70 |
| 2 | Evidence categories and mapping (M2, M4, M5) | Three scored categories: identity, content, metadata (section 3). Contact/redirect are not scored; they feed clustering only. Reason: no ground truth to validate them as evidence, and scoring them would make clustering circular. |
| 3 | Signal structure, field names, scale (M2, M3, M4, M5) | Section 3. Contract names win; values 0–1 |
| 4 | `ring_id` / `evidence_hash` (M4, M5) | Keep `ring_id` (nullable). Drop `evidence_hash` (M5 owns hashing) |
| 5 | `review_required` rule (M4, M5) | Section 5, two deterministic triggers |
| 6 | Where `evidence` and linked ids go (M2, M4) | Report data only |
| 7 | `report_builder` interface (M3/M4/M5) | Frozen interface and report keys in sections 3 and 6. Signature takes `candidates` and `engine_outputs` because label and evidence are not in `combine` results. Cluster-record structure is [OPEN] for Member 3, due before H13. |
| 8 | Official exclusion (M3) | Section 2: before scoring, cannot be overridden |
| 9 | Contact/redirect as social signals (M2) | Exposed as `indicators`, not scored |
| 10 | Identifier display (M5) | `identifier` = `username` (social) / `package_id` (app); UI shows display_name or app_name as the label via lookup |
| 11 | Display/brand fields (M5) | Not added to the result schema; report data carries `brand` and per-record `label` (M4) |
| 12 | Null behaviour and hash claim (M5) | Section 4 and section 6 |
| 13 | Who sets `ring_id` | Null in `combine` results; the report builder fills it in its report copy from `clusters` |
| 14 | Report determinism | Sorted results and clusters, no generated-at timestamp, so the SHA-256 is reproducible |
| 15 | `score_engine.combine()` input contract (M2/M3/M4) | Keep the one-argument signature. Each engine output must include `entity_id`, `target_type`, `platform`, `identifier`, `is_official`, `exclusion_reason`, `signals`, `evidence_source`, and nullable `evidence_timestamp`; `indicators` and `evidence` are for clustering/reporting only. Field rules in section 3. |
| 16 | Candidate-to-report label flow (M4/M5) | Retain `build_report(results, brand, candidates, engine_outputs, clusters=None)`. `candidates` supplies labels, `engine_outputs` supplies `evidence`, `results` stays frozen. |
| 17 | Scoring formula and rounding (M4) | Section 5: weights 0.45/0.35/0.20, renormalized over categories with data; comparisons use the score rounded to 6 decimals; reported score rounded to 3. Found during PR review: unrounded comparison made two categories at exactly 0.70 come out NOT_FLAGGED while displaying 0.7. |
| 18 | Shape of `signals` in the result (M4/M5) | Flat `{signal_name: float}`, non-null scored signals only (section 4) |
| 19 | `combine` input validation (M4) | Raise on missing required fields, unknown category, or out-of-range value; no silent defaults. |
| 20 | Repo layout (M3) | All modules at the repo root as in the roadmap (`social_engine.py`, `app_engine.py`, `score_engine.py`, `report_builder.py`, `normalization.py`, `clustering.py`). Member 3 to move `detection/app_engine.py`. |
| 21 | Report builder copies (M4) | Deep copy; the report shares no objects with its inputs (section 6) |
| 22 | Candidate in several clusters (M4) | Reject: `build_report` raises `ValueError` on overlapping clusters, duplicate `ring_id`, or malformed clusters (section 6). Chosen over "last wins" because that silently shows a wrong ring in an evidence report. |
| 23 | Contact number format (M2, M3) | Digits only, last 10 digits when there are 10 or more, else `None` (section 3). Trailing-slash handling for URLs: see ruling 28. |
| 24 | Official descriptions (M3) | Optional `official_descriptions[]` in the registry; absent means `description_similarity` is `null` (section 2) |
| 25 | Cluster record structure (M3) | Section 7, as built by Member 3 |
| 26 | Authorized publishers (M3, M4) | Optional `authorized_publishers[]`; `publisher_mismatch` measured against official plus authorized (section 2) |
| 27 | Scoring rule for strong identity plus verified publisher mismatch without content evidence (M4) | **CLOSED, no change.** Formula unchanged. A strong name match with a publisher mismatch does not, by itself, guarantee FLAGGED. When the content category has a low non-null value, such candidates score in the 0.50 to 0.70 band and come out NOT_FLAGGED with `review_required` = true, so a human sees them. Changing the formula risks false positives on legitimate third-party apps and cannot be judged fairly on the hold-out set, which must stay unseen. **Known limitation: it must be stated clearly in the evaluation documentation and on the slide** (condition set by Members 2, 3, 4 and 5, who raised no objection at hour 18). Member 5's added condition: the UI keeps displaying the engine's final outputs and never overrides them. |
| 28 | Trailing slash in `normalize_redirect_url` (M2) | **Preserved**: `/a/` and `/a` are different URLs; the path is kept as given, and only the scheme and host are lowercased. Decided by Member 1 as tie-breaker, accepting Member 2's implementation over the earlier proposal to ignore it. Reason: clustering links only on an exact full-URL match, so a missed link is safer than a false connection, and the development data has no URLs that differ only by a trailing slash. Implemented in `normalization.py` with `test_redirect_url_preserves_trailing_slash`. |

## 10. Sign-off
| Member | Role | Signed (name, hour) |
|---|---|---|
| 1 | Data & Evaluation | Kritika Pandey, hour 18 |
| 2 | Social & Normalization | Sohan, hour 18 |
| 3 | App & Clustering | Kruthika B Reddy, hour 18 |
| 4 | Scoring & Report Data | Nandini P, hour 18 |
| 5 | UI, Export & Deployment | Prajval, hour 18 |
