"""
Geo lookup that works in BOTH environments:
  - serverless (api/ on sys.path): reuse api/_engine's geo.json-backed to_state,
    so the RTO master Excel is never needed (and never deployed)
  - local build (build_deploy_data.py): fall back to geo_normalize (RTO.xlsx)
"""
try:
    import _engine as _g  # available when api/ is on sys.path (Vercel runtime)
    to_state = _g.to_state
    CODE2STATE = _g._CODE2STATE
except ImportError:
    from geo_normalize import to_state, _CODE2STATE as CODE2STATE  # noqa: F401
