"""CLI tool to fetch BigQuery schemas and generate rmi_schemas.md resources."""

from __future__ import annotations

from collections import abc
import pathlib

from absl import app
from absl import flags
from absl import logging
from google.api_core import exceptions as google_exceptions
from google.cloud import bigquery

from google3.maps.api.snapping.roads.rmi_agent import common_flags

_OUTPUT_PATH = flags.DEFINE_string(
    "output_file",
    None,
    "Path to write generated markdown schema file.",
    required=True,
)
_TABLES = flags.DEFINE_list(
    "tables",
    [
        "historical_travel_time",
        "recent_roads_data",
        "routes_status",
    ],
    "Comma-separated list of BigQuery table IDs to fetch.",
)
_SCHEMA_SANITY_MAP = str.maketrans({
    "|": "\\|",  # Escape markdown table delimiter.
    "\n": " ",  # Flatten in-cell newlines.
    "{": "{{",  # Escape for str.format().
    "}": "}}",  # Escape for str.format().
})


def _format_field(field: bigquery.SchemaField, prefix: str = "") -> list[str]:
  """Recursively formats a BigQuery schema field into markdown table rows.

  Args:
    field: The BigQuery schema field to format.
    prefix: Prefix string for nested field names.

  Returns:
    A list of formatted markdown table row strings.
  """
  rows = []
  field_name = f"{prefix}{field.name}"
  raw_desc = field.description or ""
  desc = raw_desc.translate(_SCHEMA_SANITY_MAP)
  rows.append(f"| {field_name} | {field.mode} | {field.field_type} | {desc} |")

  if field.field_type == "RECORD" and field.fields:
    for subfield in field.fields:
      rows.extend(_format_field(subfield, prefix=f"{field_name}."))
  return rows


def generate_schema_markdown(
    project_id: str,
    dataset_id: str,
    table_ids: abc.Sequence[str],
) -> str:
  """Fetches schemas for specified BigQuery tables and formats as markdown.

  Args:
    project_id: GCP project ID containing the dataset.
    dataset_id: BigQuery dataset ID containing the tables.
    table_ids: Sequence of BigQuery table names to fetch schemas for.

  Returns:
    A markdown string containing table schemas formatted as markdown tables.
  """
  client = bigquery.Client(project=project_id)
  blocks = []

  for table_id in table_ids:
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    logging.info("Fetching BigQuery schema for table: %s...", table_ref)
    try:
      table = client.get_table(table_ref)
      blocks.append(
          f"The following is the schema for the {table_id} RMI BigQuery"
          " table:\n"
      )
      blocks.append("| Name | Mode | Type | Description |")
      blocks.append("| --- | --- | --- | --- |")
      for field in table.schema:
        blocks.extend(_format_field(field))
      blocks.append("")
    except google_exceptions.GoogleAPICallError as e:
      logging.warning("Failed to fetch table %s: %s", table_ref, e)

  return "\n".join(blocks).strip() + "\n"


def main(argv: abc.Sequence[str]) -> None:
  """Main entrypoint to fetch BigQuery schemas and write rmi_schemas.md.

  Args:
    argv: Command line arguments.

  Raises:
    app.UsageError: If unexpected command-line arguments are passed.
  """
  if len(argv) > 1:
    raise app.UsageError("Too many command-line arguments.")

  project_id = common_flags.GCP_PROJECT.value
  dataset_id = common_flags.RMI_DATASET.value
  table_ids = _TABLES.value

  schema_md = generate_schema_markdown(project_id, dataset_id, table_ids)

  target_path = pathlib.Path(_OUTPUT_PATH.value)
  target_path.parent.mkdir(parents=True, exist_ok=True)
  target_path.write_text(schema_md, encoding="utf-8")

  logging.info("Successfully generated schema resource at %s!", target_path)


if __name__ == "__main__":
  app.run(main)
