"""Location resolution tool for the RMI Agent.

Resolves natural-language location queries into BigQuery SQL filter
fragments (ST_INTERSECTS / ST_DWITHIN) that can be composed into WHERE
clauses against RMI tables.

Two modes:
  - place: Looks up an official polygon from BQ public boundary tables
    first, then falls back to Places API Text Search viewport.
  - radius: Geocodes a point via Places API Text Search and builds a
    ST_DWITHIN circle filter.
"""

from __future__ import annotations

from collections.abc import Callable
import threading
from typing import Any

from absl import logging
from google.api_core import exceptions as google_exceptions
import google.auth
from google.auth import exceptions as auth_exceptions
from google.auth.transport import requests as auth_requests
from google.cloud import bigquery
import requests

_GEOMETRY_COLUMN = "route_geometry"

_PLACES_API_SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform",
)

_PLACES_TIMEOUT_SECONDS = 30

_PLACES_SEARCH_URL = (
    "https://places.googleapis.com/v1/places:searchText"
)

_PLACES_FIELDS = (
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.viewport"
)

# Lazy singletons.
_bq_client: bigquery.Client | None = None
_bq_lock = threading.Lock()
_places_session: auth_requests.AuthorizedSession | None = None
_places_lock = threading.Lock()


def _get_bq_client() -> bigquery.Client:
  """Returns a lazily-initialised BQ client using ADC."""
  global _bq_client
  if _bq_client is None:
    with _bq_lock:
      if _bq_client is None:
        _bq_client = bigquery.Client()
  return _bq_client


def _get_places_session() -> auth_requests.AuthorizedSession:
  """Returns a lazily-initialised AuthorizedSession for Places API."""
  global _places_session
  if _places_session is None:
    with _places_lock:
      if _places_session is None:
        credentials, _ = google.auth.default(scopes=_PLACES_API_SCOPES)
        _places_session = auth_requests.AuthorizedSession(credentials)
  return _places_session


def _run_boundary_query(
    sql: str,
    params: list[bigquery.ScalarQueryParameter],
) -> list[bigquery.Row]:
  """Executes a parameterised BQ query and returns rows."""
  job_config = bigquery.QueryJobConfig(
      query_parameters=params,
  )
  try:
    # Converting RowIterator to list allows index-based row access.
    return list(
        _get_bq_client().query(sql, job_config=job_config).result()
    )
  except (google_exceptions.GoogleAPIError, auth_exceptions.GoogleAuthError):
    logging.exception("BigQuery boundary query failed; treating as no match.")
    return []


# ── BQ boundary lookup functions ────────────────────────────────


def _lookup_zip_code(location_name: str) -> str | None:
  """Matches a 5-digit zip code against geo_us_boundaries."""
  clean = location_name.strip()
  if not (clean.isdigit() and len(clean) == 5):
    return None
  sql = (
      "SELECT ST_ASTEXT(zip_code_geom) AS wkt "
      "FROM `bigquery-public-data.geo_us_boundaries.zip_codes` "
      "WHERE zip_code = @zip"
  )
  rows = _run_boundary_query(
      sql,
      [bigquery.ScalarQueryParameter("zip", "STRING", clean)],
  )
  if not rows:
    return None
  return rows[0]["wkt"]


def _lookup_county(location_name: str) -> str | None:
  """Fuzzy-matches a county name (strips ' county' suffix)."""
  name = location_name.strip().lower()
  if name.endswith(" county"):
    name = name.removesuffix(" county").strip()
  sql = (
      "SELECT ST_ASTEXT(county_geom) AS wkt "
      "FROM `bigquery-public-data.geo_us_boundaries.counties` "
      "WHERE LOWER(county_name) = @name "
      "ORDER BY state_name LIMIT 1"
  )
  rows = _run_boundary_query(
      sql,
      [bigquery.ScalarQueryParameter("name", "STRING", name)],
  )
  if not rows:
    return None
  return rows[0]["wkt"]


def _lookup_state(location_name: str) -> str | None:
  """Matches a US state by name."""
  name = location_name.strip().lower()
  sql = (
      "SELECT ST_ASTEXT(state_geom) AS wkt "
      "FROM `bigquery-public-data.geo_us_boundaries.states` "
      "WHERE LOWER(state_name) = @name"
  )
  rows = _run_boundary_query(
      sql,
      [bigquery.ScalarQueryParameter("name", "STRING", name)],
  )
  if not rows:
    return None
  return rows[0]["wkt"]


