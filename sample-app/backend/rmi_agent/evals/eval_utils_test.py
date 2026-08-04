"""Unit tests for maps.api.snapping.roads.rmi_agent.evals.eval_utils."""

from __future__ import annotations

from unittest import mock

from absl.testing import absltest
from google.cloud.aiplatform.vertexai import evaluation
import pandas as pd

from google3.maps.api.snapping.roads.rmi_agent.evals import base_autorater
from google3.maps.api.snapping.roads.rmi_agent.evals import eval_utils


class EvalUtilsTest(absltest.TestCase):

  @mock.patch.object(evaluation, "EvalTask", autospec=True)
  def test_evaluate_autorater_subset_invokes_eval_task(
      self, mock_eval_task_cls: mock.Mock
  ) -> None:
    mock_eval_task = mock_eval_task_cls.return_value
    mock_results = mock.Mock(spec=evaluation.EvalResult)
    mock_results.summary_metrics = {}
    mock_results.metrics_table = None
    mock_eval_task.evaluate.return_value = mock_results

    df = pd.DataFrame({"prompt": ["test"]})
    mock_metrics = ["fake_metric"]

    result = eval_utils.evaluate_autorater_subset(
        rater_name="sql_data",
        rater_df=df,
        metrics=mock_metrics,
        experiment_name="exp_test",
        run_name="run_1",
    )

    self.assertEqual(result, mock_results)

    mock_eval_task_cls.assert_called_once_with(
        dataset=df,
        metrics=mock_metrics,
        experiment="exp_test",
        output_uri_prefix=None,
    )

    mock_eval_task.evaluate.assert_called_once_with(
        experiment_run_name="run_1",
        output_file_name="eval_results_sql_data.csv",
    )

  def test_get_rater_returns_registered_autoraters(self) -> None:
    golden_rater = eval_utils.get_rater("golden_match")
    self.assertIsInstance(golden_rater, base_autorater.BaseAutorater)

    sql_rater = eval_utils.get_rater("sql_data")
    self.assertIsInstance(sql_rater, base_autorater.BaseAutorater)

  def test_get_rater_returns_none_for_unknown(self) -> None:
    self.assertIsNone(eval_utils.get_rater("unknown_rater"))


if __name__ == "__main__":
  absltest.main()
