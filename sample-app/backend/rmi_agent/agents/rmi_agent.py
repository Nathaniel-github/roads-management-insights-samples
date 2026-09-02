"""Upgraded RMI Agent."""

from __future__ import annotations

import datetime
import importlib.resources
import pathlib
from typing import Any

from absl import logging
from google.adk import skills
from google.adk.agents import llm_agent
from google.adk.integrations.bigquery import bigquery_credentials
from google.adk.integrations.bigquery import bigquery_toolset
from google.adk.integrations.bigquery import config as bq_config
from google.adk.planners import built_in_planner
from google.adk.tools import base_tool
from google.adk.tools import skill_toolset
import google.auth
from google.genai import types

from backend.rmi_agent import common_flags
from backend.rmi_agent.agents import prompts
from backend.rmi_agent.agents.tools import resolve_location

tool_config = bq_config.BigQueryToolConfig(
    write_mode=bq_config.WriteMode.BLOCKED, max_query_result_rows=1_000_000
)


try:
  application_default_credentials, project_id = google.auth.default()
  credentials_config = bigquery_credentials.BigQueryCredentialsConfig(
      credentials=application_default_credentials
  )
  logging.info(
      "Successfully loaded Google Cloud credentials for project: %s",
      project_id,
  )
except Exception:  # pylint: disable=broad-exception-caught
  logging.error(
      "Error loading Google Cloud credentials. Please make sure you have"
      " authenticated with 'gcloud auth application-default login'"
  )
  raise

bq_toolset = bigquery_toolset.BigQueryToolset(
    credentials_config=credentials_config, bigquery_tool_config=tool_config
)


def _inject_geo_filter(
    tool: base_tool.BaseTool,
    args: dict[str, Any],
    tool_context: Any,  # ToolContext
) -> dict[str, Any] | None:
  """Substitutes {{GEO_FILTER}} in execute_sql queries.

  When the agent writes SQL containing the {{GEO_FILTER}} placeholder,
  this callback replaces it with the full spatial filter stashed by
  resolve_location before BigQuery executes the query.

  Args:
    tool: The tool about to be executed.
    args: Mutable tool input arguments dictionary.
    tool_context: The ADK tool context for state access.

  Returns:
    None to proceed with (possibly modified) args.
  """
  if tool.name == "execute_sql" and isinstance(args, dict):
    query = args.get("query") or ""
    geo_filter = tool_context.state.get("_geo_sql_filter")
    if geo_filter and "{{GEO_FILTER}}" in query:
      args["query"] = query.replace("{{GEO_FILTER}}", geo_filter)
  return None


def _strip_sql_results(
    tool: base_tool.BaseTool,
    args: dict[str, Any],
    tool_context: Any,  # ToolContext
    tool_response: dict[str, Any],
) -> dict[str, Any] | None:
  """Intercepts execute_sql to stash full results and truncate LLM payload.

  Args:
    tool: The tool being executed.
    args: Tool input arguments dictionary.
    tool_context: The ADK tool context for state storage.
    tool_response: The raw response dictionary returned by the tool.

  Returns:
    The modified response dictionary containing truncated rows and status, or
    None if the tool was not execute_sql.
  """
  if tool.name == "execute_sql":
    query = args.get("query")
    tool_context.state["_last_sql_query"] = query

    if isinstance(tool_response, dict) and "rows" in tool_response:
      rows = tool_response["rows"]
      tool_context.state["_last_sql_result"] = rows

      limit = common_flags.SQL_TRUNCATION_LIMIT.value
      tool_response["total_rows_fetched"] = len(rows)
      # Keep geometry in the stashed rows (the UI needs it) but drop it from
      # the truncated preview so heavy GeoJSON never enters the LLM context.
      tool_response["rows"] = [
          {k: v for k, v in row.items() if k != "route_geometry"}
          if isinstance(row, dict)
          else row
          for row in rows[:limit]
      ]

      tool_response["message"] = (
          f"Showing {limit} of {len(rows)} rows. "
          "Full dataset stashed in background state."
      )
  return tool_response


