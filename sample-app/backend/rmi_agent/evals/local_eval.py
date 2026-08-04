"""Local evaluation runner for RMI Agent using Vertex AI `EvalTask`."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from typing import Any

from absl import app
from absl import flags
from google.cloud.aiplatform import aiplatform
from google.cloud.aiplatform import vertexai
from google.genai import errors
from google.genai import types
import pandas as pd
import tenacity

from google3.learning.agents.orcas.framework.runners import secure_runner
from google3.maps.api.snapping.roads.rmi_agent import common_flags
from google3.maps.api.snapping.roads.rmi_agent.agents import rmi_agent
from google3.maps.api.snapping.roads.rmi_agent.evals import eval_utils
from google3.pyglib import resources

flags.adopt_module_key_flags(common_flags)

_EVAL_SET_PATH = flags.DEFINE_string(
    "eval_set_json_file_path",
    (
        "google3/maps/api/snapping/roads/rmi_agent/evals/evalsets/"
        "smoketest.evalset.json"
    ),
    "Path to the evalset JSON.",
)
_CONCURRENCY_LIMIT = flags.DEFINE_integer(
    "concurrency_limit",
    5,
    "Maximum number of concurrent agent execution tasks.",
)  # We set this to 5 because current quotas throw errors more often when we
# run at a higher concurrency.

_ENABLE_VERTEX_LOGGING = flags.DEFINE_bool(
    "enable_vertex_logging",
    True,
    "Whether to log metrics and parameters to Vertex AI Experiments.",
)

_OUTPUT_URI_PREFIX = flags.DEFINE_string(
    "output_uri_prefix",
    None,
    "GCS bucket prefix where evaluation datasets and results will be uploaded.",
)

_VERTEX_EXPERIMENT_NAME = "rmi-agent-evals"
_AGENT_MODULE = "google3.maps.api.snapping.roads.rmi_agent.agents.rmi_agent"


async def _generate_single_response(
    runner: secure_runner.InMemorySecureRunner,
    *,
    idx: str,
    prompt: str,
    autorater_name: str,
) -> dict[str, Any]:
  """Runs the agent for a single prompt in an isolated session.

  Each retry attempt uses a fresh session so evaluations stay independent.

  Args:
    runner: The `InMemorySecureRunner` instance executing the agent.
    idx: The unique index or identifier for the prompt session.
    prompt: The actual text prompt to send to the agent.
    autorater_name: The name of the autorater for this instance.

  Returns:
    A dictionary containing the response text and extracted candidate data.
  """
  new_message = types.Content(
      role="user", parts=[types.Part.from_text(text=prompt)]
  )

  result: dict[str, Any] = {}
  async for attempt in tenacity.AsyncRetrying(
      stop=tenacity.stop_after_attempt(15),
      wait=tenacity.wait_random_exponential(min=1, max=10),
      retry=tenacity.retry_if_exception_type(
          (errors.APIError, TimeoutError, ConnectionError, OSError)
      ),
      reraise=True,
  ):
    with attempt:
      attempt_num = attempt.retry_state.attempt_number
      print(
          f"[Agent Request {idx}] Starting execution (Attempt"
          f" {attempt_num})...",
          flush=True,
      )
      session_id = f"eval_session_{idx}_{attempt_num}"
      try:
        await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id="eval_user",
            session_id=session_id,
        )

        response_parts: list[str] = []
        async for event in runner.run_async(
            user_id="eval_user",
            session_id=session_id,
            new_message=new_message,
        ):
          content = event.content
          if event.is_final_response() and content and content.parts:
            response_parts.extend(
                part.text for part in content.parts if part.text
            )
        response_text = "".join(response_parts)

        print(
            f"\n[Agent Request {idx}] Prompt: {prompt}\n[Agent Request {idx}]"
            f" Response: {response_text}\n"
            + "-" * 40
        )

        session = await runner.session_service.get_session(
            app_name=runner.app_name,
            user_id="eval_user",
            session_id=session_id,
        )
        rater = eval_utils.get_rater(autorater_name)
        candidate_data = (
            rater.extract_candidate_data(session)
            if rater
            else {}
        )
        result = {**candidate_data, "response": response_text}
      finally:  # We remove the except block since tenacity will catch the
                # proper exceptions and retry the request.
        with contextlib.suppress(Exception):
          await runner.session_service.delete_session(
              app_name=runner.app_name,
              user_id="eval_user",
              session_id=session_id,
          )

  return result


async def generate_agent_responses(df: pd.DataFrame) -> pd.DataFrame:
  """Distributes batch payloads downstream without exceeding Vertex limits.

  Args:
    df: A pandas DataFrame containing at least a 'prompt' and 'autorater'
      column.

  Returns:
    A new pandas DataFrame with 'response' and candidate data appended.
  """
  runner = secure_runner.InMemorySecureRunner(agent=rmi_agent.ROOT_AGENT)
  semaphore = asyncio.Semaphore(_CONCURRENCY_LIMIT.value)

  if "autorater" not in df.columns or df["autorater"].isna().any():
    raise ValueError(
        "The 'autorater' column is missing or contains null values in the"
        " evalset. An autorater must be explicitly defined for every test case."
    )

  async def _sem_generate(
      *, idx: str, prompt: str, autorater: str
  ) -> dict[str, Any]:
    async with semaphore:
      return await _generate_single_response(
          runner, idx=idx, prompt=prompt, autorater_name=autorater
      )

  tasks = [
      _sem_generate(
          idx=str(row.Index),
          prompt=row.prompt,
          autorater=row.autorater,
      )
      for row in df.itertuples()
  ]
  results = await asyncio.gather(*tasks)

  results_df = pd.DataFrame(results, index=df.index)
  return pd.concat([df, results_df], axis=1)


async def run_eval(eval_set_path: str) -> None:
  """Executes evaluation against the specified dataset using `EvalTask`.

  Args:
    eval_set_path: The path to the evaluation dataset JSON file.

  Raises:
    app.UsageError: If Vertex logging is enabled without --output_uri_prefix.
    ValueError: If an unknown autorater is specified in the evalset.
  """
  os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

  project = common_flags.GCP_PROJECT.value or None
  location = common_flags.GCP_LOCATION.value or None
  vertexai.init(project=project, location=location)

  eval_set_name = os.path.splitext(os.path.basename(eval_set_path))[0]
  timestamp_str = time.strftime("%Y-%m-%d_%H-%M-%S", time.gmtime())
  run_name = f"{eval_set_name}-{timestamp_str}".translate(
      str.maketrans("._", "--")
  )
  logging_enabled = _ENABLE_VERTEX_LOGGING.value
  output_prefix = None

  if logging_enabled:
    if not _OUTPUT_URI_PREFIX.value:
      raise app.UsageError(
          "--output_uri_prefix must be specified when vertex logging is"
          " enabled."
      )
    base_prefix = _OUTPUT_URI_PREFIX.value.rstrip("/")
    output_prefix = f"{base_prefix}/{eval_set_name}/{timestamp_str}"
    aiplatform.init(
        project=project,
        location=location,
        experiment=_VERTEX_EXPERIMENT_NAME,
    )
    print(
        f"Configuring Vertex AI Experiment: {_VERTEX_EXPERIMENT_NAME}"
        f" (run: {run_name}, output_uri: {output_prefix})"
    )

  exp_name = _VERTEX_EXPERIMENT_NAME if logging_enabled else None
  exp_run_name = run_name if logging_enabled else None

  status = 0.0
  eval_set_df = None
  try:
    print(f"\n[1/3] Loading evaluation dataset from {eval_set_path}...")
    with resources.GetResourceAsFile(eval_set_path, "r") as f:
      eval_set_df = pd.read_json(f)

    if eval_set_df is None or eval_set_df.empty:
      raise ValueError(
          f"Evaluation dataset at '{eval_set_path}' is empty or invalid."
      )

    print("[2/3] Generating candidate responses from RMI Agent concurrently...")
    eval_response_df: pd.DataFrame = await generate_agent_responses(eval_set_df)

    print("[3/3] Running Vertex AI EvalTask in BYOR mode...")
    for rater_key, rater_df in eval_response_df.groupby("autorater"):
      rater_name = str(rater_key)
      rater = eval_utils.get_rater(rater_name)
      if rater is None:
        raise ValueError(
            f"Unknown autorater '{rater_name}' specified in the evalset."
        )
      print(
          f"\n--- Evaluating subset for rater: {rater_name} ({len(rater_df)}"
          " items) ---"
      )
      results = eval_utils.evaluate_autorater_subset(
          rater_name=rater_name,
          rater_df=rater_df,
          metrics=rater.get_eval_metrics(),
          experiment_name=exp_name,
          output_uri_prefix=output_prefix,
          run_name=exp_run_name,
      )

      print(f"\n--- Evaluation Summary Metrics ({rater_name}) ---")
      print(json.dumps(results.summary_metrics, indent=2))

      print(
          f"\n--- Detailed Granular Results & Explanations ({rater_name}) ---"
      )
      if results.metrics_table is not None:
        print(results.metrics_table.to_string(index=False))
      else:
        print(f"No detailed metrics table returned for {rater_name}.")

    print("\nEvaluation completed successfully!")
    status = 1.0
  finally:
    if logging_enabled:
      num_cases = len(eval_set_df) if eval_set_df is not None else 0
      with (
          contextlib.suppress(Exception),
          aiplatform.start_run(run_name, resume=True),
      ):
        aiplatform.log_params({
            "eval_set_path": eval_set_path,
            "eval_set_id": eval_set_name,
            "agent_module": _AGENT_MODULE,
            "num_eval_cases": num_cases,
        })
        aiplatform.log_metrics({"status": status})


def main(argv: list[str]) -> None:
  """Main entrypoint for running RMI Agent evaluation.

  Args:
    argv: Unused command line arguments.
  """
  del argv
  asyncio.run(run_eval(_EVAL_SET_PATH.value))


if __name__ == "__main__":
  app.run(main)
