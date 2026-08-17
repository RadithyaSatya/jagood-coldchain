# datasets

Reserved for datasets shared across multiple services.

The Smart Route Planner's synthetic training data
(`synthetic_historical.csv`, `synthetic_corridors.json`) is
implementation-specific and lives under
[`services/ai/route-planner/`](../services/ai/route-planner/) instead. Put
something here only once a dataset is actually consumed by more than one
service.

The route-planner commodity lookup is also service-local. Its machine-readable provenance is in
`services/ai/route-planner/app/data/commodity_provenance.json`; all current commodity values are
classified `DEMO`, not real observations or FoodKeeper-derived reference records.
