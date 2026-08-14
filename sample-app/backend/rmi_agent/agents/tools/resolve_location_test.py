"""Unit tests for resolve_location tool."""

from __future__ import annotations

from unittest import mock

from absl.testing import absltest
from google.api_core import exceptions as google_exceptions
from google.auth import exceptions as auth_exceptions
from google.auth.transport import requests as auth_requests
from google.cloud import bigquery
import requests

from backend.rmi_agent.agents.tools import resolve_location as rl

_POLYGON_WKT = "POLYGON((0 0, 1 0, 1 1, 0 0))"


def _make_bq_client(
    *,
    rows: list[dict[str, str | None]] | None = None,
    error: bool = False,
) -> mock.MagicMock:
  """Builds a fake BigQuery client for _get_bq_client to return."""
  client = mock.create_autospec(bigquery.Client, spec_set=True, instance=True)
  query_job = client.query.return_value
  if error:
    query_job.result.side_effect = google_exceptions.GoogleAPIError("boom")
  else:
    query_job.result.return_value = rows or []
  return client


def _make_places_response(
    *,
    status_code: int = 200,
    payload: dict[str, object] | None = None,
    json_error: bool = False,
) -> mock.MagicMock:
  """Builds a fake requests.Response for the Places API."""
  response = mock.create_autospec(requests.Response, instance=True)
  response.status_code = status_code
  response.text = ""
  if json_error:
    response.json.side_effect = ValueError("Invalid JSON")
  else:
    response.json.return_value = payload or {}
  return response


def _make_places_session(
    *,
    response: mock.MagicMock | None = None,
    error: bool = False,
) -> mock.MagicMock:
  """Builds a fake AuthorizedSession for _get_places_session to return."""
  session = mock.create_autospec(
      auth_requests.AuthorizedSession, spec_set=True, instance=True
  )
  if error:
    session.post.side_effect = requests.exceptions.RequestException("network")
  else:
    session.post.return_value = response
  return session


class ResolveLocationPlaceModeTest(absltest.TestCase):

  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_bq_boundary_hit(self, mock_get_client):
    mock_get_client.return_value = _make_bq_client(
        rows=[{"wkt": _POLYGON_WKT}]
    )
    result = rl.resolve_location("Suffolk County", mode="place")
    self.assertEqual(result["status"], "SUCCESS")
    self.assertEqual(result["resolution_method"], "bq_boundary")
    self.assertIn("ST_INTERSECTS", result["sql_filter"])
    self.assertIn("ST_GEOGFROMTEXT", result["sql_filter"])
    self.assertIn("route_geometry", result["sql_filter"])

  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_bq_boundary_zip_code_hit(self, mock_get_client):
    mock_get_client.return_value = _make_bq_client(
        rows=[{"wkt": _POLYGON_WKT}]
    )
    result = rl.resolve_location("02134", mode="place")
    self.assertEqual(result["status"], "SUCCESS")
    self.assertEqual(result["resolution_method"], "bq_boundary")
    self.assertIn("ST_GEOGFROMTEXT", result["sql_filter"])

  @mock.patch.object(rl, "_get_places_session", autospec=True, spec_set=True)
  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_places_viewport_fallback(self, mock_get_client, mock_get_session):
    mock_get_client.return_value = _make_bq_client(rows=[])
    response = _make_places_response(
        payload={
            "places": [{
                "displayName": {"text": "Downtown Sunnyvale"},
                "viewport": {
                    "low": {"latitude": 37.36, "longitude": -122.05},
                    "high": {"latitude": 37.39, "longitude": -122.01},
                },
            }]
        }
    )
    mock_get_session.return_value = _make_places_session(response=response)
    result = rl.resolve_location("Downtown Sunnyvale", mode="place")
    self.assertEqual(result["status"], "SUCCESS")
    self.assertEqual(result["resolution_method"], "places_viewport")
    self.assertIn(
        "ST_MAKEENVELOPE(-122.05, 37.36, -122.01, 37.39)",
        result["sql_filter"],
    )
    self.assertEqual(result["resolved_name"], "Downtown Sunnyvale")

  @mock.patch.object(rl, "_get_places_session", autospec=True, spec_set=True)
  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_no_result(self, mock_get_client, mock_get_session):
    mock_get_client.return_value = _make_bq_client(rows=[])
    response = _make_places_response(payload={"places": []})
    mock_get_session.return_value = _make_places_session(response=response)
    result = rl.resolve_location("Nonexistent Place XYZ", mode="place")
    self.assertEqual(result["status"], "NO_RESULT")

  @mock.patch.object(rl, "_get_places_session", autospec=True, spec_set=True)
  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_bq_error_falls_back_gracefully(
      self, mock_get_client, mock_get_session
  ):
    mock_get_client.return_value = _make_bq_client(error=True)
    response = _make_places_response(payload={"places": []})
    mock_get_session.return_value = _make_places_session(response=response)
    result = rl.resolve_location("Boston", mode="place")
    self.assertEqual(result["status"], "NO_RESULT")

  @mock.patch.object(rl, "_get_places_session", autospec=True, spec_set=True)
  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_bq_auth_error_falls_back_gracefully(
      self, mock_get_client, mock_get_session
  ):
    mock_get_client.side_effect = auth_exceptions.GoogleAuthError("adc error")
    response = _make_places_response(payload={"places": []})
    mock_get_session.return_value = _make_places_session(response=response)
    result = rl.resolve_location("Boston", mode="place")
    self.assertEqual(result["status"], "NO_RESULT")


