"""BrandShield AI evaluation. Run: python evaluation.py
Uses the real engines if importable; otherwise MOCK engines so the harness can be tested early.
Ground-truth fields (ground_truth, category_note, expected_ring) are NEVER passed to the engines.
Adapt ONLY decide() and predicted_groups() to the signed CONTRACT.md."""
import json, os, re
from collections import defaultdict
from itertools import combinations

STATUSES = ["CLEARED", "NOT_FLAGGED", "FLAGGED"]
EXPECTED = {"official": "CLEARED", "impersonator": "FLAGGED", "benign": "NOT_FLAGGED"}
HIDDEN = ("ground_truth", "category_note", "expected_ring")

try:
    import social_engine, app_engine, score_engine
    MOCK = False
except ImportError:
    MOCK = True
try:
    import clustering
except ImportError:
    clustering = None

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def clean(r):
    return {k: v for k, v in r.items() if k not in HIDDEN}

def norm_phone(p):
    d = re.sub(r"\D", "", p or "")
    return d[-10:] if len(d) >= 10 else None

def norm_url(u):
    return re.sub(r"^https?://(www\.)?", "", (u or "").lower()).rstrip("/") or None

# ---------- engine adapters (edit to match CONTRACT.md) ----------
def mock_decide(brand, c):
    ident = (c.get("username") or c.get("package_id") or "").lower()
    official = [h.lower() for hs in brand["official_handles"].values() for h in hs] + \
               [a["package_id"].lower() for a in brand["official_apps"]]
    if ident in official:
        return dict(status="CLEARED", risk_score=0.0, review_required=False, reasons=["registered asset"])
    bad = any(w in json.dumps(c).lower() for w in ("otp", "verify", "urgent", "payment", "reward", "fee"))
    return dict(status="FLAGGED" if bad else "NOT_FLAGGED", risk_score=0.9 if bad else 0.1,
                review_required=False, reasons=["mock keyword rule"])

def decide(kind, brand, cand):
    if MOCK:
        return mock_decide(brand, cand)
    engine = social_engine if kind == "social" else app_engine
    return score_engine.combine(engine.evaluate(brand, cand))      # adapt if the contract differs

def predicted_groups(rows):
    """Return list of sets of entity_ids. Real: wrap clustering.py per CONTRACT. Mock: union FLAGGED records
    sharing a normalized phone or redirect URL."""
    flagged = [(r, o) for r, o in rows if o["status"] == "FLAGGED"]
    if clustering is not None and not MOCK:
        results = [o for _, o in rows]
        candidates = [clean(r) for r, _ in rows]
        return [set(c["linked_candidate_ids"]) for c in clustering.cluster(results, candidates)]
    parent = {r["entity_id"]: r["entity_id"] for r, _ in flagged}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for key in ("contact_number", "redirect_url"):
        seen = {}
        for r, _ in flagged:
            k = norm_phone(r.get(key)) if key == "contact_number" else norm_url(r.get(key))
            if k is None: continue
            if k in seen: parent[find(r["entity_id"])] = find(seen[k])
            else: seen[k] = r["entity_id"]
    groups = defaultdict(set)
    for r, _ in flagged:
        groups[find(r["entity_id"])].add(r["entity_id"])
    return [g for g in groups.values() if len(g) > 1]

# ---------- metrics ----------
def detection_metrics(rows):
    cm = {t: {s: 0 for s in STATUSES} for t in EXPECTED}          # truth x predicted status
    tp = fp = fn = tn = off_total = off_fp = review = 0
    errors, by_cat = [], defaultdict(lambda: [0, 0])
    for r, o in rows:
        truth, st = r["ground_truth"], o["status"]
        cm[truth][st] += 1
        flagged, bad = st == "FLAGGED", truth == "impersonator"
        if truth == "official":
            off_total += 1; off_fp += flagged
        tp += bad and flagged; fn += bad and not flagged
        fp += (not bad) and flagged; tn += (not bad) and not flagged
        review += bool(o.get("review_required"))
        ok = st == EXPECTED[truth]
        by_cat[r["category_note"]][0] += ok; by_cat[r["category_note"]][1] += 1
        if not ok:
            errors.append(dict(id=r["entity_id"], truth=truth, got=st, score=o.get("risk_score"),
                               note=r["category_note"], reasons=o.get("reasons")))
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    F = 2 * P * R / (P + R) if P + R else 0.0
    return dict(n=len(rows), tp=tp, fp=fp, fn=fn, tn=tn, precision=round(P, 3), recall=round(R, 3), f1=round(F, 3),
                official_assets=off_total, official_false_positives=off_fp, review_flagged=review,
                confusion_matrix=cm, errors=errors, per_category={k: f"{v[0]}/{v[1]}" for k, v in by_cat.items()})

