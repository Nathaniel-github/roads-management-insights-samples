The following is the schema for the historical_travel_time RMI BigQuery table:

| Name | Mode | Type | Description |
| --- | --- | --- | --- |
| selected_route_id | NULLABLE | STRING | The unique identifier for the SelectedRoute resource (4-63 chars, alphanumeric and hyphens). Acts as the primary correlation key across RMI telemetry datasets. |
| display_name | NULLABLE | STRING | User-provided descriptive name for the route for human readability in reports and UIs. |
| record_time | NULLABLE | TIMESTAMP | The UTC timestamp representing when the route travel time was computed (hourly-truncated in historical table, daily-partitioned). |
| duration_in_seconds | NULLABLE | FLOAT | The traffic-aware travel duration in seconds considering real-time traffic conditions at record_time. |
| static_duration_in_seconds | NULLABLE | FLOAT | The traffic-unaware (static) travel duration in seconds under ideal free-flow baseline conditions. |
| route_geometry | NULLABLE | GEOGRAPHY | The optimal polyline geometry of the route as a native BigQuery GEOGRAPHY LineString (EPSG:4326). |
| road_segment_ids | REPEATED | STRING | Array of Google Maps Place IDs along the route in topological sequence. |

The following is the schema for the recent_roads_data RMI BigQuery table:

| Name | Mode | Type | Description |
| --- | --- | --- | --- |
| selected_route_id | NULLABLE | STRING | The unique identifier for the SelectedRoute resource (4-63 chars, alphanumeric and hyphens). Acts as the primary correlation key across RMI telemetry datasets. |
| display_name | NULLABLE | STRING | User-provided descriptive name for the route for human readability in reports and UIs. |
| record_time | NULLABLE | TIMESTAMP | The UTC timestamp representing when the near real-time route data was computed (high-frequency updates, daily-partitioned, 60-day retention). |
| duration_in_seconds | NULLABLE | FLOAT | The near real-time traffic-aware duration in seconds considering live traffic conditions at record_time. |
| static_duration_in_seconds | NULLABLE | FLOAT | The traffic-unaware (static) duration in seconds under ideal free-flow baseline conditions. |
| route_geometry | NULLABLE | GEOGRAPHY | The traffic-aware polyline geometry of the route as a native BigQuery GEOGRAPHY LineString (EPSG:4326). |
| speed_reading_intervals | REPEATED | RECORD | Speed Reading Intervals (SRI) breaking down the route into sub-segments based on traffic density speed classifications. |
| speed_reading_intervals.interval_coordinates | REPEATED | GEOGRAPHY | The GEOGRAPHY representation of the specific road segment for this speed interval (EPSG:4326). |
| speed_reading_intervals.speed | NULLABLE | STRING | Categorical classification of traffic speed ('NORMAL' >85% free-flow, 'SLOW' 50-85% free-flow, 'TRAFFIC_JAM' <50% free-flow). |
| road_segment_ids | REPEATED | STRING | Array of Google Maps Place IDs along the route in topological sequence. |

The following is the schema for the routes_status RMI BigQuery table:

| Name | Mode | Type | Description |
| --- | --- | --- | --- |
| selected_route_id | NULLABLE | STRING | The unique identifier for the SelectedRoute resource (4-63 chars, alphanumeric and hyphens). Logical primary key. |
| display_name | NULLABLE | STRING | User-provided descriptive name for the route for human readability in reports and UIs. |
| status | NULLABLE | STRING | Operational lifecycle state ('STATUS_RUNNING', 'STATUS_SCHEDULING', 'STATUS_VALIDATING', 'STATUS_INVALID', 'STATUS_DELETING'). |
| validation_error | NULLABLE | STRING | Error code if status is STATUS_INVALID ('VALIDATION_ERROR_ROUTE_OUTSIDE_JURISDICTION', 'VALIDATION_ERROR_LOW_ROAD_USAGE'). |
| low_road_usage_start_time | NULLABLE | TIMESTAMP | The UTC timestamp when the route transitioned to STATUS_INVALID due to low road usage. |
| route_attributes | NULLABLE | STRING | JSON-formatted string of flat key-value metadata attributes (max 10 pairs, string values). |
