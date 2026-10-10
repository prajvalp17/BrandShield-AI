# CONTRACT.md — BrandShield AI
**Version:** 0.5-RULED  |  **Owner / tie-breaker:** Member 1  |  **Status:** NOT SIGNED (rulings below take effect on sign-off)
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
`brands[]`: `brand_id, name, official_handles{platform:[handles]}, official_domains[], official_apps[{platform,package_id,publisher}], official_contact_numbers[]`.
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

`account_age` mapping (Member 2 supplies, defaults): ≤14 days → 0.9; ≤90 days → 0.5; older → 0.0; unknown → `null`.

## 4. Frozen result schema (one per candidate, from `combine`)
```json
{
  "entity_id": "", "target_type": "", "platform": "", "identifier": "",
  "risk_score": 0.0, "status": "CLEARED|NOT_FLAGGED|FLAGGED",
  "is_official": false, "signals": {}, "reasons": [],
  "exclusion_reason": null, "review_required": false,
  "evidence_source": "simulated", "evidence_timestamp": null,
  "ring_id": null
}
```
- `identifier` = `username` for social, `package_id` for apps.
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
- `risk_score` formula is Member 4's; it must ignore null signals and stay within 0–1.
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

**Approved signature / data flow (Member 1 ruling; pending Member 4 and Member 5 acknowledgement):** Keep the signature below. The caller passes the original candidate input records in `candidates`; the builder indexes them by `entity_id` and uses `display_name` for `social_profile` or `app_name` for `app_listing`. It must not infer labels from `identifier` or engine evidence. The caller also passes the matching raw engine outputs separately so `evidence` can be copied by `entity_id`. The `results` argument contains only frozen `combine()` results. Member 5 consumes the returned report and owns serialization, hashing, and download.

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
- `results`: each entry preserves every field from the frozen result schema and adds `label` and `evidence` to a **new report dictionary**. The builder must not mutate the original result records. The only frozen field it may fill in the copy is `ring_id` (see below).
- `label`: social `display_name` or app `app_name`, looked up in `candidates` by `entity_id`; `null` if missing (never guessed).
- `evidence`: the `evidence` dict from the matching entry in `engine_outputs` (by `entity_id`); `{}` when unavailable. (`combine` does not carry evidence, which is why the builder takes `engine_outputs`.)
- `ring_id`: `null` in every `combine` result. When clustering ships, the builder fills `ring_id` in its report copy from `clusters`; otherwise it stays `null`.
- **Deterministic output** (so the hash is reproducible): `results` sorted by `entity_id`, `clusters` by `ring_id`, no generated-at timestamp, only JSON-serializable values.
- `clusters`: always present. Use `[]` when clustering is unavailable. When clustering ships, use Member 3's cluster-record structure, including `ring_id`, `linked_candidate_ids`, and a reason for each link. **[OPEN]** Member 3 to write the exact record structure (including how a link reason is stored) into this section before H13.
- The report builder only assembles report data. It must not recalculate risk scores, change statuses, serialize JSON, or calculate hashes.
- Report-only fields `label` and `evidence` must not be added to the frozen result schema returned by the scoring engine.

### Serialization and export ownership
Member 4 owns report content and explanations. Member 5 owns canonical serialization, SHA-256, and download. Canonical form: UTF-8 JSON, sorted keys, `separators=(",", ":")`, `ensure_ascii=False`. The SHA-256 is computed over the exact bytes of the downloaded file and shown beside the download. It shows the file is unchanged since export; it does not prove the source evidence is authentic.

## 7. Optional clustering ("Threat Rings") — stretch
- Gate H13: continue only if the core is stable. Gate H16: if unstable, omit the UI and document as future work.
- Only `FLAGGED` candidates can be linked. Link on equal normalized `contact_number` **or** equal normalized full `redirect_url` (domain-only matches do not link; numbers one digit apart do not link).
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
| 7 | `report_builder` interface (M3/M4/M5) | Frozen interface and report keys in sections 3 and 6. Signature takes `candidates` and `engine_outputs` because label and evidence are not in `combine` results. Cluster-record structure is [OPEN] for Member 3. |
| 13 | Who sets `ring_id` | Null in `combine` results; the report builder fills it in its report copy from `clusters` |
| 14 | Report determinism | Sorted results and clusters, no generated-at timestamp, so the SHA-256 is reproducible |
| 8 | Official exclusion (M3) | Section 2: before scoring, cannot be overridden |
| 9 | Contact/redirect as social signals (M2) | Exposed as `indicators`, not scored |
| 10 | Identifier display (M5) | `identifier` = `username` (social) / `package_id` (app); UI shows display_name or app_name as the label via lookup |
| 11 | Display/brand fields (M5) | Not added to the result schema; report data carries `brand` and per-record `label` (M4) |
| 12 | Null behaviour and hash claim (M5) | Section 4 and section 6 |
| 15 | `score_engine.combine()` input contract (M2/M3/M4) | Member 1 ruling: keep the one-argument signature. Each engine output must include `entity_id`, `target_type`, `platform`, `identifier`, `is_official`, `exclusion_reason`, `signals`, `evidence_source`, and nullable `evidence_timestamp`; `indicators` and `evidence` remain available for clustering/reporting only. Exact field rules are in section 3. Member 4 to acknowledge this contract before sign-off. |
| 16 | Candidate-to-report label flow (M4/M5) | Member 1 ruling: retain `report_builder.build_report(results, brand, candidates, engine_outputs, clusters=None)`. `candidates` supplies labels by `entity_id` (`display_name` for social; `app_name` for apps); `engine_outputs` supplies `evidence`; `results` remains frozen. No label or evidence fields are added to `combine()` output. Member 4 and Member 5 to acknowledge this contract before sign-off. |

## 10. Sign-off
| Member | Role | Signed (name, hour) |
|---|---|---|
| 1 | Data & Evaluation | |
| 2 | Social & Normalization | |
| 3 | App & Clustering | |
| 4 | Scoring & Report Data | |
| 5 | UI, Export & Deployment | |