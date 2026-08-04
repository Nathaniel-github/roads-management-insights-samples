"""Tool trajectory autorater for RMI Agent Evaluation."""

from __future__ import annotations

from collections.abc import Mapping
import functools
from typing import Any

from google.adk.evaluation import eval_case
from google.adk.evaluation import eval_metrics
from google.adk.evaluation import trajectory_evaluator
from google.adk.sessions import session as adk_session
from google.cloud.aiplatform.vertexai import evaluation
from google.genai import types as genai_types

from google3.maps.api.snapping.roads.rmi_agent.evals import base_autorater

_CANDIDATE_TOOL_CALLS_KEY = "candidate_tool_calls"
_EXPECTED_TOOL_CALLS_KEY = "expected_tool_calls"
_DEFAULT_THRESHOLD = 1.0


@functools.lru_cache(maxsize=4)
def _get_evaluator(
    match_type_str: str,
    threshold: float = _DEFAULT_THRESHOLD,
) -> trajectory_evaluator.TrajectoryEvaluator:
  """Caches evaluators to avoid heavy instantiation per row."""
  match_type = eval_metrics.ToolTrajectoryCriterion.MatchType[
      match_type_str.upper()
  ]
  criterion = eval_metrics.ToolTrajectoryCriterion(
      threshold=threshold, match_type=match_type
  )
  return trajectory_evaluator.TrajectoryEvaluator(
      eval_metric=eval_metrics.EvalMetric(
          metric_name="tool_trajectory", criterion=criterion
      )
  )


def _to_function_calls(
    raw_calls: list[dict[str, Any]], strip_args: bool
) -> list[genai_types.FunctionCall]:
  """Converts raw dicts to FunctionCalls.

  Args:
    raw_calls: The list of raw function call dictionaries.
    strip_args: Whether to strip arguments by forcing them to an empty dict.

  Returns:
    A list of parsed FunctionCall objects.
  """
  calls = []
  for c in raw_calls:
    if not isinstance(c, dict) or "name" not in c:
      continue
    # If strip_args is True, force args to empty so ADK only
    # compares the name
    args = {} if strip_args else c.get("args", {})
    calls.append(genai_types.FunctionCall(name=c["name"], args=args))
  return calls


class ToolTrajectoryAutorater(base_autorater.BaseAutorater):
  """ADK Tool Trajectory Metric for RMI Agent Evaluation."""

  def extract_candidate_data(
      self, session: adk_session.Session
  ) -> dict[str, Any]:
    """Extracts candidate tool calls from the session events.

    Args:
      session: The ADK Session object containing execution events.

    Returns:
      A dictionary mapping the candidate tool calls key to a list
      of function calls.
    """
    calls = []
    for event in getattr(session, "events", []):
      if hasattr(event, "get_function_calls"):
        for fc in event.get_function_calls() or []:
          calls.append(
              {"name": fc.name, "args": dict(fc.args or {})}
          )
    return {_CANDIDATE_TOOL_CALLS_KEY: calls}

  def _tool_trajectory_match(
      self, instance: Mapping[str, Any]
  ) -> dict[str, Any]:
    """Evaluates tool trajectory equivalence.

    Uses ADK TrajectoryEvaluator to compare actual vs expected
    tool call sequences.

    Args:
      instance: A mapping containing 'prompt',
        'candidate_tool_calls', and 'expected_tool_calls'.

    Returns:
      A dictionary with 'tool_trajectory_match' score, 'status',
      and an 'explanation'.

    Raises:
      ValueError: If 'match_type' is invalid, or if 'prompt' is
        missing or empty.
    """
    match_type_str = instance.get("match_type", "IN_ORDER")
    ignore_args = instance.get("ignore_args", False)
    threshold = instance.get("threshold", _DEFAULT_THRESHOLD)

    try:
      evaluator = _get_evaluator(match_type_str, threshold)
    except KeyError as err:
      valid = [
          e.name
          for e in eval_metrics.ToolTrajectoryCriterion.MatchType
      ]
      raise ValueError(
          f"Invalid match_type '{match_type_str}'."
          f" Valid: {valid}"
      ) from err

    prompt = instance.get("prompt")
    if not prompt:
      raise ValueError(
          "Malformed dataset: 'prompt' field is missing or"
          " empty for a tool trajectory autorater case."
      )

    user_content = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text=str(prompt))],
    )

    actual_invocation = eval_case.Invocation(
        user_content=user_content,
        intermediate_data={
            "tool_uses": _to_function_calls(
                instance.get(_CANDIDATE_TOOL_CALLS_KEY, []),
                strip_args=ignore_args,
            )
        },
    )

    expected_invocation = eval_case.Invocation(
        user_content=user_content,
        intermediate_data={
            "tool_uses": _to_function_calls(
                instance.get(_EXPECTED_TOOL_CALLS_KEY, []),
                strip_args=ignore_args,
            )
        },
    )

    result = evaluator.evaluate_invocations(
        [actual_invocation], [expected_invocation]
    )
    score = (
        result.overall_score
        if result.overall_score is not None
        else 0.0
    )

    args_msg = " (Args Ignored)" if ignore_args else ""

    return {
        "tool_trajectory_match": score,
        "status": "PASS" if score >= threshold else "FAIL",
        "explanation": (
            "ADK TrajectoryEvaluator"
            f" ({match_type_str.upper()}){args_msg}"
            f" match score: {score:.2f}"
        ),
    }

  def get_eval_metrics(self) -> list[evaluation.CustomMetric]:
    """Returns the custom ADK tool trajectory evaluation metrics.

    Returns:
      A list containing the tool trajectory custom metric.
    """
    return [
        evaluation.CustomMetric(
            name="tool_trajectory_match",
            metric_function=self._tool_trajectory_match,
        )
    ]
