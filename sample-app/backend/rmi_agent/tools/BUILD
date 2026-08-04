load("//devtools/python/blaze:pytype.bzl", "pytype_strict_binary", "pytype_strict_contrib_test", "pytype_strict_library")

package(default_visibility = ["//visibility:public"])

licenses(["notice"])

pytype_strict_library(
    name = "fetch_bq_schema_lib",
    srcs = ["fetch_bq_schema.py"],
    deps = [
        "//maps/api/snapping/roads/rmi_agent:common_flags",
        "//third_party/py/absl:app",
        "//third_party/py/absl/flags",
        "//third_party/py/absl/logging",
        "//third_party/py/google/api_core",
        "//third_party/py/google/cloud/bigquery",
    ],
)

pytype_strict_binary(
    name = "fetch_bq_schema",
    srcs = ["fetch_bq_schema.py"],
    deps = [
        ":fetch_bq_schema_lib",
    ],
)

pytype_strict_contrib_test(
    name = "fetch_bq_schema_test",
    srcs = ["fetch_bq_schema_test.py"],
    deps = [
        ":fetch_bq_schema_lib",
        "//third_party/py/absl:app",
        "//third_party/py/absl/flags",
        "//third_party/py/absl/testing:absltest",
        "//third_party/py/absl/testing:flagsaver",
        "//third_party/py/google/api_core",
        "//third_party/py/google/cloud/bigquery",
    ],
)