def link_metrics(rows):
    """Pairwise: a 'link' is two records placed in the same group. False connections = links between records
    that do not share a ground-truth ring (benign, official, near-miss-phone, different ring)."""
    ring = {r["entity_id"]: r["expected_ring"] for r, _ in rows}
    true_pairs = {frozenset(p) for p in combinations([e for e, g in ring.items() if g], 2) if ring[p[0]] == ring[p[1]]}
    pred_pairs = {frozenset(p) for g in predicted_groups(rows) for p in combinations(sorted(g), 2)}
    tp, fp, fn = len(true_pairs & pred_pairs), len(pred_pairs - true_pairs), len(true_pairs - pred_pairs)
    P = tp / (tp + fp) if tp + fp else 1.0
    R = tp / (tp + fn) if tp + fn else 1.0
    return dict(true_links=len(true_pairs), predicted_links=len(pred_pairs), correct_links=tp,
                false_connections=fp, missed_links=fn, link_precision=round(P, 3), link_recall=round(R, 3),
                false_connection_pairs=sorted(tuple(sorted(p)) for p in pred_pairs - true_pairs))

def evaluate_split(brands, social_path, app_path):
    all_rows, res = [], {}
    for kind, path in (("social", social_path), ("app", app_path)):
        rows = [(r, decide(kind, brands[r["brand_id"]], clean(r))) for r in load(path)]
        res[kind] = detection_metrics(rows); all_rows += rows
    res["overall"] = detection_metrics(all_rows)
    res["links"] = link_metrics(all_rows)
    return res

def main():
    brands = {b["brand_id"]: b for b in load("data/brand_registry.json")["brands"]}
    splits = {"dev": evaluate_split(brands, "data/social_profiles.json", "data/app_listings.json")}
    if os.path.exists("holdout/social_profiles.json"):
        splits["holdout"] = evaluate_split(brands, "holdout/social_profiles.json", "holdout/app_listings.json")
    res = dict(splits)
    res["_meta"] = dict(engines="MOCK" if MOCK else "REAL", splits=list(splits),
                        note="Prototype results on simulated data; not real-world accuracy. "
                             "Hold-out is only unseen if no engine or threshold changed after its first run.")
    os.makedirs("reports", exist_ok=True)
    json.dump(res, open("reports/evaluation_results.json", "w"), indent=2)

    lines = [f"_Engines: {res['_meta']['engines']}. Simulated prototype data, not real-world accuracy._", "",
             "| Set | Target | N | Precision | Recall | F1 | Official FP | Review flags |", "|---|---|---|---|---|---|---|---|"]
    for name, sp in splits.items():
        for k in ("social", "app", "overall"):
            m = sp[k]
            lines.append(f"| {name} | {k} | {m['n']} | {m['precision']} | {m['recall']} | {m['f1']} | "
                         f"{m['official_false_positives']}/{m['official_assets']} | {m['review_flagged']} |")
    for name, sp in splits.items():
        lines += ["", f"Confusion matrix, {name} (rows: truth, columns: status)", "",
                  "| Truth \\ Status | CLEARED | NOT_FLAGGED | FLAGGED |", "|---|---|---|---|"]
        for t, row in sp["overall"]["confusion_matrix"].items():
            lines.append(f"| {t} | {row['CLEARED']} | {row['NOT_FLAGGED']} | {row['FLAGGED']} |")
        L = sp["links"]
        lines += ["", f"Possible-connection test, {name}: {L['correct_links']}/{L['true_links']} true links found, "
                  f"{L['false_connections']} false connections (link precision {L['link_precision']})."]
    open("reports/results_table.md", "w").write("\n".join(lines) + "\n")

    print("\n".join(lines))
    for name, sp in splits.items():
        for k in ("social", "app"):
            for e in sp[k]["errors"]:
                print(f"  [{name}/{k}] MISS {e['id']}: truth={e['truth']} got={e['got']} | {e['note']}")
        for p in sp["links"]["false_connection_pairs"]:
            print(f"  [{name}/link] FALSE CONNECTION", p)
    assert all(sp["overall"]["official_false_positives"] == 0 for sp in splits.values()), "Official asset was FLAGGED!"

if __name__ == "__main__":
    main()
