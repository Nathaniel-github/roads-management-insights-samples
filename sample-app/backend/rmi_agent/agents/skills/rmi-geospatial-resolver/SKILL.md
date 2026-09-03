---
name: rmi-geospatial-resolver
description: >
  Resolves natural-language location references into BigQuery spatial
  SQL filters for RMI table queries. Covers place-name resolution
  (cities, counties, states, zip codes) and radius-based proximity
  searches.
metadata:
  adk_additional_tools:
    - resolve_location
---

# RMI Geospatial Resolver Skill

## When to Use This Skill

Activate this skill whenever the user's question involves a **geographic
location** — a city name, neighborhood, zip code, county, state, address, or a
proximity phrase like "within 5 miles of".

Examples:

-   "Show me routes in **Boston**"
-   "What is the average travel time for routes in **Suffolk County**?"
-   "Find all routes within **10 km of Logan Airport**"
-   "List routes passing through zip code **02134**"

## Tool: `resolve_location`

### Parameters

| Parameter       | Type   | Required | Description                           |
| :-------------- | :----- | :------- | :------------------------------------ |
| `location_name` | string | always   | The place to resolve (city, zip,      |
:                 :        :          : county, state, or address).           :
| `mode`          | string | always   | `"place"` or `"radius"`. See mode     |
:                 :        :          : selection below.                      :
| `radius_meters` | float  | radius   | Required when mode is `"radius"`. The |
:                 :        :          : search radius **in meters**.          :

### Mode Selection

Choose the mode based on the user's intent:

| User Intent                | Mode     | Example                           |
| :------------------------- | :------- | :-------------------------------- |
| Routes **in** a named area | `place`  | "Routes in Cambridge"             |
| Routes **near** a point    | `radius` | "Routes within 2 miles of Harvard |
:                            :          : Square"                           :

### Unit Conversion

The `radius_meters` parameter accepts **meters only**. Convert before calling:

-   1 mile = 1609.34 meters
-   1 kilometer = 1000 meters
-   1 foot = 0.3048 meters

### Return Value

The tool returns a dict:

```json
{
  "status": "SUCCESS",
  "sql_filter": "{{GEO_FILTER}}",
  "resolution_method": "bq_polygon",
  "resolved_name": "Boston (bq_city_zip_union)"
}
```

The full spatial filter is stashed internally. `sql_filter` contains the
placeholder `{{GEO_FILTER}}` which is automatically substituted with the real
filter when your SQL query executes.

### Embedding the Filter

Use `{{GEO_FILTER}}` literally in your BigQuery WHERE clause:

```sql
SELECT *
FROM `{PROJECT_ID}.{RMI_DATASET}.historical_travel_time`
WHERE {{GEO_FILTER}}
```

**DO NOT** attempt to inline or modify the placeholder. The system handles
substitution automatically at execution time.

### Combining with Other Filters

You can AND the spatial filter with other conditions:

```sql
SELECT selected_route_id, avg_travel_time_minutes
FROM `{PROJECT_ID}.{RMI_DATASET}.historical_travel_time`
WHERE {{GEO_FILTER}}
  AND day_of_week = 'Monday'
```

## Error Handling

| Status      | Action                                                    |
| :---------- | :-------------------------------------------------------- |
| `SUCCESS`   | Use the `sql_filter` in your query.                       |
| `NO_RESULT` | Tell the user the location could not be resolved. Suggest |
:             : rephrasing or using a zip code.                           :
| `ERROR`     | Fix the input (e.g., missing radius, invalid mode).       |
