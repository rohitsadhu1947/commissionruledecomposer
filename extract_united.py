"""
Extractor for United India Insurance Company — motor commission circular.

SOURCE IS A SCANNED PDF (united.pdf, Annexure A2 'Motor Department', pages 5-8)
plus an email note ("United email commission note.jpg"). There is NO extractable
text/cells in the PDF, so unlike the Excel insurers this grid was TRANSCRIBED
visually (OCR-by-read) into the structured tables below. Consequences:

  * values here are a faithful transcription of the "Maximum proposed Commission
    (w.e.f 01/04/2026)" column — the current effective rates.
  * a NEW United circular (a new scan) requires re-transcription; it CANNOT be
    refreshed via the self-serve Excel upload flow. (Not registered in uploader.)

Geo model: most rows carry a SPLIT commission — a lower rate for a specific list
of states and a higher rate for "Other than above States". We emit the
"other-states" rate as a PAN_INDIA row (specificity 0) and each listed state as
a STATE_OR_CITY row (specificity 1). The resolver's scoring then serves the
state-specific lower rate to a listed state and the PAN_INDIA rate to everyone
else — exactly the grid's intent.
"""
from catalog_schema import row

INSURER = "UNITED_INDIA"
SRC = "united.pdf"
EFF = "2026-04-01"

# canonical state names (match the RTO master)
TN, KL, KA, MP, AS = "TAMIL NADU", "KERALA", "KARNATAKA", "MADHYA PRADESH", "ASSAM"
HR, RJ, UP = "HARYANA", "RAJASTHAN", "UTTAR PRADESH"

_HE_MAKES = "Tata, Maruti, Mahindra, Toyota, Hyundai, Honda and Kia"


