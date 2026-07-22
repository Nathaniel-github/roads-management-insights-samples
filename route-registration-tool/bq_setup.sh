#!/bin/bash
# bq_setup.sh
# Script to create the required BigQuery dataset and tables for the Roads API sync.

set -e

# --- Configuration Variables ---
echo "========================================="
echo "BigQuery Setup for Roads Sync Tool (Optimized)"
echo "========================================="
echo ""

read -p "Enter your Google Cloud Project ID: " PROJECT_ID
if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: Project ID cannot be empty."
    exit 1
fi

read -p "Enter the Dataset Name [default: historical_roads_data]: " DATASET_NAME
DATASET_NAME=${DATASET_NAME:-historical_roads_data}

read -p "Enter the BigQuery Location (e.g., US, EU) [default: US]: " LOCATION
LOCATION=${LOCATION:-US}

echo ""
echo "Creating dataset $DATASET_NAME in project $PROJECT_ID at location $LOCATION..."
echo ""

echo "[1/4] Checking authentication..."
# Ensure the user is authenticated with gcloud
if ! gcloud auth print-access-token &> /dev/null; then
    echo "ERROR: Not authenticated with gcloud. Please run 'gcloud auth login' first."
    exit 1
fi

echo "[2/4] Creating dataset: $DATASET_NAME (Location: $LOCATION)..."
if bq ls --project_id="$PROJECT_ID" | grep -q "$DATASET_NAME"; then
    echo "Dataset $DATASET_NAME already exists, skipping creation."
else
    bq mk --location="$LOCATION" -d "$PROJECT_ID:$DATASET_NAME"
    echo "Dataset created successfully."
fi

echo "[3/4] Creating table: routes_status..."
if bq ls --project_id="$PROJECT_ID" "$DATASET_NAME" | grep -q "routes_status"; then
    echo "Table routes_status already exists, skipping."
else
    bq mk -t "$PROJECT_ID:$DATASET_NAME.routes_status" selected_route_id:STRING,status:STRING
    echo "Table routes_status created successfully."
fi

echo "[4/4] Creating table: recent_roads_data with Partitioning & Clustering..."
if bq ls --project_id="$PROJECT_ID" "$DATASET_NAME" | grep -q "recent_roads_data"; then
    echo "Table recent_roads_data already exists, skipping."
else
    SCHEMA_JSON='[
      {"name": "selected_route_id", "type": "STRING", "mode": "NULLABLE", "description": "The unique identifier for the SelectedRoute resource."},
      {"name": "display_name", "type": "STRING", "mode": "NULLABLE", "description": "User-provided descriptive name for the route."},
      {"name": "record_time", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "UTC timestamp when the near real-time route data was computed."},
      {"name": "duration_in_seconds", "type": "FLOAT", "mode": "NULLABLE", "description": "Real-time traffic-aware duration in seconds."},
      {"name": "static_duration_in_seconds", "type": "FLOAT", "mode": "NULLABLE", "description": "Traffic-unaware (static) duration in seconds."},
      {"name": "route_geometry", "type": "GEOGRAPHY", "mode": "NULLABLE", "description": "Traffic-aware optimal path geometry."},
      {"name": "road_segment_ids", "type": "STRING", "mode": "REPEATED", "description": "Place IDs along the route in topological order."},
      {
        "name": "speed_reading_intervals",
        "type": "RECORD",
        "mode": "REPEATED",
        "description": "Intervals representing traffic density segments across the route.",
        "fields": [
          {"name": "interval_coordinates", "type": "GEOGRAPHY", "mode": "REPEATED", "description": "Coordinates representation for this speed interval."},
          {"name": "speed", "type": "STRING", "mode": "NULLABLE", "description": "The categorical speed classification: NORMAL, SLOW, or TRAFFIC_JAM."}
        ]
      }
    ]'

    # Write schema to temporary file
    TEMP_SCHEMA_FILE=$(mktemp)
    echo "$SCHEMA_JSON" > "$TEMP_SCHEMA_FILE"

    # Create table with:
    # 1. Day Partitioning on record_time
    # 2. 60-Day automatic partition expiration (sliding window retention)
    # 3. Clustering on selected_route_id and record_time
    bq mk \
      --table \
      --time_partitioning_field=record_time \
      --time_partitioning_type=DAY \
      --time_partitioning_expiration=5184000 \
      --clustering_fields=selected_route_id,record_time \
      "$PROJECT_ID:$DATASET_NAME.recent_roads_data" \
      "$TEMP_SCHEMA_FILE"
    
    rm "$TEMP_SCHEMA_FILE"
    echo "Table recent_roads_data created with optimization successfully."
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "Optimized tables and sliding-window partitions are ready."
echo "========================================="
