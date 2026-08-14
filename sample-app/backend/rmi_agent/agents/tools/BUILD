load("//devtools/python/blaze:pytype.bzl", "pytype_strict_contrib_test", "pytype_strict_library")

package(default_visibility = ["//visibility:public"])

licenses(["notice"])

pytype_strict_library(
    name = "resolve_location_lib",
    srcs = ["resolve_location.py"],
    deps = [
        "//third_party/py/absl/logging",
        "//third_party/py/google/api_core",
        "//third_party/py/google/auth:__init__",
        "//third_party/py/google/auth:exceptions",
        "//third_party/py/google/auth:transport/requests",
        "//third_party/py/google/cloud/bigquery",
        "//third_party/py/requests",
    ],
)

pytype_strict_contrib_test(
    name = "resolve_location_test",
    srcs = ["resolve_location_test.py"],
    deps = [
        ":resolve_location_lib",
        "//third_party/py/absl/testing:absltest",
        "//third_party/py/google/api_core",
        "//third_party/py/google/auth:exceptions",
        "//third_party/py/google/auth:transport/requests",
        "//third_party/py/google/cloud/bigquery",
        "//third_party/py/requests",
    ],
)
