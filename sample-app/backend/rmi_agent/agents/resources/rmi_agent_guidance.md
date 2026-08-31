Data Guidance and Guardrails:

The following definitions and patterns are authoritative. Apply them directly
instead of exploring the data to rediscover them.

Table Routing (choose the table from user intent; do not query multiple
tables just to compare which is better):

* `recent_roads_data`: "current", "latest", "now", or real-time conditions,
  and any question about speed categories (jam/slow via
  `speed_reading_intervals`). data is restricted to past 60 days.
* `historical_travel_time`: historical trends, aggregations over past
  days/weeks, or batch analysis.
* `routes_status`: route operational state, validation errors, or filtering
  to active routes.

SQL Patterns and Conventions:

* Route length: actual length is `ST_LENGTH(route_geometry)`; the intended
  (configured) length is stored as JSON in `routes_status.route_attributes`,
  read it with
  `CAST(JSON_VALUE(route_attributes, '$.route_length_meters') AS FLOAT64)`.

* Deviated / looping routes: the routing API always returns a path from
  origin to destination, so when the intended (waypoint-biased) route is
  unavailable it returns a deviated route, which often manifests as loops.
  These are frequently associated with traffic or disruptions. Detect them
  two ways:
  * Length signal: compare actual `ST_LENGTH(route_geometry)` against the
    intended `route_length_meters` attribute; a large discrepancy indicates
    a deviation.
  * Path fingerprint: group by `ARRAY_TO_STRING(road_segment_ids, '|')` to
    isolate distinct physical path variants. Because `road_segment_ids` is
    an abstract sequence of Place IDs, this suppresses minor coordinate
    adjustments and surfaces only genuine reroutes.
  Handle per intent, do not auto-filter by default: when analyzing traffic
  on specific road segments, drop deviated rows (they add noise); when
  analyzing traffic or incidents, retain them and correlate with
  disruptions to explain the deviation.

Final Query Contract:

* The last query you execute must be the one that answers the request and
  must SELECT all requested columns. Do NOT run any query after it (no
  trailing COUNT or verification probes): the result of the last executed
  query is what gets submitted.

Data Trust and Anti-Churn Guardrails:

* Trust the documented schema above. The dataset contains exactly three
  tables: `historical_travel_time`, `recent_roads_data`, and `routes_status`.
  Ignore any `*_m` table variants and any other datasets; do not enumerate
  tables, search the catalog, or query `INFORMATION_SCHEMA`.
* Prefer answering directly. Avoid redundant re-derivation of a metric you
  already computed and avoid repeated volume probes (`COUNT(*)`,
  `COUNT(DISTINCT ...)`, `GROUP BY` distribution checks, `MIN`/`MAX`
  timestamp discovery) whose only purpose is to understand the shape of the
  data. However, when the mapping from the request to specific columns is
  genuinely non-obvious (for example, a field nested inside a JSON column
  such as `route_attributes`), it is fine to inspect the schema or sample a
  few rows to discover it before writing the final query.

Output Hygiene:

* State results directly in your final answer. Do not narrate your internal
  reasoning, tool usage, or step-by-step process (e.g., "Having processed the
  data, my next step is...").
