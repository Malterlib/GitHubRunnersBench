#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


START_MARKER = "<!-- BENCHMARK_RESULTS_START -->"
END_MARKER = "<!-- BENCHMARK_RESULTS_END -->"


def load_results(root: Path) -> list[dict[str, Any]]:
    results = []
    for path in sorted(root.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and "runner_target" in data:
            results.append(data)
    return results


def text(value: Any) -> str:
    if value is None or value == "":
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def number(value: Any, precision: int = 0) -> str:
    if value is None or value == "":
        return ""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return text(value)
    if precision == 0:
        return str(int(round(numeric)))
    return f"{numeric:.{precision}f}"


def disk_metric(result: dict[str, Any], test: str, key: str, precision: int = 0) -> str:
    disk = result.get("disk", {})
    data = disk.get("tests", {}).get(test, {})
    return number(data.get(key), precision)


def geekbench_score(result: dict[str, Any], key: str) -> str:
    geekbench = result.get("geekbench", {})
    status = geekbench.get("status")
    if status == "success":
        return number(geekbench.get(key))
    if status in {"skipped", "not_requested"}:
        return status
    if status:
        return f"{status}"
    return ""


def host_description(result: dict[str, Any]) -> str:
    system = result.get("system", {})
    machine = system.get("machine") or ""
    os_name = system.get("os") or system.get("system") or ""
    if machine and os_name:
        return f"{os_name} / {machine}"
    return os_name or machine


def sort_key(result: dict[str, Any]) -> tuple[str, str]:
    target = result.get("runner_target", {})
    return (str(target.get("platform", "")), str(target.get("arch", "")))


def build_table(results: list[dict[str, Any]]) -> str:
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        START_MARKER,
        f"Last updated: {updated}",
        "",
    ]

    if not results:
        lines.extend(["No benchmark results have been published yet.", END_MARKER])
        return "\n".join(lines)

    lines.extend(
        [
            "| Target | Runner | Host | CPUs | Geekbench single | Geekbench multi | Seq read MiB/s | Seq write MiB/s | 4K read IOPS | 4K write IOPS |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for result in sorted(results, key=sort_key):
        target = result.get("runner_target", {})
        system = result.get("system", {})
        display = target.get("display") or f"{target.get('platform', '')} {target.get('arch', '')}".strip()
        lines.append(
            "| "
            + " | ".join(
                [
                    text(display),
                    f"`{text(target.get('runner'))}`",
                    text(host_description(result)),
                    number(system.get("cpu_count")),
                    geekbench_score(result, "single_core_score"),
                    geekbench_score(result, "multi_core_score"),
                    disk_metric(result, "sequential_read", "bandwidth_mib_per_second", 1),
                    disk_metric(result, "sequential_write", "bandwidth_mib_per_second", 1),
                    disk_metric(result, "random_read_4k", "iops"),
                    disk_metric(result, "random_write_4k", "iops"),
                ]
            )
            + " |"
        )

    lines.append(END_MARKER)
    return "\n".join(lines)


def update_readme(readme: Path, table: str) -> bool:
    existing = readme.read_text(encoding="utf-8") if readme.exists() else ""
    block = table + "\n"

    if START_MARKER in existing and END_MARKER in existing:
        before = existing.split(START_MARKER, 1)[0]
        after = existing.split(END_MARKER, 1)[1]
        updated = before.rstrip() + "\n\n" + block + after.lstrip("\n")
    else:
        updated = existing.rstrip() + "\n\n## Benchmark Results\n\n" + block

    if updated == existing:
        return False
    readme.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: update_readme_results.py <artifact-root> <README.md>", file=sys.stderr)
        return 2

    artifact_root = Path(sys.argv[1])
    readme = Path(sys.argv[2])
    results = load_results(artifact_root)
    changed = update_readme(readme, build_table(results))
    print(f"Updated {readme} from {len(results)} result file(s); changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
