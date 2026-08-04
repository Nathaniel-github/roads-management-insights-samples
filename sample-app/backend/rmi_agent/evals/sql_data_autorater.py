"""Deterministic metrics for SQL data evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from google.cloud import bigquery
from google.cloud.aiplatform.vertexai import evaluation
import pandas as pd

from google3.maps.api.snapping.roads.rmi_agent.evals import base_autorater

_DATE_FORMAT = "ISO8601"


def _extract_candidate_table(
    instance: Mapping[str, Any],
) -> pd.DataFrame | None:
  """Extracts candidate data table from instance.

  Args:
    instance: The evaluation instance mapping containing agent response data.

  Returns:
    A pandas DataFrame of the candidate table, or None if not available.
  """
  data = instance.get("candidate_table")
  if data is None:
    return None
  return data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)


def _evaluate_table_equivalence(
    *,
    golden_df: pd.DataFrame | None,
    candidate_df: pd.DataFrame | None,
) -> tuple[float, str]:
  """Deterministically compares two DataFrames for tabular equivalence.

  Performs column alignment and deterministic row sorting, with relaxed type
  checking and conversion.

  Args:
    golden_df: The reference DataFrame produced by the Golden SQL.
    candidate_df: The candidate DataFrame produced by the agent.

  Returns:
    A tuple of (score, explanation) where score is 1.0 if the tables are
    equivalent (0.0 otherwise), and explanation is a string detailing the
    judgment.
  """
  if golden_df is None or candidate_df is None:
    return 0.0, "Missing Golden or Candidate table."

  golden_df = golden_df.copy()
  candidate_df = candidate_df.copy()

  golden_df.columns = [str(c).lower() for c in golden_df.columns]
  candidate_df.columns = [str(c).lower() for c in candidate_df.columns]

  if not set(golden_df.columns).issubset(candidate_df.columns):
    return 0.0, (
        "Candidate missing required columns. Expected "
        f"{list(golden_df.columns)}"
    )

  for col in golden_df.columns:
    is_golden_dt = pd.api.types.is_datetime64_any_dtype(golden_df[col])
    is_candidate_dt = pd.api.types.is_datetime64_any_dtype(candidate_df[col])
    if is_golden_dt or is_candidate_dt:
      golden_df[col] = pd.to_datetime(
          golden_df[col], utc=True, format=_DATE_FORMAT, errors="coerce"
      )
      candidate_df[col] = pd.to_datetime(
          candidate_df[col], utc=True, format=_DATE_FORMAT, errors="coerce"
      )
    elif pd.api.types.is_numeric_dtype(golden_df[col]):
      candidate_df[col] = pd.to_numeric(candidate_df[col], errors="coerce")
    elif pd.api.types.is_string_dtype(golden_df[col]):
      golden_df[col] = golden_df[col].astype(str).str.lower()
      candidate_df[col] = candidate_df[col].astype(str).str.lower()

  golden_cols = list(golden_df.columns)
  filtered_candidate_df = candidate_df[golden_cols]

  sorted_golden_df = golden_df.sort_values(by=golden_cols).reset_index(
      drop=True
  )
  sorted_candidate_df = filtered_candidate_df.sort_values(
      by=golden_cols
  ).reset_index(drop=True)

  try:
    pd.testing.assert_frame_equal(
        sorted_golden_df,
        sorted_candidate_df,
        check_like=True,
        check_dtype=False,
        check_names=False,
    )
    return 1.0, "Exact tabular match."
  except (AssertionError, ValueError, KeyError, TypeError) as e:
    return 0.0, f"Deterministic comparison failed: {e}"


class SqlDataAutorater(base_autorater.BaseAutorater):
  """Deterministic metrics for SQL data evaluation."""

  def __init__(self, client: bigquery.Client | None = None) -> None:
    """Initializes SqlDataAutorater with an optional BigQuery client.

    Args:
      client: Optional `bigquery.Client` for executing golden SQL queries.
    """
    self._client = client

  def extract_candidate_data(self, session: Any) -> dict[str, Any]:
    """Extracts candidate table and query data from the execution session.

    Args:
      session: The execution session object.

    Returns:
      A dictionary mapping 'candidate_table' and 'candidate_query' to values.
    """
    state = session.state if session else {}
    return {
        "candidate_table": state.get("candidate_table"),
        "candidate_query": state.get("candidate_query"),
    }

  def get_eval_metrics(self) -> list[evaluation.CustomMetric]:
    """Returns the configured custom metrics for Golden SQL data evaluation.

    Returns:
      A list containing the custom SQL data equivalence metric.
    """
    bq_client = self._client or bigquery.Client()

    def sql_data_match_fn(instance: Mapping[str, Any]) -> dict[str, Any]:
      """Evaluates SQL data match by comparing BigQuery golden query results.

      Args:
        instance: Evaluation instance mapping containing the 'sql' golden query
          and candidate table data.

      Returns:
        Dict containing 'sql_data_match' score, 'status', and 'explanation'.

      Raises:
        ValueError: If 'sql' field is missing or empty in instance.
      """
      sql_entries = instance.get("sql")
      if not sql_entries:
        raise ValueError(
            "Malformed dataset: 'sql' field is missing or empty for a SQL"
            " autorater case."
        )

      if isinstance(sql_entries, (list, tuple)):
        sql_query = "\n".join(str(e) for e in sql_entries)
      else:
        sql_query = str(sql_entries)

      try:
        golden_df = bq_client.query(sql_query).to_dataframe()
      except Exception as e:  # pylint: disable=broad-exception-caught
        return {
            "sql_data_match": 0.0,
            "status": "FAIL",
            "explanation": f"Failed to execute Golden SQL: {e}",
        }

      score, explanation = _evaluate_table_equivalence(
          golden_df=golden_df,
          candidate_df=_extract_candidate_table(instance),
      )
      return {
          "sql_data_match": score,
          "status": "PASS" if score == 1.0 else "FAIL",
          "explanation": explanation,
      }

    return [
        evaluation.CustomMetric(
            name="sql_data_match",
            metric_function=sql_data_match_fn,
        )
    ]
