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

The following is the schema for the disruptions_nested RMI BigQuery table:

| Name | Mode | Type | Description |
| --- | --- | --- | --- |
| disruption_id | NULLABLE | STRING | Unique identifier for the traffic disruption incident. |
| selected_route_id | NULLABLE | STRING | Unique identifier of the registered SelectedRoute resource associated with this disruption. |
| display_name | NULLABLE | STRING | Human-readable road name or corridor descriptor affected by the incident. |
| disruption_type | NULLABLE | STRING | Classification of the disruption (e.g. ACCIDENT, ROAD_CLOSURE, CONGESTION, HAZARD). |
| road_segment_ids | REPEATED | STRING | Array of Google Maps Place IDs corresponding to physical road segments affected by the incident. |
| start_time | NULLABLE | TIMESTAMP | The UTC timestamp when the disruption began or was scheduled to start. |
| centroid | NULLABLE | GEOGRAPHY | Spatial epicenter point of the disruption as a native BigQuery GEOGRAPHY Point (EPSG:4326). |
| geometry | NULLABLE | GEOGRAPHY | Native BigQuery GEOGRAPHY representing incident geometry (ST_Point if 1 position point, ST_LineString/ST_MultiLineString if >1). |
| total_observations | NULLABLE | INTEGER | Total raw observation snapshots recorded throughout the incident lifecycle. |
| first_seen_time | NULLABLE | TIMESTAMP | The earliest UTC retrieval timestamp when the incident was first detected by the monitoring system. |
| last_seen_time | NULLABLE | TIMESTAMP | The latest UTC retrieval timestamp when the incident was last reported active. |
| active_duration_minutes | NULLABLE | INTEGER | Total elapsed active lifecycle duration in minutes from first_seen_time to last_seen_time. |
| max_confirm_votes | NULLABLE | INTEGER | Peak cumulative user confirmation votes affirming the incident. |
| max_deny_votes | NULLABLE | INTEGER | Peak cumulative user denial votes indicating the incident has cleared. |
| total_state_changes | NULLABLE | INTEGER | Number of distinct state change intervals detected across the incident lifecycle. |
| events | REPEATED | RECORD | Run-length compressed chronological observation state intervals tracking vote changes over time. |
| events.first_retrieval_time | NULLABLE | TIMESTAMP | The UTC timestamp when this specific vote/state interval was first observed. |
| events.last_retrieval_time | NULLABLE | TIMESTAMP | The UTC timestamp when this specific vote/state interval was last observed before transitioning. |
| events.confirm_vote_count | NULLABLE | INTEGER | User confirmation vote count during this stable observation interval. |
| events.deny_vote_count | NULLABLE | INTEGER | User denial vote count during this stable observation interval. |
| events.provenances | REPEATED | STRING | Disruption telemetry provider sources active during this interval. |
| events.interval_observation_count | NULLABLE | INTEGER | Count of consecutive ~30s raw observation deliveries compressed into this stable state interval. |

The following is the schema for the disruptions_raw RMI BigQuery table:

| Name | Mode | Type | Description |
| --- | --- | --- | --- |
| disruption_id | NULLABLE | STRING | Unique identifier for the traffic disruption incident. |
| disruption_type | NULLABLE | STRING | Classification of the disruption (e.g. ACCIDENT, ROAD_CLOSURE, CONGESTION, HAZARD). |
| road_segment_ids | REPEATED | STRING | Array of Google Maps Place IDs corresponding to physical road segments affected by the disruption. |
| selected_route_id | NULLABLE | STRING | Unique identifier of the registered SelectedRoute resource associated with this disruption telemetry. |
| display_name | NULLABLE | STRING | Human-readable road name or corridor descriptor affected by the incident. |
| start_time | NULLABLE | RECORD | UTC timestamp struct indicating when the disruption began or was scheduled to start. |
| start_time.seconds | NULLABLE | INTEGER | Seconds of UTC time since Unix epoch (1970-01-01T00:00:00Z). |
| start_time.nanos | NULLABLE | INTEGER | Non-negative fractions of a second at nanosecond resolution. |
| provenances | REPEATED | STRING | Data provider and source authority classifications supplying the disruption telemetry. |
| centroid | NULLABLE | RECORD | Geographic center point coordinate struct of the overall disruption. |
| centroid.latitude | NULLABLE | NUMERIC | Latitude in decimal degrees (WGS84). |
| centroid.longitude | NULLABLE | NUMERIC | Longitude in decimal degrees (WGS84). |
| stretches | REPEATED | RECORD | Array of disruption stretch spatial segments, each containing coordinate waypoints and stretch centroid. |
| stretches.positions | REPEATED | RECORD | Ordered coordinate positions defining the stretch point or polyline corridor. |
| stretches.positions.latitude | NULLABLE | NUMERIC | Latitude in decimal degrees (WGS84). |
| stretches.positions.longitude | NULLABLE | NUMERIC | Longitude in decimal degrees (WGS84). |
| stretches.centroid | NULLABLE | RECORD | Center point coordinate of this individual disruption stretch. |
| stretches.centroid.latitude | NULLABLE | NUMERIC | Latitude in decimal degrees (WGS84). |
| stretches.centroid.longitude | NULLABLE | NUMERIC | Longitude in decimal degrees (WGS84). |
| confirm_vote_count | NULLABLE | INTEGER | Cumulative user confirmation vote count affirming the presence of the incident. |
| deny_vote_count | NULLABLE | INTEGER | Cumulative user denial vote count indicating the incident has cleared. |
| retrieval_time | NULLABLE | RECORD | UTC timestamp struct indicating when the observation snapshot was collected from RMI. |
| retrieval_time.seconds | NULLABLE | INTEGER | Seconds of UTC time since Unix epoch (1970-01-01T00:00:00Z). |
| retrieval_time.nanos | NULLABLE | INTEGER | Non-negative fractions of a second at nanosecond resolution. |
| subscription_name | NULLABLE | STRING | Cloud Pub/Sub subscription resource name delivering the telemetry stream. |
| message_id | NULLABLE | STRING | Unique Cloud Pub/Sub message identifier assigned by the messaging system. |
| publish_time | NULLABLE | TIMESTAMP | The UTC timestamp when the message was published to the Cloud Pub/Sub topic. |
| attributes | NULLABLE | STRING | JSON string of Cloud Pub/Sub message metadata attributes. |
