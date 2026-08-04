The following is the schema for the historical_travel_time RMI BigQuery table:

Name                       | Mode     | Type      | Description
-------------------------- | -------- | --------- | -----------
selected_route_id          | NULLABLE | STRING    | The unique identifier for the SelectedRoute resource. It corresponds to the final component of the resource name: 'projects/{{project}}/selectedRoutes/{{selected_route_id}}'. Constraints: 4-63 characters, alphanumeric plus hyphens ([a-zA-Z0-9-]). This ID is used to subscribe to periodic road data collection via the Roads Selection API.
display_name               | NULLABLE | STRING    | User-provided descriptive name for the route. Unlike selected_route_id, this name does not need to be unique and is intended for human readability within reports and UIs.
record_time                | NULLABLE | TIMESTAMP | The UTC timestamp representing when the route data was computed. Data is periodically collected and written in hourly batches to this table.
duration_in_seconds        | NULLABLE | FLOAT     | The traffic-aware duration of the route in seconds. This value represents the estimated travel time considering current real-time traffic conditions at the 'record_time'.
static_duration_in_seconds | NULLABLE | FLOAT     | The traffic-unaware (static) duration of the route in seconds. This represents the estimated travel time under ideal or free-flow conditions, regardless of current traffic.
route_geometry             | NULLABLE | GEOGRAPHY | The traffic-aware polyline geometry of the route as a GEOGRAPHY object (WKT/GeoJSON). This represents the actual optimal path determined by the routing engine at 'record_time'.

The following is the schema for the recent_roads_data RMI BigQuery table:

Name                                         | Mode     | Type      | Description
-------------------------------------------- | -------- | --------- | -----------
selected_route_id                            | NULLABLE | STRING    | The unique identifier for the SelectedRoute resource. It corresponds to the final component of the resource name: 'projects/{{project}}/selectedRoutes/{{selected_route_id}}'. Constraints: 4-63 characters, alphanumeric plus hyphens ([a-zA-Z0-9-]). Use this ID to join with historical_travel_time and routes_status tables.
display_name                                 | NULLABLE | STRING    | User-provided descriptive name for the route. Intended for human readability and does not need to be unique.
record_time                                  | NULLABLE | TIMESTAMP | The UTC timestamp representing when the route data was computed. This table typically contains near real-time data with a 60-day retention period.
duration_in_seconds                          | NULLABLE | FLOAT     | The traffic-aware duration of the route in seconds, estimating travel time considering current real-time traffic conditions.
static_duration_in_seconds                   | NULLABLE | FLOAT     | The traffic-unaware (static) duration of the route in seconds, representing estimated travel time under ideal/free-flow conditions.
route_geometry                               | NULLABLE | GEOGRAPHY | The traffic-aware polyline geometry of the route as a GEOGRAPHY object, representing the actual optimal path at 'record_time'.
speed_reading_intervals                      | REPEATED | RECORD    | Intervals representing traffic density across the route. This field breaks down the route into segments based on traffic speed categories.
speed_reading_intervals.interval_coordinates | REPEATED | GEOGRAPHY | The GEOGRAPHY representation of the specific road segment for this speed interval.
speed_reading_intervals.speed                | NULLABLE | STRING    | The categorical classification of speed for this interval. Possible values: 'NORMAL' (Traffic is flowing smoothly, no slowdown), 'SLOW' (Slowdown detected, but no traffic jam), 'TRAFFIC_JAM' (Significant traffic delays detected).

The following is the schema for the routes_status RMI BigQuery table:

Name                      | Mode     | Type      | Description
------------------------- | -------- | --------- | -----------
selected_route_id         | NULLABLE | STRING    | The unique identifier for the SelectedRoute resource. Final component of the resource name: 'projects/{{project}}/selectedRoutes/{{selected_route_id}}'. Constraints: 4-63 characters, [a-zA-Z0-9-].
display_name              | NULLABLE | STRING    | User-provided descriptive name for the route. Used for human readability in reports.
status                    | NULLABLE | STRING    | The current operational state of the route. Possible values: 'STATUS_SCHEDULING' (Created, being scheduled), 'STATUS_RUNNING' (Active and collecting data), 'STATUS_DELETING' (Marked for deletion), 'STATUS_VALIDATING' (Undergoing validation checks), 'STATUS_INVALID' (Validation failed; see validation_error field).
validation_error          | NULLABLE | STRING    | Detailed reason why a route is in 'STATUS_INVALID'. Possible values: 'VALIDATION_ERROR_ROUTE_OUTSIDE_JURISDICTION' (The route path is outside the allowed project jurisdiction), 'VALIDATION_ERROR_LOW_ROAD_USAGE' (Insufficient road usage/traffic detected for reliable insights).
low_road_usage_start_time | NULLABLE | TIMESTAMP | The UTC timestamp when the route first encountered the 'VALIDATION_ERROR_LOW_ROAD_USAGE' error during re-validation.
route_attributes          | NULLABLE | STRING    | JSON-formatted string of custom key-value attributes (e.g., '{{"region": "north", "tier": "priority"}}'). Up to 10 pairs allowed. Both keys and values are limited to string types. Keys/values max 100 characters each. Keys cannot start with 'goog'. Used for filtering and grouping in downstream analysis.
