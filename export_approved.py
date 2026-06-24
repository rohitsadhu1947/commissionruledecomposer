"""
Export the FINAL, platform-ready catalog by baking review decisions into it.

Reads:
  rules_catalog.json  - the atomic catalog (build_rule_catalog.py)
  rules_review.json   - per-rule sign-off (written by the Review-catalog tab)

Applies each decision:
  REJECTED  -> dropped
  CONFIRMED -> review_status=CONFIRMED; edited pay_in_pct / reason applied;
               reviewer + reviewed_ts stamped
  (none)    -> kept as review_status=PENDING (still needs sign-off; flagged)

Writes (same format/styling as the catalog):
  rules_catalog_approved.xlsx / .csv / .json
"""
import json
import os

# reuse the catalog's writers + column model so output styling matches exactly
import build_rule_catalog as cat

CATALOG_FILE = "rules_catalog.json"
REVIEW_FILE = "rules_review.json"

# approved export carries a few extra audit columns after the base catalog columns
EXTRA_COLS = ["reviewer", "reviewed_ts", "edited"]
APPROVED_COLUMNS = cat.COLUMNS + EXTRA_COLS


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def apply_reviews(rules, review):
    out, counts = [], {"confirmed": 0, "rejected": 0, "pending": 0, "edited": 0}
    for r in rules:
        d = review.get(r["catalog_id"])
        row = dict(r)
        row.setdefault("reviewer", "")
        row.setdefault("reviewed_ts", "")
        row.setdefault("edited", "")
        if not d:
            row["review_status"] = "PENDING"
            counts["pending"] += 1
            out.append(row)
            continue
        status = d.get("status", "PENDING")
        if status == "REJECTED":
            counts["rejected"] += 1
            continue  # drop
        edited = False
        if d.get("pay_in_pct") not in (None, "") and str(d["pay_in_pct"]) != str(r.get("pay_in_pct")):
            row["pay_in_pct"] = d["pay_in_pct"]
            edited = True
        if d.get("reason") not in (None, "") and d["reason"] != r.get("reason"):
            row["reason"] = d["reason"]
            edited = True
        row["review_status"] = status  # CONFIRMED (or PENDING if explicitly set)
        row["reviewer"] = d.get("reviewer", "")
        row["reviewed_ts"] = d.get("ts", "")
        row["edited"] = "yes" if edited else ""
        if status == "CONFIRMED":
            counts["confirmed"] += 1
        else:
            counts["pending"] += 1
        if edited:
            counts["edited"] += 1
        out.append(row)
    return out, counts


def main():
    catalog = load(CATALOG_FILE, {"meta": {}, "rules": []})
    review = load(REVIEW_FILE, {})
    rows, counts = apply_reviews(catalog["rules"], review)

    meta = dict(catalog.get("meta", {}))
    meta["export"] = "approved (review decisions applied)"
    meta["review_summary"] = {**counts, "exported": len(rows)}

    # point the catalog writers at the approved column set + filenames
    cat.COLUMNS = APPROVED_COLUMNS
    cat.write_csv(rows, "rules_catalog_approved.csv")
    cat.write_json(rows, meta, "rules_catalog_approved.json")
    cat.write_xlsx(rows, meta, "rules_catalog_approved.xlsx")

    print("Approved catalog exported:")
    print(f"  CONFIRMED : {counts['confirmed']}  (of which edited: {counts['edited']})")
    print(f"  REJECTED  : {counts['rejected']}  (dropped)")
    print(f"  PENDING   : {counts['pending']}  (still need sign-off)")
    print(f"  EXPORTED  : {len(rows)} rows")
    print("  -> rules_catalog_approved.xlsx / .csv / .json")
    if counts["pending"]:
        print(f"  WARNING: {counts['pending']} rules are not yet reviewed (kept, flagged PENDING).")
    return meta["review_summary"]


if __name__ == "__main__":
    main()
