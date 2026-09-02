---
name: rmi-disruptions-grounding
description: >
  Real-time road disruption incidents from the RMI disruptions BigQuery
  dataset. Covers disruption type filtering and counts, active/time-window
  selection, confidence filtering via confirm/deny votes, and duration or
  severity ranking of incidents and corridors. Use when the user asks about
  disruptions, incidents, crashes, closures, lane closures, construction,
  flooding, stalled vehicles, objects on the road, or which roads are most
  affected by incidents.
---

# RMI Disruptions Grounding Skill

## Tables

-   **`disruptions_nested`** (curated; use this by default): one row per
    disruption incident, with native `TIMESTAMP`/`GEOGRAPHY` columns and a
    nested `events` array of vote/state intervals.
-   **`disruptions_raw`** (raw Pub/Sub landing; lineage/debugging only): one
    row per observation snapshot. Timestamps and coordinates are nested
    structs, not native types (see Caveats).

Qualify every table as `` `{PROJECT_ID}.{DISRUPTIONS_DATASET}.<table>` ``.
Disruptions join to the route tables on `selected_route_id`.

## Disruption Type Enum

`disruption_type` values always carry the full `RESPONSE_DISRUPTION_TYPE_`
prefix. Suggested severity tiers below are a heuristic for ranking/labeling;
ask the user if they want a different ordering.

| `disruption_type` value                    | Label           | Severity tier |
| ------------------------------------------ | --------------- | ------------- |
| `RESPONSE_DISRUPTION_TYPE_ROAD_CLOSED`     | Road closed     | Critical      |
| `RESPONSE_DISRUPTION_TYPE_CRASH`           | Crash           | High          |
| `RESPONSE_DISRUPTION_TYPE_FLOOD`           | Flood           | High          |
| `RESPONSE_DISRUPTION_TYPE_LANE_CLOSURE`    | Lane closure    | Medium        |
| `RESPONSE_DISRUPTION_TYPE_CONSTRUCTION`    | Construction    | Medium        |
| `RESPONSE_DISRUPTION_TYPE_STALLED_VEHICLE` | Stalled vehicle | Medium        |
| `RESPONSE_DISRUPTION_TYPE_OBJECT_ON_ROAD`  | Object on road  | Low           |
| `RESPONSE_DISRUPTION_TYPE_UNPLOWED_ROAD`   | Unplowed road   | Low           |
| `RESPONSE_DISRUPTION_TYPE_SLIPPERY_ROAD`   | Slippery road   | Low           |
| `RESPONSE_DISRUPTION_TYPE_FOG`             | Fog             | Low           |

## Patterns

### D1. Type filter / count

-   **Triggers**: "how many crashes", "count by type", "how many lane
    closures", "which incident types are most common"
-   Filter a single type with the full enum value; count with `GROUP BY`.

```sql
SELECT
  disruption_type,
  COUNT(*) AS disruption_count
FROM `{PROJECT_ID}.{DISRUPTIONS_DATASET}.disruptions_nested`
-- Optional single-type filter:
-- WHERE disruption_type = 'RESPONSE_DISRUPTION_TYPE_CRASH'
GROUP BY disruption_type
ORDER BY disruption_count DESC
```

### D2. Active / time window

-   **Triggers**: "active disruptions", "incidents right now", "disruptions on
    July 4", "incidents last week"
-   An incident is active between `first_seen_time` and `last_seen_time`. To
    find incidents active at a reference instant, bracket that instant; to
    filter by when incidents began, range on `start_time`.

```sql
SELECT
  disruption_id,
  disruption_type,
  display_name,
  first_seen_time,
  last_seen_time
FROM `{PROJECT_ID}.{DISRUPTIONS_DATASET}.disruptions_nested`
WHERE first_seen_time <= TIMESTAMP('2026-07-15 08:00:00', '<TIMEZONE>')
  AND last_seen_time  >= TIMESTAMP('2026-07-15 08:00:00', '<TIMEZONE>')
-- Or filter by start date range instead:
-- WHERE start_time >= TIMESTAMP('2026-07-04', '<TIMEZONE>')
--   AND start_time <  TIMESTAMP('2026-07-05', '<TIMEZONE>')
```