class ResolveLocationRadiusModeTest(absltest.TestCase):

  @mock.patch.object(rl, "_get_places_session", autospec=True, spec_set=True)
  def test_radius_success(self, mock_get_session):
    response = _make_places_response(
        payload={
            "places": [{
                "displayName": {"text": "Logan Airport"},
                "location": {"latitude": 42.3656, "longitude": -71.0096},
            }]
        }
    )
    session = _make_places_session(response=response)
    mock_get_session.return_value = session
    result = rl.resolve_location(
        "Logan Airport", mode="radius", radius_meters=5000.0
    )
    self.assertEqual(result["status"], "SUCCESS")
    self.assertEqual(result["resolution_method"], "places_radius")
    self.assertIn(
        "ST_DWITHIN(route_geometry, ST_GEOGPOINT(-71.0096, 42.3656), 5000.0)",
        result["sql_filter"],
    )
    _, kwargs = session.post.call_args
    self.assertEqual(kwargs["timeout"], rl._PLACES_TIMEOUT_SECONDS)

  @mock.patch.object(rl, "_get_places_session", autospec=True, spec_set=True)
  def test_radius_no_result(self, mock_get_session):
    response = _make_places_response(payload={"places": []})
    mock_get_session.return_value = _make_places_session(response=response)
    result = rl.resolve_location(
        "Nowhere XYZ", mode="radius", radius_meters=1000.0
    )
    self.assertEqual(result["status"], "NO_RESULT")

  def test_radius_missing_meters(self):
    result = rl.resolve_location(
        "Logan Airport", mode="radius", radius_meters=0.0
    )
    self.assertEqual(result["status"], "ERROR")

  @mock.patch.object(rl, "_get_places_session", autospec=True, spec_set=True)
  def test_places_http_error_returns_no_result(self, mock_get_session):
    response = _make_places_response(status_code=403)
    mock_get_session.return_value = _make_places_session(response=response)
    result = rl.resolve_location(
        "Logan Airport", mode="radius", radius_meters=5000.0
    )
    self.assertEqual(result["status"], "NO_RESULT")

  @mock.patch.object(rl, "_get_places_session", autospec=True, spec_set=True)
  def test_places_network_error_returns_no_result(self, mock_get_session):
    mock_get_session.return_value = _make_places_session(error=True)
    result = rl.resolve_location(
        "Logan Airport", mode="radius", radius_meters=5000.0
    )
    self.assertEqual(result["status"], "NO_RESULT")

  @mock.patch.object(rl, "_get_places_session", autospec=True, spec_set=True)
  def test_places_invalid_json_returns_no_result(self, mock_get_session):
    response = _make_places_response(json_error=True)
    mock_get_session.return_value = _make_places_session(response=response)
    result = rl.resolve_location(
        "Logan Airport", mode="radius", radius_meters=5000.0
    )
    self.assertEqual(result["status"], "NO_RESULT")

  @mock.patch.object(rl, "_get_places_session", autospec=True, spec_set=True)
  def test_places_auth_error_returns_no_result(self, mock_get_session):
    mock_get_session.side_effect = auth_exceptions.GoogleAuthError("adc boom")
    result = rl.resolve_location(
        "Logan Airport", mode="radius", radius_meters=5000.0
    )
    self.assertEqual(result["status"], "NO_RESULT")


