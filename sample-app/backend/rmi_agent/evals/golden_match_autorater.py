"""Golden match autorater for RMI Agent Evaluation."""

from __future__ import annotations

import textwrap

from google.cloud.aiplatform.vertexai import evaluation

from google3.maps.api.snapping.roads.rmi_agent.evals import base_autorater

# 1. Binary Match Metric Template
_BINARY_MATCH_TEMPLATE = evaluation.PointwiseMetricPromptTemplate(
    criteria={"equivalence": textwrap.dedent("""\
            Your task is to determine whether the "candidate" answer is
            equivalent in content to the "reference" answer.""")},
    rating_rubric={
        "1": textwrap.dedent("""\
            Your judgement should be "true" if the candidate response contains
            all of the information that is in the reference response and no
            information which contradicts or is inconsistent with the reference
            response. The candidate response may contain extra information, as
            long as it is relevant to the prompt and does not contradict the
            reference response."""),
        "0": textwrap.dedent("""\
            Your judgement should be "false" if the candidate response is
            missing any of the information that is in the reference response, or
            if the candidate response contradicts or is inconsistent with the
            reference response."""),
    },
    input_variables=["prompt", "reference", "response"],
)

GOLDEN_MATCH_BINARY_METRIC = evaluation.PointwiseMetric(
    metric="golden_match_binary",
    metric_prompt_template=_BINARY_MATCH_TEMPLATE,
)

# 2. Likert 5-Point Scale Metric Template (Partial Credit & Formats)
_LIKERT_MATCH_TEMPLATE = evaluation.PointwiseMetricPromptTemplate(
    criteria={"equivalence": textwrap.dedent("""\
            Your task is to determine whether the "candidate" answer is
            equivalent in content to the "reference" answer. In all cases,
            extra information that does not contradict the reference answer is
            acceptable, as long as it is relevant to the prompt.

            The format of the answers should not be considered, only the
            content.

            Judging Equivalence:

            * For numeric answers, values within +/-10% of the reference
            answer are considered equivalent and should receive a rating of
            `completely`. An exact match is not required due to the confidence
            interval of the reference numbers.
            * This does not apply to numeric identifiers, which must match
              exactly.
            * For place names, variations in formatting (e.g., "Harris
              County" vs. "Harris, TX") are not important, as long as the
              candidate answer contains the same place as the reference
              answer consider them equivalent.""")},
    rating_rubric={
        "1": textwrap.dedent("""\
            The candidate answer is completely different from or
            contradicts the reference answer, is significantly focused on
            information that is not relevant to the prompt, or is empty."""),
        "2": textwrap.dedent("""\
            The candidate answer is missing significant information that is in
            the reference answer, such that the candidate answer is very
            incomplete, or contains enough irrelevant information that the
            answer appears misaligned with the prompt."""),
        "3": textwrap.dedent("""\
            The candidate answer contains a significant part of the
            information in the reference answer, such that it is somewhat
            helpful, but is missing significant information available in the
            reference answer."""),
        "4": textwrap.dedent("""\
            The candidate answer contains most of the information in the
            reference answer, such that the answer is mostly satisfactory, but
            it is missing nuances or details of the information that is in the
            reference answer."""),
        "5": textwrap.dedent("""\
            The candidate response contains all of the information that is
            in the reference response, and any extra information is relevant
            to the prompt. No numerical values differ by more than 10% of the
            reference values."""),
    },
    input_variables=["prompt", "reference", "response"],
)

GOLDEN_MATCH_LIKERT_METRIC = evaluation.PointwiseMetric(
    metric="golden_match_likert",
    metric_prompt_template=_LIKERT_MATCH_TEMPLATE,
)


class GoldenMatchAutorater(base_autorater.BaseAutorater):
  """Declarative Golden Match Pointwise Metrics for RMI Agent Evaluation."""

  def get_eval_metrics(self) -> list[evaluation.PointwiseMetric]:
    """Returns the pointwise evaluation metrics for golden match evaluation."""
    return [GOLDEN_MATCH_BINARY_METRIC, GOLDEN_MATCH_LIKERT_METRIC]
