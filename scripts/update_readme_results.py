#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


START_MARKER = "<!-- BENCHMARK_RESULTS_START -->"
END_MARKER = "<!-- BENCHMARK_RESULTS_END -->"
GEEKBENCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
GEEKBENCH_SCORE_FETCH_ATTEMPTS = 5
GEEKBENCH_SCORE_FETCH_BASE_DELAY_SECONDS = 3
GEEKBENCH_SCORE_FETCH_MAX_DELAY_SECONDS = 30


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


def parse_geekbench_scores(html: str) -> dict[str, int]:
    scores: dict[str, int] = {}
    pattern = re.compile(
        r"<div\s+class=['\"]score['\"]>\s*([0-9,]+)\s*</div>\s*"
        r"<div\s+class=['\"]note['\"]>\s*([^<]+?)\s*</div>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        value = int(match.group(1).replace(",", ""))
        note = unescape(match.group(2)).strip().lower()
        if note == "single-core score":
            scores["single_core_score"] = value
        elif note == "multi-core score":
            scores["multi_core_score"] = value
    return scores


def retry_after_seconds(headers: Any) -> float | None:
    raw = headers.get("Retry-After") if headers else None
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(raw)
        return max(0.0, retry_at.timestamp() - time.time())
    except (TypeError, ValueError, OSError):
        return None


def geekbench_score_fetch_delay(attempt: int, headers: Any = None) -> float:
    retry_after = retry_after_seconds(headers)
    if retry_after is not None:
        return min(retry_after, GEEKBENCH_SCORE_FETCH_MAX_DELAY_SECONDS)
    delay = GEEKBENCH_SCORE_FETCH_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
    return min(float(delay), GEEKBENCH_SCORE_FETCH_MAX_DELAY_SECONDS)


def fetch_geekbench_scores(url: str) -> tuple[dict[str, int], str | None]:
    error = None
    headers = None
    for attempt in range(1, GEEKBENCH_SCORE_FETCH_ATTEMPTS + 1):
        try:
            with urlopen(Request(url, headers=GEEKBENCH_HEADERS), timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")
            scores = parse_geekbench_scores(html)
            if scores:
                return scores, None
            return {}, "score blocks not found"
        except HTTPError as exc:
            error = f"HTTP {exc.code}"
            headers = exc.headers
        except (OSError, URLError) as exc:
            error = str(exc)
            headers = None
        if attempt < GEEKBENCH_SCORE_FETCH_ATTEMPTS:
            delay = geekbench_score_fetch_delay(attempt, headers)
            print(f"Geekbench score fetch failed for {url} ({error}); retrying in {delay:.1f}s.", file=sys.stderr)
            time.sleep(delay)
    return {}, error


def enrich_geekbench_scores(results: list[dict[str, Any]]) -> None:
    cache: dict[str, tuple[dict[str, int], str | None]] = {}
    for result in results:
        geekbench = result.get("geekbench", {})
        if geekbench.get("status") != "success":
            continue
        if geekbench.get("single_core_score") and geekbench.get("multi_core_score"):
            continue
        url = geekbench.get("browser_url")
        if not url:
            continue
        if url not in cache:
            cache[url] = fetch_geekbench_scores(url)
        scores, error = cache[url]
        geekbench.update(scores)
        if scores:
            geekbench["score_source"] = "geekbench_browser"
        elif error:
            geekbench["score_fetch_error"] = error


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


def geekbench_url(result: dict[str, Any]) -> str:
    url = result.get("geekbench", {}).get("browser_url")
    if not url:
        return ""
    return f"[result]({text(url)})"


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
    enrich_geekbench_scores(results)
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
            "| Target | Runner | Host | CPUs | Geekbench single | Geekbench multi | Geekbench URL | Seq read MiB/s | Seq write MiB/s | 4K read IOPS | 4K write IOPS |",
            "| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
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
                    geekbench_url(result),
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
