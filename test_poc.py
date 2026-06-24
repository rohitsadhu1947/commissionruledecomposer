"""
Hard test suite for the TW extraction POC + resolution engine.

Run: python3 test_poc.py
No external test framework needed; prints PASS/FAIL per check and exits non-zero on any failure.
"""
import json
import sys
import openpyxl
from openpyxl.utils import column_index_from_string

from poc_tw_extractor import extract, CONFIG, FILE, num
from resolution_engine import resolve_rate, _cc_in_band

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


rules, warnings = extract()
wb = openpyxl.load_workbook(FILE, data_only=True)
ws = wb[CONFIG["grid_version"]["source_sheet"]]

print("\n[1] Extraction integrity")
# 1a. every emitted rule's value equals the actual cell it cites (no silent drift)
mismatch = []
for r in rules:
    cell = r["source"]["cell"]
    col = column_index_from_string(''.join(filter(str.isalpha, cell)))
    row = int(''.join(filter(str.isdigit, cell)))
    if num(ws.cell(row=row, column=col).value) != r["effect"]["value"]:
        mismatch.append(cell)
check("every rule value matches its source cell", not mismatch, f"mismatched: {mismatch[:5]}")

# 1b. no rule was emitted from a blank cell (blank != 0% rate)
blanks = [r["source"]["cell"] for r in rules if r["effect"]["value"] is None]
check("no rule emitted for blank cell", not blanks, str(blanks[:5]))

# 1c. column correctness: TW must read ONLY AD/AE/AF. AB/AC are Pvt Car; Z/AA are School Bus.
src_cols = {''.join(filter(str.isalpha, r["source"]["cell"])) for r in rules}
check("TW source columns are AD/AE/AF only (no Pvt Car / School Bus bleed)",
      src_cols <= {"AD", "AE", "AF"}, str(src_cols))
# the Pvt Car values that fooled the first cut (28/25, 30/27) must NOT be TW rates here
check("Pvt Car constant 55/57 (School Bus) never captured as TW",
      55.0 not in {r["effect"]["value"] for r in rules})

# 1d. cc bands are sane and non-degenerate
bad_band = [r["rule_id"] for r in rules
            if r["scope"]["cc_band"]["max_cc"] is not None
            and r["scope"]["cc_band"]["min_cc"] >= r["scope"]["cc_band"]["max_cc"]]
check("all cc bands well-formed (min < max)", not bad_band, str(bad_band[:5]))

# 1e. provenance + review status present on every rule
check("every rule carries provenance + PENDING review",
      all(r["source"]["cell"] and r["source"]["review_status"] == "PENDING" for r in rules))

print("\n[2] Known-value spot checks (read independently from the sheet)")
def find(state, sub, maxcc):
    for r in rules:
        if (r["scope"]["state"] == state and r["scope"]["sub_segment"] == sub
                and r["scope"]["cc_band"]["max_cc"] == maxcc):
            return r
    return None
kol_s = find("Kolkata", "SCOOTER", 150)
check("Kolkata scooter <=150 = 35%", kol_s and kol_s["effect"]["value"] == 35.0,
      str(kol_s["effect"]["value"] if kol_s else None))
kol_b = find("Kolkata", "BIKE", 125)
check("Kolkata bike <=125 = 23.5% (the column the user spotted)",
      kol_b and kol_b["effect"]["value"] == 23.5, str(kol_b["effect"]["value"] if kol_b else None))
blr = find("Bangalore", "SCOOTER", 150)
check("Bangalore scooter <=150 = 50%", blr and blr["effect"]["value"] == 50.0,
      str(blr["effect"]["value"] if blr else None))
# Assam TW is blank on this sheet -> must produce NO rules (was wrongly '30' before the fix)
assam_any = [r for r in rules if r["scope"]["state"] == "ASSAM"]
check("Assam has no TW rules (blank in sheet)", not assam_any, f"{len(assam_any)} found")
# 'Above 125cc' is empty everywhere -> zero rules with min_cc 125
above = [r for r in rules if r["scope"]["cc_band"]["min_cc"] == 125]
check("no Above-125cc rules (column empty)", not above, f"{len(above)} found")