def present_final_table(
    description: str,
    tool_context: Any,
) -> dict[str, Any]:
  """Presents the stashed data table from the last SQL query to the system.

  Use this tool to submit the stashed dataset (from your last successful query)
  as the final answer to the user's core request.

  Args:
    description: A brief explanation of what this data represents.
    tool_context: The ADK tool context (injected automatically).

  Returns:
    A dictionary indicating the status of the operation.
  """
  rows = tool_context.state.get("_last_sql_result")
  if rows is None:
    return {
        "status": "ERROR",
        "message": "No data stashed from a previous SQL query.",
    }

  tool_context.state["candidate_table"] = rows
  tool_context.state["candidate_query"] = tool_context.state.get(
      "_last_sql_query"
  )
  return {
      "status": "SUCCESS",
      "message": (
          f"Table '{description}' with {len(rows)} rows presented successfully."
      ),
  }


bq_tools = [bq_toolset, present_final_table]

# ── Skills ───────────────────────────────────────────────────────
_PACKAGE_FILES = importlib.resources.files(
    "backend.rmi_agent.agents"
)
_GEO_SKILL_DIR = pathlib.Path(
    str(_PACKAGE_FILES.joinpath("skills", "rmi-geospatial-resolver"))
)
_METRICS_SKILL_DIR = pathlib.Path(
    str(_PACKAGE_FILES.joinpath("skills", "rmi-traffic-metrics-grounding"))
)
_DISRUPTIONS_SKILL_DIR = pathlib.Path(
    str(_PACKAGE_FILES.joinpath("skills", "rmi-disruptions-grounding"))
)
_geo_skill = skills.load_skill_from_dir(_GEO_SKILL_DIR)
_metrics_skill = skills.load_skill_from_dir(_METRICS_SKILL_DIR)
_disruptions_skill = skills.load_skill_from_dir(_DISRUPTIONS_SKILL_DIR)
rmi_skill_toolset = skill_toolset.SkillToolset(
    skills=[_geo_skill, _metrics_skill, _disruptions_skill],
    additional_tools=[resolve_location.resolve_location],
)


SMOKETEST_INSTRUCTION = (
    "\nWhen asked what agent you are, respond exactly: 'I am the RMI Agent.'"
)


def get_rmi_agent_instruction(unused_ctx: object | None = None) -> str:
  """Returns the RMI Agent instruction hydrated with live flags and date.

  Args:
    unused_ctx: Unused context parameter required by the ADK callback interface.

  Returns:
    The instruction prompt string for the main RMI agent.
  """
  gcp_project = common_flags.GCP_PROJECT.value
  rmi_dataset = common_flags.RMI_DATASET.value
  disruptions_dataset = common_flags.RMI_DISRUPTIONS_DATASET.value

  today = datetime.date.today()
  day_of_week = today.strftime("%A")
  date_str = today.strftime("%Y-%m-%d")

  return (
      prompts.RMI_AGENT_PROMPT.format(
          PROJECT_ID=gcp_project,
          RMI_DATASET=rmi_dataset,
          DISRUPTIONS_DATASET=disruptions_dataset,
          DAY_OF_WEEK=day_of_week,
          DATE_STR=date_str,
      )
      + prompts.AGENT_IDENTITY
      + SMOKETEST_INSTRUCTION
  )


ROOT_AGENT = llm_agent.Agent(
    model="gemini-3.5-flash",
    name="RMI_agent",
    description=(
        "Agent to answer questions about RMI data residing in BigQuery."
    ),
    planner=built_in_planner.BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_level="medium",
        )
    ),
    instruction=get_rmi_agent_instruction,
    tools=bq_tools + [rmi_skill_toolset],
    before_tool_callback=_inject_geo_filter,
    after_tool_callback=_strip_sql_results,
)

__all__ = ["ROOT_AGENT"]