def _lookup_city_via_zip_union(
    location_name: str,
) -> str | None:
  """Approximates a city boundary via the union of its zip codes."""
  name = location_name.strip().lower()
  sql = (
      "SELECT ST_ASTEXT("
      "  ST_UNION_AGG(zip_code_geom)"
      ") AS wkt "
      "FROM `bigquery-public-data.geo_us_boundaries.zip_codes` "
      "WHERE LOWER(city) = @name OR LOWER(city) LIKE CONCAT(@name, ' %')"
  )
  rows = _run_boundary_query(
      sql,
      [bigquery.ScalarQueryParameter("name", "STRING", name)],
  )
  # BigQuery aggregate function ST_UNION_AGG always returns exactly 1 row.
  # If no rows match the WHERE clause, rows[0]["wkt"] is BigQuery NULL
  # (Python None).
  if not rows or rows[0]["wkt"] is None:
    return None
  return rows[0]["wkt"]


_BOUNDARY_CASCADE: list[
    tuple[str, Callable[[str], str | None], str]
] = [
    ("zip_code", _lookup_zip_code, "bq_zip_code"),
    ("county", _lookup_county, "bq_county"),
    ("state", _lookup_state, "bq_state"),
    ("city", _lookup_city_via_zip_union, "bq_city_zip_union"),
]


def _lookup_boundary(
    location_name: str,
    location_type: str | None = None,
) -> tuple[str | None, str]:
  """Cascades through BQ boundary tables.

  Args:
    location_name: Name of the location or zip code to look up.
    location_type: Optional hint from the agent.  If provided and
      valid, that table is tried first.  The full cascade always
      runs as a fallback regardless of hint correctness.

  Returns:
    (wkt_string_or_none, source_description).
  """
  # Try hinted type first (if provided and valid).
  if location_type:
    for key, fn, source in _BOUNDARY_CASCADE:
      if key == location_type:
        wkt = fn(location_name)
        if wkt:
          return wkt, source
        break

  # Full cascade fallback (skips already-tried hint).
  for key, fn, source in _BOUNDARY_CASCADE:
    if key == location_type:
      continue
    wkt = fn(location_name)
    if wkt:
      return wkt, source

  return None, ""


# ── Places API functions ─────────────────────────────────────────