print("\n[3] Resolution engine — cc band boundaries")
band125 = {"min_cc": 0, "max_cc": 125}
band_above = {"min_cc": 125, "max_cc": None}
check("125cc falls in <=125 band", _cc_in_band(125, band125))
check("125cc NOT in above-125 band", not _cc_in_band(125, band_above))
check("126cc in above-125 band", _cc_in_band(126, band_above))
check("scooter 150 in 0-150 band", _cc_in_band(150, {"min_cc": 0, "max_cc": 150}))
check("151 not in 0-150 band", not _cc_in_band(151, {"min_cc": 0, "max_cc": 150}))

print("\n[4] Resolution engine — end to end")
# Scooter 110cc COMP in Kolkata -> Kolkata scooter rule (35%)
res = resolve_rate(rules, {"category": "TW", "sub_segment": "SCOOTER", "cc": 110,
                            "policy_type": "COMP", "state": "Kolkata"})
check("resolve Kolkata scooter COMP 110cc -> 35%", res and res["pay_in_pct"] == 35.0, str(res))
# SAOD also valid (policy_type list includes SAOD)
res_saod = resolve_rate(rules, {"category": "TW", "sub_segment": "SCOOTER", "cc": 110,
                                 "policy_type": "SAOD", "state": "Kolkata"})
check("resolve Kolkata scooter SAOD 110cc -> 35%", res_saod and res_saod["pay_in_pct"] == 35.0)
# Bike 100cc COMP in Kolkata -> 23.5%
res_bike = resolve_rate(rules, {"category": "TW", "sub_segment": "BIKE", "cc": 100,
                                 "policy_type": "COMP", "state": "Kolkata"})
check("resolve Kolkata bike 100cc -> 23.5%", res_bike and res_bike["pay_in_pct"] == 23.5, str(res_bike))
# Bike 200cc (>125) anywhere -> no rule (Above-125 column empty) -> reject, not a wrong %
res_big = resolve_rate(rules, {"category": "TW", "sub_segment": "BIKE", "cc": 200,
                                "policy_type": "COMP", "state": "Kolkata"})
check("Kolkata bike 200cc -> no match (>125 not rated)", res_big is None, str(res_big))
# Negative: a category we didn't extract -> no match
res_none = resolve_rate(rules, {"category": "GCV", "cc": 110, "policy_type": "COMP", "state": "Kolkata"})
check("GCV risk -> no TW rule matches", res_none is None)
# Negative: a state with no TW rule (TW blank) -> no match
res_blank = resolve_rate(rules, {"category": "TW", "sub_segment": "SCOOTER", "cc": 110,
                                  "policy_type": "COMP", "state": "ASSAM"})
check("Assam scooter (blank in sheet) -> no match", res_blank is None, str(res_blank))

print("\n[5] Specificity / no double-counting")
# A bike 100cc COMP in Kolkata must resolve to the <=125 rule, not the above-125 rule
res_small = resolve_rate(rules, {"category": "TW", "sub_segment": "BIKE", "cc": 100,
                                  "policy_type": "COMP", "state": "Kolkata"})
kol_small = find("Kolkata", "BIKE", 125)
check("Kolkata bike 100cc -> <=125 rule", res_small and res_small["rule_id"] == kol_small["rule_id"])
# only one band should match a given cc for a given sub_segment+state
matches = [r for r in rules if r["scope"]["state"] == "Kolkata"
           and r["scope"]["sub_segment"] == "BIKE" and _cc_in_band(100, r["scope"]["cc_band"])]
check("exactly one Kolkata BIKE band matches 100cc", len(matches) == 1, f"{len(matches)} matched")

print("\n[6] Anomaly surfacing")
# Karnataka rows (scooter rated, bike blank) must be flagged
kar_flagged = any("Bike" in w.get("issue", "") and w.get("state") in ("Bangalore", "ROKarnataka")
                  for w in warnings)
check("Karnataka scooter-without-bike flagged", kar_flagged, str(warnings[:2]))
# the empty 'Above 125cc' column must be flagged at sheet level
check("empty Above-125cc column flagged at sheet level",
      any(w.get("scope") == "sheet" and "Above 125cc" in w.get("issue", "") for w in warnings))

print(f"\n==== {PASS} passed, {FAIL} failed ====")
sys.exit(1 if FAIL else 0)