class ResolveLocationStashingTest(absltest.TestCase):

  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_stashes_filter_in_context_state(self, mock_get_client):
    mock_get_client.return_value = _make_bq_client(
        rows=[{"wkt": _POLYGON_WKT}]
    )
    mock_context = mock.Mock(spec_set=["state"])
    mock_context.state = {}
    result = rl.resolve_location(
        "Boston", mode="place", tool_context=mock_context
    )
    self.assertEqual(result["status"], "SUCCESS")
    self.assertEqual(result["sql_filter"], "{{GEO_FILTER}}")
    self.assertIn("ST_INTERSECTS", mock_context.state["_geo_sql_filter"])


class ResolveLocationInputValidationTest(absltest.TestCase):

  def test_invalid_mode(self):
    result = rl.resolve_location("Boston", mode="auto")
    self.assertEqual(result["status"], "ERROR")
    self.assertIn("Invalid mode", result["message"])


class ResolveLocationTypeHintTest(absltest.TestCase):
  """Tests for the optional location_type hint parameter."""

  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_correct_hint_skips_cascade(self, mock_get_client):
    """A correct hint resolves on the first try."""
    client = _make_bq_client(rows=[{"wkt": _POLYGON_WKT}])
    mock_get_client.return_value = client
    result = rl.resolve_location(
        "Massachusetts", mode="place", location_type="state"
    )
    self.assertEqual(result["status"], "SUCCESS")
    self.assertEqual(result["resolution_method"], "bq_boundary")
    # State lookup is a single BQ query; zip/county/city skipped.
    self.assertEqual(client.query.call_count, 1)

  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_wrong_hint_falls_back_to_cascade(self, mock_get_client):
    """A wrong hint still resolves via the fallback cascade."""
    client = mock.create_autospec(
        bigquery.Client, spec_set=True, instance=True
    )
    # First call (hinted "state") returns empty, subsequent calls
    # return a match (county cascade hit).
    job_miss = mock.Mock()
    job_miss.result.return_value = []
    job_hit = mock.Mock()
    job_hit.result.return_value = [{"wkt": _POLYGON_WKT}]
    client.query.side_effect = [job_miss, job_miss, job_hit]
    mock_get_client.return_value = client
    result = rl.resolve_location(
        "Suffolk County", mode="place", location_type="state"
    )
    self.assertEqual(result["status"], "SUCCESS")
    self.assertEqual(result["resolution_method"], "bq_boundary")

  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_invalid_hint_ignored(self, mock_get_client):
    """An unrecognised hint runs the normal cascade."""
    mock_get_client.return_value = _make_bq_client(
        rows=[{"wkt": _POLYGON_WKT}]
    )
    result = rl.resolve_location(
        "02134", mode="place", location_type="province"
    )
    self.assertEqual(result["status"], "SUCCESS")
    self.assertEqual(result["resolution_method"], "bq_boundary")

  @mock.patch.object(
      rl, "_get_places_session", autospec=True, spec_set=True
  )
  @mock.patch.object(rl, "_get_bq_client", autospec=True, spec_set=True)
  def test_hint_miss_all_cascade_miss_falls_to_places(
      self, mock_get_client, mock_get_session
  ):
    """Hint + full cascade miss → Places viewport fallback."""
    mock_get_client.return_value = _make_bq_client(rows=[])
    response = _make_places_response(
        payload={
            "places": [{
                "displayName": {"text": "Springfield"},
                "viewport": {
                    "low": {"latitude": 37.0, "longitude": -122.0},
                    "high": {"latitude": 38.0, "longitude": -121.0},
                },
            }]
        }
    )
    mock_get_session.return_value = _make_places_session(
        response=response
    )
    result = rl.resolve_location(
        "Springfield", mode="place", location_type="city"
    )
    self.assertEqual(result["status"], "SUCCESS")
    self.assertEqual(result["resolution_method"], "places_viewport")


if __name__ == "__main__":
  absltest.main()
