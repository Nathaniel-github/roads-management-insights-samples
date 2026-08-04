"""Unit tests for maps.api.snapping.roads.rmi_agent.evals.autoraters."""

from __future__ import annotations

import datetime
from typing import Any
from unittest import mock

from absl.testing import absltest
from absl.testing import parameterized
import db_dtypes
from google.cloud import bigquery
import pandas as pd

from google3.maps.api.snapping.roads.rmi_agent.evals import base_autorater
from google3.maps.api.snapping.roads.rmi_agent.evals import eval_utils
from google3.maps.api.snapping.roads.rmi_agent.evals import golden_match_autorater
from google3.maps.api.snapping.roads.rmi_agent.evals import sql_data_autorater
from google3.maps.api.snapping.roads.rmi_agent.evals import tool_trajectory_autorater


class AutoratersTest(parameterized.TestCase):
  """Unit tests for autorater classes and their evaluation metrics."""

  def test_autoraters_registry_keys(self) -> None:
    for key in ("golden_match", "sql_data", "tool_trajectory"):
      rater = eval_utils.get_rater(key)
      self.assertIsNotNone(rater)
      self.assertIsInstance(rater, base_autorater.BaseAutorater)

  def test_golden_match_autorater_metrics(self) -> None:
    metrics = golden_match_autorater.GoldenMatchAutorater().get_eval_metrics()
    self.assertEqual(
        metrics,
        [
            golden_match_autorater.GOLDEN_MATCH_BINARY_METRIC,
            golden_match_autorater.GOLDEN_MATCH_LIKERT_METRIC,
        ],
    )

  def test_sql_data_autorater_extract_candidate_data(self) -> None:
    rater = sql_data_autorater.SqlDataAutorater()

    mock_session = mock.Mock()
    mock_session.state = {
        "candidate_table": [{"col": 1}],
        "candidate_query": "SELECT 1;",
    }
    self.assertEqual(
        rater.extract_candidate_data(mock_session),
        {"candidate_table": [{"col": 1}], "candidate_query": "SELECT 1;"},
    )

    self.assertEqual(
        rater.extract_candidate_data(None),
        {"candidate_table": None, "candidate_query": None},
    )

  @parameterized.named_parameters(
      dict(
          testcase_name="exact_match",
          golden=pd.DataFrame({"id": [1, 2], "val": ["A", "B"]}),
          candidate=pd.DataFrame({"id": [1, 2], "val": ["A", "B"]}),
          expected_score=1.0,
      ),
      dict(
          testcase_name="out_of_order_rows",
          golden=pd.DataFrame({"id": [1, 2], "val": ["A", "B"]}),
          candidate=pd.DataFrame({"id": [2, 1], "val": ["B", "A"]}),
          expected_score=1.0,
      ),
      dict(
          testcase_name="extra_columns_ignored",
          golden=pd.DataFrame({"id": [1]}),
          candidate=pd.DataFrame({"id": [1], "extra": ["X"]}),
          expected_score=1.0,
      ),
      dict(
          testcase_name="missing_columns",
          golden=pd.DataFrame({"id": [1], "val": ["A"]}),
          candidate=pd.DataFrame({"id": [1]}),
          expected_score=0.0,
      ),
      dict(
          testcase_name="type_coercion",
          golden=pd.DataFrame({"val": [1.5]}),
          candidate=pd.DataFrame({"val": ["1.5"]}),
          expected_score=1.0,
      ),
      dict(
          testcase_name="different_column_names",
          golden=pd.DataFrame({"id": [1, 2], "val": ["A", "B"]}),
          candidate=pd.DataFrame({"x": [1, 2], "y": ["A", "B"]}),
          expected_score=0.0,
      ),
      dict(
          testcase_name="double_counting_prevented",
          golden=pd.DataFrame({"a": [1], "b": [1]}),
          candidate=pd.DataFrame({"x": [1], "y": [2]}),
          expected_score=0.0,
      ),
      dict(
          testcase_name="missing_table",
          golden=pd.DataFrame({"id": [1]}),
          candidate=None,
          expected_score=0.0,
      ),
  )
  def test_evaluate_table_equivalence_logic(
      self,
      golden: pd.DataFrame,
      candidate: pd.DataFrame | None,
      expected_score: float,
  ) -> None:
    score, _ = sql_data_autorater._evaluate_table_equivalence(
        golden_df=golden, candidate_df=candidate
    )
    self.assertEqual(score, expected_score)

  def test_sql_data_autorater_metric_handles_bq_error(self) -> None:
    mock_bq = mock.Mock(spec=bigquery.Client)
    mock_bq.query.side_effect = Exception("BQ Timeout")

    rater = sql_data_autorater.SqlDataAutorater(client=mock_bq)
    metric_fn = rater.get_eval_metrics()[0].metric_function

    result = metric_fn({"sql": "SELECT 1", "candidate_table": pd.DataFrame()})

    self.assertEqual(result["status"], "FAIL")
    self.assertEqual(result["sql_data_match"], 0.0)
    self.assertIn("BQ Timeout", result["explanation"])

  def test_sql_data_autorater_metric_missing_sql(self) -> None:
    rater = sql_data_autorater.SqlDataAutorater(client=mock.Mock())
    metric_fn = rater.get_eval_metrics()[0].metric_function

    with self.assertRaisesRegex(ValueError, "Malformed dataset"):
      metric_fn({"candidate_table": pd.DataFrame()})

  def test_sql_data_autorater_metric_sql_list_join(self) -> None:
    mock_bq = mock.Mock(spec=bigquery.Client)
    mock_bq.query.return_value.to_dataframe.return_value = pd.DataFrame(
        {"id": [1]}
    )

    rater = sql_data_autorater.SqlDataAutorater(client=mock_bq)
    metric_fn = rater.get_eval_metrics()[0].metric_function

    result = metric_fn({
        "sql": ["SELECT id", "FROM table"],
        "candidate_table": pd.DataFrame({"id": [1]}),
    })

    self.assertEqual(result["status"], "PASS")
    mock_bq.query.assert_called_once_with("SELECT id\nFROM table")

  def test_sql_data_autorater_positional_column_match(self) -> None:
    mock_bq = mock.Mock(spec=bigquery.Client)
    mock_bq.query.return_value.to_dataframe.return_value = pd.DataFrame(
        {"golden_a": [1, 2], "golden_b": ["x", "y"]}
    )

    rater = sql_data_autorater.SqlDataAutorater(client=mock_bq)
    metric_fn = rater.get_eval_metrics()[0].metric_function

    result = metric_fn({
        "sql": "SELECT 1",
        "candidate_table": pd.DataFrame(
            {"cand_x": [1, 2], "cand_y": ["x", "y"]}
        ),
    })

    self.assertEqual(result["status"], "FAIL")
    self.assertEqual(result["sql_data_match"], 0.0)
    self.assertIn("Candidate missing required columns", result["explanation"])

  def test_sql_data_autorater_db_dtypes_support(self) -> None:
    """Ensure db_dtypes is imported as it is required by SQL autorater."""

    golden = pd.DataFrame({
        "d": pd.Series(
            [datetime.date(2025, 10, 1)], dtype=db_dtypes.DateDtype()
        )
    })
    candidate = pd.DataFrame({
        "d": pd.Series(
            [datetime.date(2025, 10, 1)], dtype=db_dtypes.DateDtype()
        )
    })
    score, explanation = sql_data_autorater._evaluate_table_equivalence(
        golden_df=golden, candidate_df=candidate
    )
    self.assertEqual(score, 1.0)
    self.assertEqual(explanation, "Exact tabular match.")

  def test_tool_trajectory_autorater_extracts_calls(self) -> None:
    rater = tool_trajectory_autorater.ToolTrajectoryAutorater()

    mock_fc = mock.Mock()
    mock_fc.name = "search"
    mock_fc.args = {"q": "test"}

    mock_event = mock.Mock()
    mock_event.get_function_calls.return_value = [mock_fc]

    mock_session = mock.Mock(events=[mock_event])
    self.assertEqual(
        rater.extract_candidate_data(mock_session),
        {"candidate_tool_calls": [{"name": "search", "args": {"q": "test"}}]},
    )

    self.assertEqual(
        rater.extract_candidate_data(mock.Mock(events=[])),
        {"candidate_tool_calls": []},
    )

  @parameterized.named_parameters(
      dict(
          testcase_name="exact_match",
          candidate=[{"name": "search", "args": {"q": "test"}}],
          expected=[{"name": "search", "args": {"q": "test"}}],
          expected_status="PASS",
      ),
      dict(
          testcase_name="mismatch_args",
          candidate=[{"name": "search", "args": {"q": "wrong"}}],
          expected=[{"name": "search", "args": {"q": "test"}}],
          expected_status="FAIL",
      ),
      dict(
          testcase_name="mismatch_tool",
          candidate=[{"name": "other_tool", "args": {}}],
          expected=[{"name": "search", "args": {}}],
          expected_status="FAIL",
      ),
      dict(
          testcase_name="ignore_args_match",
          candidate=[{"name": "search", "args": {"q": "test"}}],
          expected=[{"name": "search"}],
          ignore_args=True,
          expected_status="PASS",
      ),
  )
  def test_tool_trajectory_autorater_evaluates_match(
      self,
      candidate: list[dict[str, Any]],
      expected: list[dict[str, Any]],
      expected_status: str,
      ignore_args: bool = False,
  ) -> None:
    rater = tool_trajectory_autorater.ToolTrajectoryAutorater()
    metric_fn = rater.get_eval_metrics()[0].metric_function

    result = metric_fn({
        "prompt": "test prompt",
        "candidate_tool_calls": candidate,
        "expected_tool_calls": expected,
        "ignore_args": ignore_args,
    })

    self.assertEqual(result["status"], expected_status)


if __name__ == "__main__":
  absltest.main()
