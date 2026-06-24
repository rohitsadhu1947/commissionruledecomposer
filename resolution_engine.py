"""
Resolution engine (POC scope: RATE rules).

Given a fully-specified risk, returns the winning pay-in rate + an audit trace.
Selection = match on all bound scope dimensions, then most-specific wins
(specificity = number of bound dimensions), ties broken by `precedence`.

This is the insurer-agnostic core described in ARCHITECTURE.md section 4.
"""
from typing import Optional

try:
    from geo_normalize import to_state as _to_state
except Exception:  # RTO master not available -> fall back to identity
    _to_state = None


def _norm_state(s):
    """Canonicalize a geo label to its state via the RTO master; identity fallback."""
    if s is None:
        return None
    if _to_state is not None:
        return _to_state(s) or s.strip().upper()
    return s.strip().upper()


def _cc_in_band(cc, band):
    if band is None:
        return True
    lo = band.get("min_cc")
    hi = band.get("max_cc")
    # convention: lo exclusive, hi inclusive  -> (lo, hi]
    if lo is not None and not (cc > lo):
        return False
    if hi is not None and not (cc <= hi):
        return False
    return True


def _scope_matches(scope, risk):
    """All bound dimensions in scope must be satisfied by risk. Returns (ok, bound_count)."""
    bound = 0

    def check(dim, predicate):
        nonlocal bound
        if predicate is None:
            return True
        bound += 1
        return risk.get(dim) is not None and predicate(risk[dim])

    ok = True
    ok &= check("category", (lambda v: v == scope["category"]) if scope.get("category") else None)
    ok &= check("sub_segment", (lambda v: v == scope["sub_segment"]) if scope.get("sub_segment") else None)
    ok &= check("policy_type", (lambda v: v in scope["policy_type"]) if scope.get("policy_type") else None)
    ok &= check("rto_cluster",
                (lambda v: v.strip().lower() == scope["rto_cluster"].strip().lower()) if scope.get("rto_cluster") else None)
    ok &= check("state",
                (lambda v: _norm_state(v) == _norm_state(scope["state"])) if scope.get("state") else None)

    # cc_band is special: bound dimension, matched against risk['cc']
    if scope.get("cc_band") is not None:
        bound += 1
        if risk.get("cc") is None or not _cc_in_band(risk["cc"], scope["cc_band"]):
            ok = False

    return ok, bound


def _as_list(v):
    return v if isinstance(v, list) else [v]


def _make_match(risk_make, target):
    if target == "*OTHER*":
        return True  # "all other makes" -- caller must ensure specific makes checked first; here it matches any
    return risk_make is not None and target.lower() in risk_make.lower()


def _model_match(risk_model, models, mode=None):
    if models is None:
        return True
    if "ALL" in models:
        return True
    if risk_model is None:
        return False
    rm = risk_model.lower()
    return any(m.lower() in rm or rm in m.lower() for m in models)


def check_eligibility(elig_rules, risk) -> list:
    """Return a list of decline reasons. Empty list == eligible."""
    reasons = []
    rstate = _norm_state(risk.get("state"))  # canonical state for all geo comparisons
    for r in elig_rules:
        sc, eff = r["scope"], r["effect"]
        if sc.get("category") and risk.get("category") != sc["category"]:
            continue
        if sc.get("sub_segment") and risk.get("sub_segment") not in _as_list(sc["sub_segment"]):
            continue
        if sc.get("policy_type") and risk.get("policy_type") not in _as_list(sc["policy_type"]):
            continue

        # ALLOW_ONLY: eligible geos enumerated; anything outside is declined
        if eff.get("mode") == "ALLOW_ONLY":
            st_ok = rstate in {_norm_state(s) for s in eff.get("allowed_states", [])}
            rto_ok = risk.get("rto_code") in eff.get("allowed_rto_codes", [])
            if not (st_ok or rto_ok):
                reasons.append((r["rule_id"], eff["reason"]))
            continue

        # plain decline rules: a rule fires only if its bound geo/make/age predicates all match
        if "age_years_min" in sc:
            if risk.get("age_years") is None or risk["age_years"] < sc["age_years_min"]:
                continue

        if "states" in sc and "make_models" not in sc and "make_state_declines" not in sc:
            if rstate not in {_norm_state(s) for s in sc["states"]}:
                continue
            reasons.append((r["rule_id"], eff["reason"]))
            continue

        if "make_models" in sc:
            # optional state gate
            if "states" in sc and rstate not in {_norm_state(s) for s in sc["states"]}:
                continue
            hit = any(_make_match(risk.get("make"), mm["make"]) and _model_match(risk.get("model"), mm.get("models"), mm.get("match"))
                      for mm in sc["make_models"])
            if hit:
                reasons.append((r["rule_id"], eff["reason"]))
            continue

        if "make_state_declines" in sc:
            for msd in sc["make_state_declines"]:
                if rstate in {_norm_state(s) for s in msd["states"]} and _make_match(risk.get("make"), msd["make"]):
                    reasons.append((r["rule_id"], f'{eff["reason"]} ({msd["make"]})'))
                    break
            continue

        # rule with only category/sub/policy + age handled above -> applies
        if "age_years_min" in sc:
            reasons.append((r["rule_id"], eff["reason"]))
    return reasons


def apply_modifiers(mod_rules, risk, base_pct) -> tuple:
    pct, applied = base_pct, []
    for m in sorted(mod_rules, key=lambda x: x.get("precedence", 100)):
        sc, eff = m["scope"], m["effect"]
        ok = all([
            (not sc.get("category")) or risk.get("category") == sc["category"],
            (not sc.get("policy_type")) or risk.get("policy_type") in _as_list(sc["policy_type"]),
            (not sc.get("ncb_status")) or risk.get("ncb_status") == sc["ncb_status"],
            (not sc.get("segment")) or risk.get("segment") == sc["segment"],
        ])
        if not ok:
            continue
        op = eff["op"]
        if op == "SET":
            pct = eff["value"]
        elif op == "ADD":
            pct += eff["value"]
        elif op == "SUBTRACT":
            pct -= eff["value"]
        applied.append((m["rule_id"], op, eff["value"]))
    return pct, applied


def quote(rate_rules, elig_rules, mod_rules, risk) -> dict:
    declines = check_eligibility(elig_rules, risk)
    if declines:
        return {"decision": "DECLINE", "reasons": declines}
    base = resolve_rate(rate_rules, risk)
    if base is None:
        return {"decision": "NO_RATE", "reason": "No matching rate rule"}
    final, applied = apply_modifiers(mod_rules, risk, base["pay_in_pct"])
    return {"decision": "ALLOW", "pay_in_pct": final, "base_pct": base["pay_in_pct"],
            "applies_on": base["applies_on"], "rate_rule": base["rule_id"], "modifiers": applied}


def resolve_rate(rules, risk) -> Optional[dict]:
    candidates = []
    for r in rules:
        if r["rule_type"] != "RATE":
            continue
        ok, spec = _scope_matches(r["scope"], risk)
        if ok:
            candidates.append((spec, r["precedence"], r))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    winner = candidates[0][2]
    return {
        "pay_in_pct": winner["effect"]["value"],
        "applies_on": winner["effect"]["applies_on"],
        "rule_id": winner["rule_id"],
        "trace": [c[2]["rule_id"] for c in candidates],
    }