def _places_text_search(
    query: str,
) -> dict[str, Any] | None:
  """Calls Places API v1 Text Search with ADC.

  Args:
    query: The text query to search for.

  Returns:
    The first place result dict, or None.
  """
  try:
    session = _get_places_session()
    response = session.post(
        _PLACES_SEARCH_URL,
        json={"textQuery": query},
        headers={
            "Content-Type": "application/json",
            "X-Goog-FieldMask": _PLACES_FIELDS,
        },
        timeout=_PLACES_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
      logging.warning(
          "Places API error %d: %s",
          response.status_code,
          response.text,
      )
      return None
    data = response.json()
  except (
      requests.exceptions.RequestException,
      ValueError,
      auth_exceptions.GoogleAuthError,
  ):
    logging.exception("Places API request failed for query %r.", query)
    return None

  places = data.get("places", [])
  if not places:
    return None
  return places[0]


def _viewport_to_sql(viewport: dict[str, Any]) -> str:
  """Converts a Places viewport to a ST_INTERSECTS envelope filter."""
  low = viewport["low"]
  high = viewport["high"]
  return (
      f"ST_INTERSECTS({_GEOMETRY_COLUMN}, "
      f"ST_MAKEENVELOPE("
      f"{low['longitude']}, {low['latitude']}, "
      f"{high['longitude']}, {high['latitude']}))"
  )


def _point_to_radius_sql(
    *,
    lat: float,
    lng: float,
    radius_meters: float,
) -> str:
  """Builds a ST_DWITHIN circle filter."""
  return (
      f"ST_DWITHIN({_GEOMETRY_COLUMN}, "
      f"ST_GEOGPOINT({lng}, {lat}), {radius_meters})"
  )


# ── Main tool function ───────────────────────────────────────────


def resolve_location(
    location_name: str,
    mode: str,
    radius_meters: float = 0.0,
    location_type: str | None = None,
    tool_context: Any = None,
) -> dict[str, Any]:
  """Resolves a location name into a BigQuery spatial SQL filter.

  Use this tool to convert a natural-language place name or address
  into a SQL fragment that filters RMI table rows by geography.

  Args:
    location_name: The place to resolve, e.g. "Downtown Sunnyvale",
      "02134", "Suffolk County", "Massachusetts".
    mode: Either "place" (polygon boundary lookup, for questions like
      "routes in Boston") or "radius" (circular buffer around a
      point, for questions like "routes within 5 km of Logan
      Airport").  The agent must pick the mode explicitly.
    radius_meters: Required when mode is "radius".  The search
      radius in meters around the resolved point.
    location_type: Optional hint for boundary resolution in "place"
      mode.  One of "zip_code", "county", "state", or "city".
      When provided, the hinted table is tried first, but the
      full cascade always runs as a fallback.  Safe to omit.
    tool_context: ADK tool context, auto-injected at runtime.
      Used to stash the full spatial filter in agent state.

  Returns:
    A dict with keys:
      status: "SUCCESS" or "NO_RESULT".
      sql_filter: "{{GEO_FILTER}}" placeholder (full filter is
        stashed in tool_context.state for later substitution).
      resolution_method: How the location was resolved.  One of
        "bq_boundary", "places_viewport", "places_radius".
      resolved_name: The display name or matched source.
  """
  if mode not in ("place", "radius"):
    return {
        "status": "ERROR",
        "message": (
            f"Invalid mode '{mode}'. Must be 'place' or 'radius'."
        ),
    }
  if mode == "radius" and radius_meters <= 0:
    return {
        "status": "ERROR",
        "message": (
            "radius_meters must be > 0 when mode is 'radius'."
        ),
    }

  # ── Mode: place ──────────────────────────────────────────────
  if mode == "place":
    wkt, _ = _lookup_boundary(location_name, location_type)
    if wkt:
      sql_filter = (
          f"ST_INTERSECTS({_GEOMETRY_COLUMN}, "
          f"ST_GEOGFROMTEXT('{wkt}'))"
      )
      return _maybe_stash(
          sql_filter=sql_filter,
          resolution_method="bq_boundary",
          resolved_name=location_name,
          tool_context=tool_context,
      )

    # Fallback: Places API viewport.
    place = _places_text_search(location_name)
    if place and "viewport" in place:
      sql_filter = _viewport_to_sql(place["viewport"])
      display = (
          place.get("displayName", {}).get("text", location_name)
      )
      return _maybe_stash(
          sql_filter=sql_filter,
          resolution_method="places_viewport",
          resolved_name=display,
          tool_context=tool_context,
      )

    return {
        "status": "NO_RESULT",
        "message": (
            f"Could not resolve '{location_name}' to a boundary."
        ),
    }

  # ── Mode: radius ─────────────────────────────────────────────
  place = _places_text_search(location_name)
  if place and "location" in place:
    loc = place["location"]
    sql_filter = _point_to_radius_sql(
        lat=loc["latitude"],
        lng=loc["longitude"],
        radius_meters=radius_meters,
    )
    display = (
        place.get("displayName", {}).get("text", location_name)
    )
    return _maybe_stash(
        sql_filter=sql_filter,
        resolution_method="places_radius",
        resolved_name=display,
        tool_context=tool_context,
    )

  return {
      "status": "NO_RESULT",
      "message": (
          f"Could not geocode '{location_name}' via Places API."
      ),
  }


_GEO_FILTER_PLACEHOLDER = "{{GEO_FILTER}}"
_GEO_STATE_KEY = "_geo_sql_filter"


def _maybe_stash(
    *,
    sql_filter: str,
    resolution_method: str,
    resolved_name: str,
    tool_context: Any,
) -> dict[str, Any]:
  """Builds the success response, stashing the filter when possible.

  When tool_context is available (ADK runtime), the full sql_filter is
  stored in agent state and replaced with a lightweight placeholder so
  the large WKT geometry never enters the LLM context window.

  Args:
    sql_filter: The full SQL spatial filter string.
    resolution_method: How the location was resolved.
    resolved_name: Human-readable resolved name.
    tool_context: ADK tool context or None.

  Returns:
    The tool response dict.
  """
  if tool_context is not None:
    tool_context.state[_GEO_STATE_KEY] = sql_filter
    sql_filter = _GEO_FILTER_PLACEHOLDER
  return {
      "status": "SUCCESS",
      "sql_filter": sql_filter,
      "resolution_method": resolution_method,
      "resolved_name": resolved_name,
  }

