"""
Tests for the TW eligibility gate (notes -> ELIGIBILITY rules) and end-to-end quote().
Run: python3 test_eligibility.py
"""
import json
import sys
from poc_tw_extractor import extract
from resolution_engine import check_eligibility, quote

rate_rules, _ = extract()
with open("poc_tw_notes_rules.json") as f:
    elig_rules = json.load(f)["eligibility_rules"]
mod_rules = []  # TW has no modifiers in this grid

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS  {name}")
    else: FAIL += 1; print(f"  FAIL  {name}  {detail}")

def declined_by(risk, rule_id):
    return any(rid == rule_id for rid, _ in check_eligibility(elig_rules, risk))

print("\n[A] Decline rules fire correctly")
# Sports/cruiser bike (TW2) declined for COMP regardless of state
check("KTM bike COMP (MH) declined by TW2",
      declined_by({"category": "TW", "sub_segment": "BIKE", "policy_type": "COMP",
                   "make": "KTM", "model": "Duke 390", "state": "MAHARASHTRA"}, "SBI-TW-ELIG-TW2"))
# Splendor (Hero) COMP in Bihar (TW1)
check("Hero Splendor bike COMP (BIHAR) declined by TW1",
      declined_by({"category": "TW", "sub_segment": "BIKE", "policy_type": "COMP",
                   "make": "Hero", "model": "Splendor Plus", "state": "BIHAR"}, "SBI-TW-ELIG-TW1"))
# TVS scooter COMP in MP (TW5)
check("TVS scooter COMP (MADHYA PRADESH) declined by TW5",
      declined_by({"category": "TW", "sub_segment": "SCOOTER", "policy_type": "COMP",
                   "make": "TVS", "model": "Jupiter", "state": "MADHYA PRADESH"}, "SBI-TW-ELIG-TW5"))
# Royal Enfield bike COMP in TN (TW5 RE list includes TN)
check("Royal Enfield bike COMP (TAMIL NADU) declined by TW5",
      declined_by({"category": "TW", "sub_segment": "BIKE", "policy_type": "COMP",
                   "make": "Royal Enfield", "model": "Classic 350", "state": "TAMIL NADU"}, "SBI-TW-ELIG-TW5"))
# 'all other makes' in CG/KL/MP (TW5 *OTHER*)
check("Honda scooter COMP (KERALA) declined by TW5 (all-other-makes)",
      declined_by({"category": "TW", "sub_segment": "SCOOTER", "policy_type": "COMP",
                   "make": "Honda", "model": "Activa", "state": "KERALA"}, "SBI-TW-ELIG-TW5"))
# SATP declined states (TW6)
check("scooter SATP (GUJARAT) declined by TW6",
      declined_by({"category": "TW", "sub_segment": "SCOOTER", "policy_type": "SATP",
                   "make": "Honda", "model": "Activa", "state": "GUJARAT"}, "SBI-TW-ELIG-TW6"))

print("\n[B] Allow-only (doable) lists")
# Scooter COMP allowed in HP (in TW3 list)
check("Honda scooter COMP (HIMACHAL PRADESH) NOT blocked by allow-only TW3",
      not declined_by({"category": "TW", "sub_segment": "SCOOTER", "policy_type": "COMP",
                       "make": "Honda", "model": "Activa", "state": "HIMACHAL PRADESH"}, "SBI-TW-ELIG-TW3"))
# Bike COMP in HP -> NOT in bike doable (TW4) -> declined
check("Honda bike COMP (HIMACHAL PRADESH) blocked by allow-only TW4",
      declined_by({"category": "TW", "sub_segment": "BIKE", "policy_type": "COMP",
                   "make": "Honda", "model": "Shine", "state": "HIMACHAL PRADESH"}, "SBI-TW-ELIG-TW4"))

print("\n[C] Policy-type specificity (COMP vs SAOD vs SATP)")
# A sports bike under SAOD is NOT declined by TW2 (COMP-only) nor TW4/TW6
saod_reasons = check_eligibility(elig_rules,
    {"category": "TW", "sub_segment": "BIKE", "policy_type": "SAOD",
     "make": "KTM", "model": "Duke 390", "state": "MAHARASHTRA"})
check("KTM bike SAOD (MH) NOT declined (TW2/TW4 are COMP-only, TW6 is SATP)", not saod_reasons, str(saod_reasons))

print("\n[D] Vehicle-age gate (G2)")
check("scooter COMP age 22y declined (>20y COMP cap)",
      declined_by({"category": "TW", "sub_segment": "SCOOTER", "policy_type": "COMP",
                   "make": "Honda", "model": "Activa", "state": "HIMACHAL PRADESH", "age_years": 22}, "SBI-GEN-ELIG-G2-COMP"))
check("scooter COMP age 5y NOT age-declined",
      not declined_by({"category": "TW", "sub_segment": "SCOOTER", "policy_type": "COMP",
                       "make": "Honda", "model": "Activa", "state": "HIMACHAL PRADESH", "age_years": 5}, "SBI-GEN-ELIG-G2-COMP"))

print("\n[E] End-to-end quote()")
# Eligible + has a grid rate -> ALLOW with %
q1 = quote(rate_rules, elig_rules, mod_rules,
           {"category": "TW", "sub_segment": "SCOOTER", "policy_type": "COMP", "cc": 110,
            "make": "Honda", "model": "Activa", "state": "HIMACHAL PRADESH", "age_years": 3})
check("HP Honda Activa scooter COMP -> ALLOW 35%", q1["decision"] == "ALLOW" and q1["pay_in_pct"] == 35.0, str(q1))
# Declined make -> DECLINE
q2 = quote(rate_rules, elig_rules, mod_rules,
           {"category": "TW", "sub_segment": "BIKE", "policy_type": "COMP", "cc": 200,
            "make": "KTM", "model": "Duke 390", "state": "MAHARASHTRA", "age_years": 2})
check("KTM bike COMP -> DECLINE", q2["decision"] == "DECLINE", str(q2))
# Eligible but no grid rate (HP scooter SAOD is fine, has rate 35) vs a state with no rate
q3 = quote(rate_rules, elig_rules, mod_rules,
           {"category": "TW", "sub_segment": "SCOOTER", "policy_type": "SAOD", "cc": 110,
            "make": "Honda", "model": "Activa", "state": "HIMACHAL PRADESH", "age_years": 3})
check("HP scooter SAOD -> ALLOW 35% (SAOD not gated by COMP/SATP notes)",
      q3["decision"] == "ALLOW" and q3["pay_in_pct"] == 35.0, str(q3))

print(f"\n==== {PASS} passed, {FAIL} failed ====")
sys.exit(1 if FAIL else 0)
