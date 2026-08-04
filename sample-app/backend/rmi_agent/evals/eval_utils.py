"""Evaluation utilities and autorater metrics dispatcher for RMI Agent evals."""

from __future__ import annotations

from typing import Any

from google.cloud.aiplatform.vertexai import evaluation
import pandas as pd

from google3.maps.api.snapping.roads.rmi_agent.evals import base_autorater
from google3.maps.api.snapping.roads.rmi_agent.evals import golden_match_autorater
from google3.maps.api.snapping.roads.rmi_agent.evals import sql_data_autorater
from google3.maps.api.snapping.roads.rmi_agent.evals import tool_trajectory_autorater

_AUTORATERS: dict[str, base_autorater.BaseAutorater] = {
    "golden_match": golden_match_autorater.GoldenMatchAutorater(),
    "sql_data": sql_data_autorater.SqlDataAutorater(),
    "tool_trajectory": tool_trajectory_autorater.ToolTrajectoryAutorater(),
}


def get_rater(name: str) -> base_autorater.BaseAutorater | None:
  """Returns the autorater instance for the given rater name."""
  return _AUTORATERS.get(name)


def evaluate_autorater_subset(
    rater_name: str,
    rater_df: pd.DataFrame,
    metrics: list[Any],
    *,
    experiment_name: str | None = None,
    output_uri_prefix: str | None = None,
    run_name: str | None = None,
) -> evaluation.EvalResult:
  """Runs Vertex AI `EvalTask` for a single autorater dataset subset.

  Args:
    rater_name: The identifier of the autorater (e.g., 'golden_match',
      'sql_data').
    rater_df: DataFrame containing the slice of instances for this autorater.
    metrics: List of metric definitions compatible with Vertex AI `EvalTask`.
    experiment_name: Optional Vertex AI experiment name for tracking.
    output_uri_prefix: Optional GCS prefix for output artifacts.
    run_name: Optional timestamped experiment run name.

  Returns:
    The resulting `evaluation.EvalResult` from Vertex AI `EvalTask`.
  """
  eval_task = evaluation.EvalTask(
      dataset=rater_df,
      metrics=metrics,
      experiment=experiment_name,
      output_uri_prefix=output_uri_prefix,
  )

  output_filename = f"eval_results_{rater_name}.csv"
  return eval_task.evaluate(
      experiment_run_name=run_name,
      output_file_name=output_filename,
  )
