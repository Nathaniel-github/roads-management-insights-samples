from __future__ import annotations

import pathlib
from unittest import mock

from absl import app
from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver
from google.api_core import exceptions as google_exceptions
from google.cloud import bigquery

from google3.maps.api.snapping.roads.rmi_agent.tools import fetch_bq_schema

# Set a default value for required flag so absltest.main() flag parsing passes.
flags.FLAGS.set_default("output_file", "/dummy/path.md")


class FetchBqSchemaTest(absltest.TestCase):
  """Unit tests for fetch_bq_schema."""

  def test_format_field_primitive(self) -> None:
    """Verifies single primitive fields format into markdown table rows."""
    field = bigquery.SchemaField(
        "segment_id", "STRING", mode="REQUIRED", description="Unique ID"
    )

    rows = fetch_bq_schema._format_field(field)

    self.assertEqual(rows, ["| segment_id | REQUIRED | STRING | Unique ID |"])

  def test_format_field_escapes_special_characters(self) -> None:
    """Verifies special characters are escaped for markdown."""
    field = bigquery.SchemaField(
        "col",
        "STRING",
        mode="NULLABLE",
        description="Line 1\nLine 2 with | pipe and {brace}",
    )

    rows = fetch_bq_schema._format_field(field)

    expected = [
        r"| col | NULLABLE | STRING | Line 1 Line 2 with \| pipe and"
        r" {{brace}} |"
    ]
    self.assertEqual(rows, expected)

  def test_format_field_nested_record(self) -> None:
    """Verifies nested RECORD fields recursively format child fields."""
    subfield = bigquery.SchemaField(
        "lat", "FLOAT", mode="NULLABLE", description="Latitude"
    )
    record_field = bigquery.SchemaField(
        "location",
        "RECORD",
        mode="NULLABLE",
        fields=[subfield],
        description="Geo location",
    )

    rows = fetch_bq_schema._format_field(record_field)

    expected = [
        "| location | NULLABLE | RECORD | Geo location |",
        "| location.lat | NULLABLE | FLOAT | Latitude |",
    ]
    self.assertEqual(rows, expected)

  @mock.patch.object(bigquery, "Client", autospec=True)
  def test_generate_schema_markdown_returns_formatted_tables(
      self, mock_client_cls: mock.MagicMock
  ) -> None:
    """Verifies table schema fetching formats markdown tables correctly."""
    mock_client = mock_client_cls.return_value
    mock_table = mock.create_autospec(bigquery.Table, instance=True)
    mock_table.schema = [
        bigquery.SchemaField(
            "id", "INTEGER", mode="REQUIRED", description="ID field"
        )
    ]
    mock_client.get_table.return_value = mock_table

    result = fetch_bq_schema.generate_schema_markdown(
        "test-proj", "test-ds", ["table1"]
    )

    expected = (
        "The following is the schema for the table1 RMI BigQuery table:\n\n"
        "| Name | Mode | Type | Description |\n"
        "| --- | --- | --- | --- |\n"
        "| id | REQUIRED | INTEGER | ID field |\n"
    )
    self.assertEqual(result, expected)
    mock_client.get_table.assert_called_once_with("test-proj.test-ds.table1")

  @mock.patch.object(bigquery, "Client", autospec=True)
  def test_generate_schema_markdown_handles_api_call_error(
      self, mock_client_cls: mock.MagicMock
  ) -> None:
    """Verifies GoogleAPICallError is gracefully caught and logged."""
    mock_client = mock_client_cls.return_value
    mock_client.get_table.side_effect = google_exceptions.NotFound(
        "Table not found"
    )

    with self.assertLogs(level="WARNING") as cm:
      result = fetch_bq_schema.generate_schema_markdown(
          "test-proj", "test-ds", ["bad_table"]
      )

    self.assertEqual(result, "\n")
    self.assertIn(
        "Failed to fetch table test-proj.test-ds.bad_table", cm.output[0]
    )

  @mock.patch.object(
      fetch_bq_schema, "generate_schema_markdown", autospec=True
  )
  def test_main_writes_schema_to_output_path(
      self, mock_generate_md: mock.MagicMock
  ) -> None:
    """Verifies CLI main function parses flags and writes output to file."""
    mock_generate_md.return_value = "# Schema Docs\n"
    output_file = pathlib.Path(self.create_tempdir().full_path) / "out.md"
    target_flag = fetch_bq_schema._OUTPUT_PATH

    with flagsaver.flagsaver((target_flag, str(output_file))):
      fetch_bq_schema.main(["fetch_bq_schema"])

    self.assertEqual(output_file.read_text(encoding="utf-8"), "# Schema Docs\n")

  def test_main_raises_usage_error_when_too_many_arguments(self) -> None:
    """Verifies main raises app.UsageError if extra arguments are passed."""
    with self.assertRaises(app.UsageError):
      fetch_bq_schema.main(["fetch_bq_schema", "unexpected_arg"])


if __name__ == "__main__":
  absltest.main()