def extract_rows():
    rate_rows, elig_rows, warnings = [], [], []
    seq = {"TW": 0, "PVTCAR": 0, "PCV": 0, "GCV": 0, "MISD": 0}

    def nid(k):
        seq[k] += 1
        return f"UNITED-{k}-{seq[k]:04d}"

    def emit(k, category, sub_segment, pol, pct, state, page, **extra):
        geo = ({"geo_kind": "PAN_INDIA", "geo_label": "PAN_INDIA"} if state is None
               else {"geo_kind": "STATE_OR_CITY", "geo_label": state, "canonical_state": state})
        rate_rows.append(row(
            catalog_id=nid(k), source_rule_id=f"{SRC}#{page}",
            insurer=INSURER, rule_type="RATE", effect="RATE", pay_in_pct=pct,
            applies_on=extra.pop("applies_on", "NET"),
            category=category, sub_segment=sub_segment, policy_type=pol,
            make=extra.pop("make", ""), model=extra.pop("model", ""),
            cc_min=extra.pop("cc_min", ""), cc_max=extra.pop("cc_max", ""),
            **geo, source_sheet=f"{SRC} (scanned)", source_cell=page,
            source_text=extra.pop("text", f"{sub_segment} {pol}"),
            confidence=0.9, review_status="NEEDS_REVIEW", **extra))

    def split(k, category, sub_segment, pol, low_pct, low_states, high_pct, page, **extra):
        """lower rate for the listed states, higher rate for everyone else."""
        emit(k, category, sub_segment, pol, high_pct, None, page,
             text=f"{sub_segment} {pol} (other states)", **extra)
        for st in low_states:
            emit(k, category, sub_segment, pol, low_pct, st, page,
                 text=f"{sub_segment} {pol} ({st})", **dict(extra))

    # ----------------------------------------------------- TW (Annexure A2, p5)
    TW_LOW = [TN, KL, KA, MP, AS]
    split("TW", "TW", "TW UPTO 150CC", "COMP & SATP", 5.0, TW_LOW, 27.5, "p5",
          cc_min=0, cc_max=150)
    split("TW", "TW", "TW 150-350CC", "COMP & SATP", 5.0, TW_LOW, 27.5, "p5",
          cc_min=151, cc_max=350)
    split("TW", "TW", "TW ABOVE 350CC", "COMP & SATP", 5.0, TW_LOW, 17.5, "p5",
          cc_min=351, cc_max="")
    split("TW", "TW", "TW [ELECTRIC]", "COMP & SATP", 5.0, TW_LOW, 22.5, "p5")
    emit("TW", "TW", "TW (ALL BANDS INCL EV)", "SAOD", 20.0, None, "p5",
         text="TW SAOD all bands incl electric — 20% all states")

    # ----------------------------------------------- PCV (A2, p5-6)
    emit("PCV", "PCV", "PCV 2W (ALL CC)", "COMP", 10.0, None, "p6",
         text="2-wheeled PCV all CC — 10% all states")
    split("PCV", "PCV", "PCV 3W (ALL BANDS INCL EV)", "COMP", 25.0, [MP], 40.0, "p6")
    emit("PCV", "PCV", "PCV EDU INSTITUTION & STAFF BUS", "COMP", 62.5, None, "p6",
         text="Educational institution & staff buses (incl EV) — 62.5% all states")
    split("PCV", "PCV", "PCV TAXI (ALL CC INCL EV)", "COMP", 15.0, [HR, KA, RJ, TN, UP, MP], 25.0, "p6")
    # 4W PCV > 6 passengers (by passenger carrying capacity, PCC)
    split("PCV", "PCV", "PCV 4W >6 (PCC<=10)", "COMP", 10.0, [HR, RJ], 20.0, "p5")
    split("PCV", "PCV", "PCV 4W >6 (10<PCC<=20)", "COMP", 10.0, [TN, KA], 20.0, "p5")
    split("PCV", "PCV", "PCV 4W >6 (20<PCC<=30) [EXCEPT EV]", "COMP", 7.5, [TN, MP, UP], 10.0, "p5")
    for band in ("30<PCC<=40", "40<PCC<=50", "50<PCC<=60", "PCC>60"):
        emit("PCV", "PCV", f"PCV 4W >6 ({band}) [EXCEPT EV]", "COMP", 5.0, None, "p5",
             text=f"4W PCV >6 {band} except EV — 5% all states")
    emit("PCV", "PCV", "PCV 4W >6 (PCC<20) [ELECTRIC]", "COMP", 10.0, None, "p5",
         text="4W PCV >6 PCC<20 electric — 10% all states")

    # ----------------------------------------------- GCV by GVW (A2, p6-7)
    # (cc_min/cc_max carry the GVW band in Kg.)
    GCV = [
        ("GCV GVW<=2000",        0,     2000,  20.0, [UP],               57.5),
        ("GCV 2000<GVW<=3500",   2001,  3500,  15.0, [HR, MP, RJ, TN, UP], 56.5),
        ("GCV 3500<GVW<=7500",   3501,  7500,  10.0, [HR, RJ, TN, UP],   27.5),
        ("GCV 7500<GVW<=10000",  7501,  10000, 10.0, [MP, RJ, TN],       17.5),
        ("GCV 12000<GVW<=20000", 12001, 20000, 5.0,  [HR, MP, RJ, TN, KL], 15.0),
        ("GCV 20000<GVW<=25000", 20001, 25000, 5.0,  [HR, RJ, TN, MP, KL], 15.0),
        ("GCV 25000<GVW<=32000", 25001, 32000, 2.5,  [HR, MP, RJ, TN, KL], 12.5),
        ("GCV GVW>40000",        40001, "",    0.0,  [HR, MP, RJ, TN, KL], 5.0),
    ]
    for sub, lo, hi, low_pct, low_states, high_pct in GCV:
        split("GCV", "GCV", sub, "COMP & SATP", low_pct, low_states, high_pct, "p6",
              cc_min=lo, cc_max=hi)
    # all-state GCV bands
    emit("GCV", "GCV", "GCV 10000<GVW<=12000", "COMP & SATP", 2.5, None, "p6",
         cc_min=10001, cc_max=12000, text="GCV 10-12T — 2.5% all states")
    emit("GCV", "GCV", "GCV 32000<GVW<=40000", "COMP & SATP", 5.0, None, "p7",
         cc_min=32001, cc_max=40000, text="GCV 32-40T — 5% all states")
    emit("GCV", "GCV", "GCV E-CART", "COMP & SATP", 50.0, None, "p7",
         text="E-Cart — 50% all states")

    # ----------------------------------------------- MISD (A2, p7)
    emit("MISD", "MISD", "AMBULANCE", "COMP & SATP", 20.0, None, "p7", text="Ambulance 20%")
    emit("MISD", "MISD", "AGRICULTURAL TRACTOR", "COMP & SATP", 40.0, None, "p7", text="Agri Tractor 40%")
    emit("MISD", "MISD", "MISC VEHICLES", "COMP & SATP", 10.0, None, "p7", text="Misc vehicles 10%")
    emit("MISD", "MISD", "MOTOR TRADE", "COMP & SATP", 5.0, None, "p7", text="Motor Trade 5%")
    emit("MISD", "MISD", "STANDALONE CPA", "CPA", 15.0, None, "p7", text="Standalone CPA 15%")

    # ----------------------------------------------- PRIVATE CAR (A2, p8)
    # three segments per policy: Diesel<=1500cc | Above 2500cc EXCEPT the 7 makes |
    # all other. Commission on NET (OD & TP).
    def pc(policy_label, pol, btype, diesel_pct, highend_pct, other_pct):
        emit("PVTCAR", "PVT_CAR", f"PVT CAR {policy_label} [DIESEL <=1500CC]", pol,
             diesel_pct, None, "p8", cc_max=1500, make="DIESEL",
             text=f"{policy_label} diesel <=1500cc ({btype})")
        emit("PVTCAR", "PVT_CAR", f"PVT CAR {policy_label} [>2500CC EXCEPT {_HE_MAKES}]", pol,
             highend_pct, None, "p8", cc_min=2501, make=f"All except {_HE_MAKES}",
             text=f"{policy_label} >2500cc except {_HE_MAKES} ({btype})")
        emit("PVTCAR", "PVT_CAR", f"PVT CAR {policy_label}", pol,
             other_pct, None, "p8", text=f"{policy_label} all other segments ({btype})")

    pc("BUNDLED (1+3)", "COMP-NB", "New", 10.0, 10.0, 27.5)
    pc("PACKAGE", "COMP", "Renewal/Rollover", 5.0, 5.0, 20.0)
    pc("SAOD", "SAOD", "All", 5.0, 5.0, 20.0)
    emit("PVTCAR", "PVT_CAR", "PVT CAR [ELECTRIC]", "SAOD", 27.5, None, "p8",
         make="ELECTRIC", text="New EV SAOD/SATP — 27.5%")
    emit("PVTCAR", "PVT_CAR", "PVT CAR [ELECTRIC] [RENEWAL]", "COMP", 22.5, None, "p8",
         make="ELECTRIC", text="Renewal EV Package/SAOD/SATP — 22.5%")

    # --------- things referenced but on sub-annexures not in the captured pages
    warnings += [
        {"insurer": INSURER, "scope": "united.pdf", "cell": "Sub Annexure-2",
         "issue": "GCV 'other states' rates exclude a list of RTOs (Sub Annexure-2) that is "
                  "not in the captured pages — those RTO exclusions are NOT modelled."},
        {"insurer": INSURER, "scope": "united.pdf", "cell": "Sub Annexure-3 / p8 note",
         "issue": "Private Car preferred-city RTOs (Sub Annexure-3) get 40% commission — the "
                  "preferred-RTO list is not captured; 40% override NOT applied."},
        {"insurer": INSURER, "scope": "united.pdf", "cell": "p8 incentive table",
         "issue": "Private Car additional OD/TP incentive table (>1000-1500cc 2.5%/15%, "
                  ">2000cc 10%/10% etc.) is an add-on incentive, not folded into the base "
                  "commission rows."},
        {"insurer": INSURER, "scope": "source", "cell": "-",
         "issue": "United is transcribed from a SCANNED PDF (no machine-readable cells); "
                  "values flagged review_status=NEEDS_REVIEW. A new circular needs "
                  "re-transcription — it cannot be refreshed via the Excel upload flow."},
    ]
    return rate_rows, elig_rows, warnings


if __name__ == "__main__":
    from collections import Counter
    rates, eligs, warns = extract_rows()
    print(f"UNITED: {len(rates)} RATE, {len(eligs)} ELIG, {len(warns)} warnings")
    print("  by category:", dict(Counter(r["category"] for r in rates)))
    for s in rates[:6]:
        print("  e.g.", s["catalog_id"], s["sub_segment"], s["policy_type"],
              "=", s["pay_in_pct"], "@", s["geo_label"])
