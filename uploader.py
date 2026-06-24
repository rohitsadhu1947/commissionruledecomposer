"""
Server-side grid upload pipeline: insurer name + workbook bytes in, extracted
catalog rows + a validation/diff report out. The raw Excel is parsed strictly
in memory and never written to disk or stored — only the extracted rules are.

SBI_GENERAL is not uploadable here: its pipeline spans multiple source files
(grid + notes rules + RTO cluster map) and is rebuilt locally via
build_deploy_data.py.
"""
import io

import extract_chola
import extract_godigit
import extract_misc_4w as misc

SUPPORTED = {
    "CHOLA_MS": lambda b: extract_chola.extract_rows(io.BytesIO(b)),
    "GODIGIT": lambda b: extract_godigit.extract_rows(io.BytesIO(b)),
    "TATA_AIG": lambda b: misc.extract_tata(io.BytesIO(b)),
    "CAT_B": lambda b: misc.extract_catb(io.BytesIO(b)),
    "HDFC_ERGO": lambda b: misc.extract_hdfc(io.BytesIO(b)),
    "ICICI_LOMBARD": lambda b: misc.extract_icici(io.BytesIO(b)),
}

UNSUPPORTED_NOTE = {
    "SBI_GENERAL": "SBI spans multiple source files (grid + notes + RTO cluster map); "
                   "rebuild locally with build_deploy_data.py and redeploy.",
}


def _key(r):
    return (r.get("category"), r.get("sub_segment"), r.get("make"), r.get("model"),
            r.get("policy_type"), str(r.get("cc_min")), str(r.get("cc_max")),
            str(r.get("age_min")), str(r.get("age_max")), r.get("geo_label"))


def extract(insurer, data):
    if insurer not in SUPPORTED:
        raise ValueError(UNSUPPORTED_NOTE.get(insurer, f"no upload adapter for {insurer}"))
    try:
        rates, eligs, warns = SUPPORTED[insurer](data)
    except ValueError:
        raise
    except Exception as e:  # missing sheets / shifted layout / not-an-xlsx
        raise ValueError(f"could not parse this file as a {insurer} grid "
                         f"({type(e).__name__}: {e}) — wrong file, or the layout "
                         f"changed and the adapter needs updating")
    # F6: guard EVERY emitted row (rate AND eligibility), not just rates
    bad = [r for r in (rates + eligs) if r.get("insurer") != insurer]
    if bad:
        raise ValueError(f"extractor emitted rows for {bad[0].get('insurer')!r}; "
                         f"is this really a {insurer} grid?")
    if not rates:
        raise ValueError("no rate rows extracted — wrong file or layout changed; not stored")
    return rates, eligs, warns


def stats(rates, eligs, warns):
    from collections import Counter
    pays = [float(r["pay_in_pct"]) for r in rates if r.get("pay_in_pct") not in ("", None)]
    return {
        "rate_rows": len(rates),
        "elig_rows": len(eligs),
        "warnings": len(warns),
        "by_category": dict(Counter(r["category"] for r in rates)),
        "by_policy": dict(Counter(r["policy_type"] for r in rates)),
        "pay_min": min(pays) if pays else None,
        "pay_max": max(pays) if pays else None,
        "n_zero": sum(1 for p in pays if p == 0),
    }


def diff(new_rates, current_rules):
    """Dimension-level comparison against the insurer's currently active rules."""
    cur = {_key(r): r.get("pay_in_pct") for r in current_rules if r.get("rule_type") == "RATE"}
    new = {_key(r): r.get("pay_in_pct") for r in new_rates}
    added = [k for k in new if k not in cur]
    removed = [k for k in cur if k not in new]
    changed = [
        {"scope": " / ".join(str(x) for x in k if x not in ("", None)),
         "old": cur[k], "new": new[k]}
        for k in new if k in cur and str(new[k]) != str(cur[k])
    ]
    return {
        "current_rows": len(cur), "new_rows": len(new),
        "added": len(added), "removed": len(removed), "changed": len(changed),
        "unchanged": len(new) - len(added) - len(changed),
        "sample_changes": changed[:25],
    }
