load("//devtools/python/blaze:pytype.bzl", "pytype_strict_library")

package(default_visibility = ["//visibility:public"])

licenses(["notice"])

pytype_strict_library(
    name = "rmi_agent",
    srcs = [
        "prompts.py",
        "rmi_agent.py",
    ],
    data = [
        "resources/rmi_schemas.md",
    ] + glob(["skills/**"]),
    deps = [
        "//maps/api/snapping/roads/rmi_agent:common_flags",
        "//maps/api/snapping/roads/rmi_agent/agents/tools:resolve_location_lib",
        "//third_party/py/absl/logging",
        "//third_party/py/google/adk",
        "//third_party/py/google/auth:__init__",
        "//third_party/py/google/genai",
    ],
)
