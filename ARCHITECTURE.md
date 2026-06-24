# Commission Grid Extraction — Architecture & Rule Schema

Goal: ingest an insurer's commission **pay-in** grid (Excel), normalize it into a
canonical, editable rule store set up once, then maintained (add/update/delete) by
customers. Designed **multi-insurer** from the start — insurer-specific quirks live in
config/mapping, never in the core engine.

---

## 1. Core idea — three rule types over one shared dimension vocabulary

Every line in any insurer grid reduces to one of three rule types. They share the same
"scope" vocabulary (the dimensions that say *where a rule applies*).

| Rule type     | Answers                                   | Effect payload                               |
|---------------|-------------------------------------------|----------------------------------------------|
| `RATE`        | "what % do I earn here?"                   | `{ value, applies_on: OD\|NET\|TP }`         |
| `ELIGIBILITY` | "can I write this business at all?"        | `{ allowed: bool, reason }`                  |
| `MODIFIER`    | "what adjusts the base %?"                 | `{ op: ADD\|SUBTRACT\|SET, value, when }`    |

- Grid **cells** → `RATE` rules (deterministic extraction).
- Decline / doable lists in the **Notes** text → `ELIGIBILITY` rules (LLM-assisted).
- "−5% on Non-NCB", "−3% age 1-9y", "<25L → −2%", "+2% DL reg" → `MODIFIER` rules.

This separation is what makes it multi-insurer: every insurer maps to the same three
tables; only the *mapping config* differs.

---

## 2. Canonical dimension vocabulary (the `scope`)

A scope is a set of predicates. Absent dimension = "applies to all". Insurer raw labels
are normalized into these via a per-insurer mapping dictionary.

- `category`        : PVT_CAR | GCV | PCV | MISD | TW
- `sub_segment`     : free but controlled, e.g. SCOOTER | BIKE | TAXI | SCHOOL_BUS | TRACTOR | AUTO_3W
- `gvw_band`        : { min_t, max_t }            (GCV)
- `cc_band`         : { min_cc, max_cc }          (TW, Pvt Car SATP, PCV taxi)
- `seating`         : { min, max }                (PCV)
- `make_group`      : TATA_AL | MAHINDRA | OTHER | <specific make>
- `make`, `model`   : for decline lists / high-end enabler
- `fuel`            : PETROL | DIESEL | CNG | LPG | EV | HYBRID  (or a fuel group set)
- `age_band`        : { is_new, min_years, max_years }   (covers New / 0-5 / 1-5 / 5+ / 1-9 / 10+)
- `policy_type`     : COMP | SATP | SAOD | PACKAGE | LIABILITY
- `cover_variant`   : NIL_DEP | NON_NIL_DEP        (taxi)
- `ncb_status`      : NCB | NON_NCB
- `rto_cluster`     : cluster name (FK → RTO Cluster Master, already in Ensuredit)
- `state`, `region` : optional coarser geo
- `idv_band`        : { min, max }                 (e.g. IDV > 2Cr → refer UW)
- `premium_slab`    : { min, max }                 (e.g. < 25L → −2%)
- `registration_state` : e.g. DL                   (+2% rule)

---

## 3. Canonical rule object (JSON)

```jsonc
{
  "rule_id": "uuid",
  "insurer": "SBI_GENERAL",
  "grid_version": {
    "effective_from": "2026-05-11",
    "effective_to":   "2026-05-31",
    "source_file":    "Provincial sbi Grid revision__May'26 ...xlsx",
    "source_sheet":   "PCV, MISD & TW"
  },
  "rule_type": "RATE",
  "scope": {
    "category": "TW",
    "sub_segment": "SCOOTER",
    "cc_band": { "min_cc": 0, "max_cc": 150 },
    "policy_type": ["COMP", "SAOD"],
    "rto_cluster": "Kolkata",
    "term": "1+1"
  },
  "effect": { "value": 30, "applies_on": "NET" },
  "precedence": 100,
  "source": {
    "cell": "AB13",
    "raw_header": "Scooter upto 150 cc (Comp & SAOD)",
    "raw_row_label": "Kolkata",
    "confidence": 1.0,
    "review_status": "PENDING"   // PENDING | CONFIRMED | EDITED | REJECTED
  }
}
```

Same object for ELIGIBILITY (`effect.allowed`) and MODIFIER (`effect.op/value` + `scope` carries the condition, e.g. `ncb_status: NON_NCB`).

---

## 4. Resolution engine (how a quote gets a final %)

Given a fully-specified risk (category, cc, age, fuel, make/model, rto_cluster, policy_type, ncb, idv...):

1. **Eligibility gate** — if any matching `ELIGIBILITY` rule says `allowed:false`, reject (return reason).
2. **Base rate** — select the matching `RATE` rule with the *most specific* scope (specificity = count of bound dimensions; ties broken by `precedence`).
3. **Modifiers** — apply all matching `MODIFIER` rules in precedence order (SET overrides; ADD/SUBTRACT stack).
4. Return `{ pay_in_pct, applies_on, trace[] }` — trace lists every rule that fired (auditability).

---

## 5. Extraction pipeline

```
Excel ──▶ (1) Sheet classifier ──▶ (2) Header reconstruction ──▶ (3) Grid cell extractor ──▶ RATE rules
                                          │
                                          └──▶ (4) Notes/decline extractor (LLM) ──▶ ELIGIBILITY + MODIFIER rules
                                                                                          │
        (5) Label normalizer (raw → canonical) ◀──────────────────────────────────────────┘
                                          │
        (6) Validator (anomalies, offsets, 0-ambiguity) ──▶ (7) Versioning + diff vs prior ──▶ (8) Human review UI ──▶ ACTIVE
```

Key design points:
- **(2) Header reconstruction is the highest-risk step and MUST be human-confirmed.**
  Merged multi-row headers make it easy to bind the wrong column. In the SBI `PCV, MISD & TW`
  sheet the adjacent blocks are School Bus (Z/AA, flat 55/57) | Pvt Car (AB/AC) | 2-Wheeler
  (AD/AE/AF) — and a first cut mislabelled Pvt Car's AB/AC as the TW scooter/bike columns.
  Critically, a full self-consistency test suite still PASSED on the wrong mapping, because
  cell-value and band-math checks have no external ground truth for what a column *means*.
  Only a human spotted it (the "Bike ≤125 = 23.5" column). Lesson: the column→dimension
  mapping is config that a reviewer signs off once per insurer/sheet; automated tests guard
  against drift *after* that, they cannot establish semantic correctness on their own.
- **(4) Notes are natural language** and carry most of the complexity + monthly churn.
  Use LLM extraction with `confidence` + source sentence, always human-reviewed.
- **(6) Validators** must catch: cluster mislabels (sample has `BR` tagged "Karnataka"
  instead of Bihar), `0` meaning "declined" vs "genuine zero" ambiguity in SATP grid,
  blank vs not-allowed.
- **(7) Diff** is the real product for recurring uploads: same structure, changed
  percentages / decline lists / new segments → show the customer only what changed.

---

## 6. Multi-insurer strategy

Per insurer, you author a small **mapping config** (YAML/JSON), not new code:
- sheet → category/template binding
- header label → canonical dimension value (synonyms: "SATP", "Stand Alone TP", "Liability only")
- column offset / anchor rules
- notes terminology hints

The core schema, resolution engine, validator, and diff are shared and insurer-agnostic.
```
