"""Common flags for the RMI Agent."""

from __future__ import annotations

import os
from absl import flags

GCP_PROJECT = flags.DEFINE_string(
    "gcp_project",
    os.environ.get("GOOGLE_CLOUD_PROJECT", "nsthomas-intern-2026"),
    "GCP project for deployment and evaluation.",
)

RMI_DATASET = flags.DEFINE_string(
    "rmi_dataset",
    os.environ.get("RMI_DATASET", "boston_oct_2025_sample_data"),
    "GCP dataset containing RMI tables.",
)

SERVICE_ACCOUNT = flags.DEFINE_string(
    "service_account",
    os.environ.get("GOOGLE_SERVICE_ACCOUNT", ""),
    "Service account used by the agent.",
)

GCP_LOCATION = flags.DEFINE_string(
    "gcp_location",
    os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    "GCP region/location.",
)

DATA_LOCATION = flags.DEFINE_string(
    "data_location",
    os.environ.get("DATA_LOCATION", "US"),
    "Data location.",
)

DATA_STORE_ID = flags.DEFINE_string(
    "data_store_id",
    os.environ.get("DATA_STORE_ID", "insights-search-ds"),
    "Data store ID.",
)

SEARCH_LOCATION = flags.DEFINE_string(
    "search_location",
    os.environ.get("SEARCH_LOCATION", "us"),
    "Search location.",
)

GOOGLE_MAPS_API_KEY = flags.DEFINE_string(
    "google_maps_api_key",
    os.environ.get("GOOGLE_MAPS_API_KEY"),
    "Google Maps API key.",
)

SQL_TRUNCATION_LIMIT = flags.DEFINE_integer(
    "sql_truncation_limit",
    int(os.environ.get("SQL_TRUNCATION_LIMIT", 20)),
    "Number of rows to limit/truncate in SQL query results returned to the"
    " agent.",
)
