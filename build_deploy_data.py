"""
Precompute every data file the serverless app needs into api/_data/*.json so the
Vercel runtime never has to parse Excel (no openpyxl for reads, raw insurer grid
files never deployed). Run locally before each deploy when source data changes.

Multi-insurer registry: each insurer contributes an extractor that returns
(rate_rows, elig_rows, warnings) in the shared 27-column atomic schema, plus
geo maps (rto_code -> cluster labels, cluster label -> states).

Outputs:
  api/_data/rate_rules.json   - legacy TW RATE rules (poc_tw_extractor)
  api/_data/elig_rules.json   - legacy TW eligibility rules
  api/_data/catalog.json      - merged atomic catalog (all insurers)
  api/_data/geo.json          - {code2state, city2state, states} from the RTO master
  api/_data/clusters.json     - per-insurer {rto2clusters, cluster2states}
"""
import json
import os
from collections import Counter

from poc_tw_extractor import extract
import geo_normalize as gn
import build_rule_catalog as brc
import extract_4w_cv as cv
import rto_clusters as rc
import extract_chola as chola
import extract_godigit as godigit
import extract_misc_4w as misc

OUT = os.path.join("api", "_data")


def sbi_rows():
    """SBI General: legacy TW pipeline + the 4W/CV extractor."""
    rate_rules, warnings = extract()
    with open("poc_tw_notes_rules.json") as f:
        notes = json.load(f)
    elig_rules = notes["eligibility_rules"]
    rate_rows = brc.expand_rate(rate_rules)
    elig_rows = brc.expand_eligibility(elig_rules)
    cv_rate, cv_elig, cv_warn = cv.extract_rows()
    return (rate_rows + cv_rate, elig_rows + cv_elig,
            warnings + cv_warn + rc.WARNINGS, notes, rate_rules, elig_rules)


def main():
    os.makedirs(OUT, exist_ok=True)

    sbi_rate, sbi_elig, sbi_warn, notes, legacy_rate, legacy_elig = sbi_rows()
    ch_rate, ch_elig, ch_warn = chola.extract_rows()
    gd_rate, gd_elig, gd_warn = godigit.extract_rows()

    rows = sbi_rate + sbi_elig + ch_rate + ch_elig + gd_rate + gd_elig

    def tag(ws, ins):
        return [{**w, "insurer": ins} for w in ws]
    warnings = (tag(sbi_warn, "SBI_GENERAL") + tag(ch_warn, "CHOLA_MS")
                + tag(gd_warn, "GODIGIT"))

    misc_geo = {}
    for name, fn, geo in misc.INSURERS:
        m_rate, m_elig, m_warn = fn()
        rows += m_rate + m_elig
        warnings += tag(m_warn, name)
        if geo:
            r2c, c2s = geo()
            misc_geo[name] = {"rto2clusters": r2c, "cluster2states": c2s}

    catalog = {
        "meta": {
            "insurers": {
                "SBI_GENERAL": {"source_file": "Provincial sbi Grid revision__May'26 _w.e.f 11th May'26.xlsx",
                                "grid_version": notes.get("grid_version", {})},
                "CHOLA_MS": {"source_file": "June'26 Grid - Retail Broking Motor Cholamandalam.xlsx",
                             "grid_version": {"effective_from": "2026-06-01"}},
                "GODIGIT": {"source_file": "Large Broker Grid Jun'26  Godigit.xlsx",
                            "grid_version": {"effective_from": "2026-06-01"},
                            "note": "pay_in_pct = Max CD2; CD1 & Avg CD2 in source_text"},
                "TATA_AIG": {"source_file": "Tata_Pvt car _Energise Broker.xlsx",
                             "grid_version": {"effective_from": "2026-04-01", "effective_to": "2027-03-31"}},
                "CAT_B": {"source_file": "Motor Grid- CAT B Feb.xlsx",
                          "note": "INSURER NAME NOT IN FILE — confirm with team"},
                "HDFC_ERGO": {"source_file": "HDFC_SATP Grid NEW.xlsx"},
                "ICICI_LOMBARD": {"source_file": "ICICI_Pvt Car Grid_June 26 Final M2B.xlsx",
                                  "grid_version": {"effective_from": "2026-06-01"}},
            },
            "counts": {
                "total": len(rows),
                "rate": sum(1 for r in rows if r["rule_type"] == "RATE"),
                "eligibility": sum(1 for r in rows if r["rule_type"] == "ELIGIBILITY"),
                "by_insurer": dict(Counter(r["insurer"] for r in rows)),
                "by_category": dict(Counter(r["category"] for r in rows)),
            },
            "geography": "source labels preserved; canonical_state via RTO master; "
                         "cluster/state-group spans in clusters.json",
            "expansion": "atomic (one source cell per row)",
            "warnings": warnings,
        },
        "rules": rows,
    }

    geo = {
        "code2state": gn._CODE2STATE,
        "city2state": gn._CITY2STATE,
        "states": sorted(gn._STATES),
        "aliases": gn._ALIASES,
    }

    ch_r2c, ch_c2s = chola.geo_maps()
    gd_r2c, gd_c2s = godigit.geo_maps()
    clusters = {
        "SBI_GENERAL": {"rto2clusters": {k: [v] for k, v in rc.RTO2CLUSTER.items()},
                        "cluster2states": rc.CLUSTER2STATES,
                        "source_file": "Broker Enabler GCV__Apr 26 _w.e.f 22nd April-26.xlsx"},
        "CHOLA_MS": {"rto2clusters": ch_r2c, "cluster2states": ch_c2s},
        "GODIGIT": {"rto2clusters": gd_r2c, "cluster2states": gd_c2s},
        **misc_geo,
    }

    def dump(name, obj):
        with open(os.path.join(OUT, name), "w") as f:
            json.dump(obj, f, separators=(",", ":"))
        print(f"  {name:18} {os.path.getsize(os.path.join(OUT, name)):>9} bytes")

    print("Precomputed deploy data:")
    dump("rate_rules.json", legacy_rate)
    dump("elig_rules.json", legacy_elig)
    dump("catalog.json", catalog)
    dump("geo.json", geo)
    dump("clusters.json", clusters)
    print(f"  ({len(rows)} catalog rows: "
          f"{dict(Counter(r['insurer'] for r in rows))}, {len(warnings)} warnings)")


if __name__ == "__main__":
    main()
