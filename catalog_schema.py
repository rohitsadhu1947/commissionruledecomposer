"""
The shared 27-column atomic catalog schema. One row == one platform rule ==
one source grid cell. Extracted here (out of build_rule_catalog) so the
serverless upload pipeline can import it without dragging in the SBI legacy
modules and their local-file dependencies.
"""

COLUMNS = [
    "catalog_id", "source_rule_id", "rule_type", "effect", "pay_in_pct", "applies_on",
    "insurer", "category", "sub_segment", "make", "model", "match",
    "cc_min", "cc_max", "policy_type",
    "geo_kind", "geo_label", "canonical_state", "rto_code",
    "age_min", "age_max",
    "reason", "source_sheet", "source_cell", "source_text", "confidence", "review_status",
]


def row(**kw):
    return {c: kw.get(c, "") for c in COLUMNS}
