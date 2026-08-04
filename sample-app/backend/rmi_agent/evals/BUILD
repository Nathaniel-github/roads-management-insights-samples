load("//devtools/python/blaze:pytype.bzl", "pytype_binary", "pytype_library", "pytype_strict_contrib_test")

package(default_visibility = ["//visibility:public"])

licenses(["notice"])

filegroup(
    name = "evalsets",
    srcs = glob(["evalsets/*.json"]),
)

pytype_library(
    name = "base_autorater",
    srcs = ["base_autorater.py"],
    strict_deps = False,
)

pytype_library(
    name = "golden_match_autorater",
    srcs = ["golden_match_autorater.py"],
    strict_deps = False,
    deps = [
        ":base_autorater",
        "//third_party/py/google/cloud/aiplatform",
    ],
)

pytype_library(
    name = "sql_data_autorater",
    srcs = ["sql_data_autorater.py"],
    strict_deps = False,
    deps = [
        ":base_autorater",
        "//third_party/py/db_dtypes",
        "//third_party/py/google/cloud/aiplatform",
        "//third_party/py/google/cloud/bigquery",
        "//third_party/py/pandas",
    ],
)

pytype_library(
    name = "tool_trajectory_autorater",
    srcs = ["tool_trajectory_autorater.py"],
    strict_deps = False,
    deps = [
        ":base_autorater",
        "//third_party/py/google/adk",
        "//third_party/py/google/cloud/aiplatform",
        "//third_party/py/google/genai",
    ],
)

pytype_library(
    name = "eval_utils",
    srcs = ["eval_utils.py"],
    strict_deps = False,
    deps = [
        ":base_autorater",
        ":golden_match_autorater",
        ":sql_data_autorater",
        ":tool_trajectory_autorater",
        "//third_party/py/google/cloud/aiplatform",
        "//third_party/py/pandas",
    ],
)

pytype_strict_contrib_test(
    name = "eval_utils_test",
    srcs = ["eval_utils_test.py"],
    deps = [
        ":base_autorater",
        ":eval_utils",
        "//third_party/py/absl/testing:absltest",
        "//third_party/py/google/cloud/aiplatform",
        "//third_party/py/pandas",
    ],
)

pytype_strict_contrib_test(
    name = "autoraters_test",
    srcs = ["autoraters_test.py"],
    deps = [
        ":base_autorater",
        ":eval_utils",
        ":golden_match_autorater",
        ":sql_data_autorater",
        ":tool_trajectory_autorater",
        "//third_party/py/absl/testing:absltest",
        "//third_party/py/absl/testing:parameterized",
        "//third_party/py/db_dtypes",
        "//third_party/py/google/cloud/bigquery",
        "//third_party/py/pandas",
    ],
)

pytype_binary(
    name = "local_eval",
    srcs = ["local_eval.py"],
    data = [":evalsets"],
    strict_deps = False,
    deps = [
        ":eval_utils",
        "//learning/agents/orcas/framework/runners:secure_runner",
        "//maps/api/snapping/roads/rmi_agent:common_flags",
        "//maps/api/snapping/roads/rmi_agent/agents:rmi_agent",
        "//pyglib:resources",
        "//third_party/py/absl:app",
        "//third_party/py/absl/flags",
        "//third_party/py/google/cloud/aiplatform",
        "//third_party/py/google/genai",
        "//third_party/py/pandas",
        "//third_party/py/tenacity",
    ],
)
