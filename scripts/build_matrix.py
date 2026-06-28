#!/usr/bin/env python3
import json
import os
import sys


ROWS = [
    {
        "input": "INPUT_LINUX_X64",
        "id": "linux-x64",
        "display": "Linux x64",
        "platform": "Linux",
        "arch": "x64",
        "runner": "ubuntu-22.04",
        "build_in_container": False,
        "container_image": "",
        "container_platform": "",
    },
    {
        "input": "INPUT_LINUX_ARM64",
        "id": "linux-arm64",
        "display": "Linux arm64",
        "platform": "Linux",
        "arch": "arm64",
        "runner": "ubuntu-22.04-arm",
        "build_in_container": False,
        "container_image": "",
        "container_platform": "",
    },
    {
        "input": "INPUT_LINUX_X86",
        "id": "linux-x86",
        "display": "Linux x86",
        "platform": "Linux",
        "arch": "x86",
        "runner": "ubuntu-22.04",
        "build_in_container": True,
        "container_image": "debian:12@sha256:8a8cd02c5912770b4980228a54d4aff9e4f986f1eb2525d2d371dec5232cefcc",
        "container_platform": "linux/386",
    },
    {
        "input": "INPUT_MACOS_ARM64",
        "id": "macos-arm64",
        "display": "macOS arm64",
        "platform": "macOS",
        "arch": "arm64",
        "runner": "macos-26",
        "build_in_container": False,
        "container_image": "",
        "container_platform": "",
    },
    {
        "input": "INPUT_MACOS_X64",
        "id": "macos-x64",
        "display": "macOS x64",
        "platform": "macOS",
        "arch": "x64",
        "runner": "macos-15-intel",
        "build_in_container": False,
        "container_image": "",
        "container_platform": "",
    },
    {
        "input": "INPUT_WINDOWS_X64",
        "id": "windows-x64",
        "display": "Windows x64",
        "platform": "Windows",
        "arch": "x64",
        "runner": "windows-2022",
        "build_in_container": False,
        "container_image": "",
        "container_platform": "",
    },
    {
        "input": "INPUT_WINDOWS_ARM64",
        "id": "windows-arm64",
        "display": "Windows arm64",
        "platform": "Windows",
        "arch": "arm64",
        "runner": "windows-11-arm",
        "build_in_container": False,
        "container_image": "",
        "container_platform": "",
    },
]


def enabled(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    include = []
    for row in ROWS:
        if enabled(row["input"]):
            item = dict(row)
            del item["input"]
            include.append(item)

    if not include:
        print("At least one platform/architecture checkbox must be enabled.", file=sys.stderr)
        return 1

    matrix = json.dumps({"include": include}, separators=(",", ":"))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"matrix={matrix}\n")

    print(json.dumps({"include": include}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