### D3. Confidence filtering

-   **Triggers**: "confirmed incidents", "high-confidence disruptions", "ignore
    likely-cleared incidents"
-   `max_confirm_votes` / `max_deny_votes` are the peak cumulative user
    confirm/deny votes. Net-confirmed means confirms exceed denies; tighten
    with a margin for "high confidence" (threshold is tunable — ask the user).

```sql
SELECT
  disruption_id,
  disruption_type,
  display_name,
  max_confirm_votes,
  max_deny_votes
FROM `{PROJECT_ID}.{DISRUPTIONS_DATASET}.disruptions_nested`
WHERE max_confirm_votes > max_deny_votes            -- net-confirmed
-- High-confidence variant (tunable margin):
-- WHERE max_confirm_votes >= max_deny_votes + 5
ORDER BY max_confirm_votes DESC
```

### D4. Duration / severity ranking

-   **Triggers**: "longest disruptions", "most disruptive incidents", "which
    roads are most affected", "worst corridors"
-   Rank individual incidents by `active_duration_minutes`, or aggregate per
    corridor (`display_name`) by count and total active minutes.

```sql
-- Longest-running individual incidents:
SELECT
  disruption_id,
  disruption_type,
  display_name,
  active_duration_minutes
FROM `{PROJECT_ID}.{DISRUPTIONS_DATASET}.disruptions_nested`
ORDER BY active_duration_minutes DESC
LIMIT 20
```

```sql
-- Most-affected corridors:
SELECT
  display_name,
  COUNT(*) AS disruption_count,
  SUM(active_duration_minutes) AS total_active_minutes
FROM `{PROJECT_ID}.{DISRUPTIONS_DATASET}.disruptions_nested`
GROUP BY display_name
ORDER BY total_active_minutes DESC
LIMIT 20
```

## Caveats

1.  **Enum prefix**: `disruption_type` values always start with
    `RESPONSE_DISRUPTION_TYPE_`. Always filter on the full value (e.g.
    `'RESPONSE_DISRUPTION_TYPE_CRASH'`), never the bare label.

2.  **Prefer `disruptions_nested`**: it has one clean row per incident with
    native `TIMESTAMP`/`GEOGRAPHY`/`INTEGER` columns. Only touch
    `disruptions_raw` for lineage/debugging — there `start_time` and
    `retrieval_time` are `{seconds, nanos}` structs (convert with
    `TIMESTAMP_SECONDS(start_time.seconds)`) and `centroid` is a
    `{latitude, longitude}` struct, not native types.

3.  **Timezone**: all timestamps are UTC. Apply `AT TIME ZONE '<TIMEZONE>'`
    (e.g. `'America/New_York'`) when extracting local hour/day, and anchor
    literal cutoffs with `TIMESTAMP('YYYY-MM-DD', '<TIMEZONE>')`.

4.  **Active-window semantics**: use `first_seen_time`/`last_seen_time` to test
    whether an incident was active at an instant. Sample data covers roughly
    July 2026, so "active now" relative to today may return zero rows — use a
    reference instant inside the coverage window.

5.  **Spatial is out of scope here**: `centroid`/`geometry` exist on
    `disruptions_nested`, but the `{{GEO_FILTER}}` geo tool is built around the
    route `route_geometry` column and does not apply to disruption tables. Do
    not emit the `{{GEO_FILTER}}` placeholder against disruption tables.

6.  **Votes are cumulative peaks**: `max_confirm_votes`/`max_deny_votes` are
    the peak totals over the incident lifecycle; use a net or margin
    comparison for confidence rather than a single raw count.
