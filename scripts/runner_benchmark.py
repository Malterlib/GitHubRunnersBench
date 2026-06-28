#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import glob
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


ARTIFACT_DIR = Path("artifacts")
GEEKBENCH_DEFAULT_VERSION = "6.7.1"


def log(message: str) -> None:
    print(message, flush=True)


def truthy(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def command_name(command: list[str | os.PathLike[str]]) -> str:
    return " ".join(str(part) for part in command[:3]) + (" ..." if len(command) > 3 else "")


def run_command(
    command: list[str | os.PathLike[str]],
    *,
    timeout: int | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    quiet: bool = False,
    check: bool = False,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    if not quiet:
        log(f"+ {command_name(command)}")
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0 and completed.stdout:
        print(completed.stdout)
    if check and completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {command_name(command)}")
    return completed


def ensure_executable(path: Path) -> None:
    if os.name != "nt":
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def safe_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}, got {value}")
    return value


def windows_total_memory_bytes() -> int | None:
    if os.name != "nt":
        return None

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return int(status.ullTotalPhys)
    return None


def total_memory_bytes() -> int | None:
    if sys.platform.startswith("linux"):
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1]) * 1024
    if sys.platform == "darwin":
        completed = run_command(["sysctl", "-n", "hw.memsize"], quiet=True)
        if completed.returncode == 0:
            try:
                return int(completed.stdout.strip())
            except ValueError:
                return None
    return windows_total_memory_bytes()


def collect_system_info() -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "total_memory_bytes": total_memory_bytes(),
    }


def config_from_env() -> dict[str, Any]:
    return {
        "id": os.environ.get("BENCHMARK_ID", "local"),
        "display": os.environ.get("BENCHMARK_DISPLAY", platform.platform()),
        "platform": os.environ.get("BENCHMARK_PLATFORM", platform.system()),
        "arch": os.environ.get("BENCHMARK_ARCH", platform.machine()),
        "runner": os.environ.get("BENCHMARK_RUNNER", os.environ.get("RUNNER_NAME", "")),
        "build_in_container": truthy(os.environ.get("BENCHMARK_BUILD_IN_CONTAINER")),
        "container_image": os.environ.get("BENCHMARK_CONTAINER_IMAGE", ""),
        "container_platform": os.environ.get("BENCHMARK_CONTAINER_PLATFORM", ""),
        "run_geekbench": truthy(os.environ.get("BENCHMARK_RUN_GEEKBENCH"), True),
        "run_disk": truthy(os.environ.get("BENCHMARK_RUN_DISK"), True),
        "disk_size_mb": safe_int_env("BENCHMARK_DISK_SIZE_MB", 1024, 64, 65536),
        "disk_runtime_seconds": safe_int_env("BENCHMARK_DISK_RUNTIME_SECONDS", 15, 1, 600),
        "geekbench_version": os.environ.get("GEEKBENCH_VERSION", GEEKBENCH_DEFAULT_VERSION),
    }


def github_info() -> dict[str, str]:
    keys = [
        "GITHUB_ACTION",
        "GITHUB_ACTOR",
        "GITHUB_EVENT_NAME",
        "GITHUB_JOB",
        "GITHUB_REF",
        "GITHUB_REPOSITORY",
        "GITHUB_RUN_ATTEMPT",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_NUMBER",
        "GITHUB_SHA",
        "RUNNER_ARCH",
        "RUNNER_ENVIRONMENT",
        "RUNNER_NAME",
        "RUNNER_OS",
        "RUNNER_TEMP",
    ]
    return {key: os.environ[key] for key in keys if key in os.environ}


def create_base_result(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "started_at_unix": int(time.time()),
        "runner_target": {
            "id": config["id"],
            "display": config["display"],
            "platform": config["platform"],
            "arch": config["arch"],
            "runner": config["runner"],
            "build_in_container": config["build_in_container"],
            "container_image": config["container_image"],
            "container_platform": config["container_platform"],
        },
        "github": github_info(),
        "system": collect_system_info(),
        "geekbench": {"status": "not_requested"} if not config["run_geekbench"] else {},
        "disk": {"status": "not_requested"} if not config["run_disk"] else {},
    }


def download_file(url: str, destination: Path) -> None:
    log(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=60) as response:
        with destination.open("wb") as handle:
            total = int(response.headers.get("Content-Length", "0") or "0")
            downloaded = 0
            next_report = 64 * 1024 * 1024
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if downloaded >= next_report:
                    if total:
                        log(f"Downloaded {downloaded // 1048576} MiB of {total // 1048576} MiB")
                    else:
                        log(f"Downloaded {downloaded // 1048576} MiB")
                    next_report += 64 * 1024 * 1024


def assert_zip_path(root: Path, member_name: str) -> Path:
    target = root / member_name
    resolved_root = root.resolve()
    resolved_target = target.resolve(strict=False)
    if resolved_root != resolved_target and resolved_root not in resolved_target.parents:
        raise RuntimeError(f"Refusing to extract ZIP member outside destination: {member_name}")
    return target


def extract_zip_preserving_metadata(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as zip_handle:
        for info in zip_handle.infolist():
            target = assert_zip_path(destination, info.filename)
            mode = info.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            permissions = mode & 0o777

            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                if permissions:
                    target.chmod(permissions)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()

            if file_type == stat.S_IFLNK:
                os.symlink(zip_handle.read(info).decode("utf-8"), target)
                continue

            with zip_handle.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            if permissions:
                target.chmod(permissions)


def geekbench_download(version: str) -> tuple[str, str, str, bool]:
    system = platform.system()
    machine = platform.machine().lower()
    base = "https://cdn.geekbench.com"
    if system == "Darwin":
        filename = f"Geekbench-{version}-Mac.zip"
        return f"{base}/{filename}", filename, "mac", False
    if system == "Windows":
        filename = f"Geekbench-{version}-WindowsSetup.exe"
        return f"{base}/{filename}", filename, "windows", False
    if system == "Linux" and machine in {"x86_64", "amd64"}:
        filename = f"Geekbench-{version}-Linux.tar.gz"
        return f"{base}/{filename}", filename, "linux", False
    if system == "Linux" and machine in {"aarch64", "arm64"}:
        filename = f"Geekbench-{version}-LinuxARMPreview.tar.gz"
        return f"{base}/{filename}", filename, "linux-arm-preview", True
    raise RuntimeError(f"Geekbench is not supported for {system} {platform.machine()}")


def find_windows_geekbench() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Geekbench 6" / "geekbench6.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Geekbench 6" / "geekbench6.exe",
    ]
    for pattern in [
        r"C:\Program Files*\Geekbench 6\geekbench6.exe",
        r"C:\Users\*\AppData\Local\Programs\Geekbench 6\geekbench6.exe",
    ]:
        candidates.extend(Path(path) for path in glob.glob(pattern))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def install_geekbench(version: str) -> tuple[Path, bool]:
    url, filename, kind, preview = geekbench_download(version)
    install_root = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "geekbench-install"
    install_root.mkdir(parents=True, exist_ok=True)
    archive = install_root / filename
    if not archive.exists():
        download_file(url, archive)

    if kind == "windows":
        existing = find_windows_geekbench()
        if existing:
            return existing, preview
        completed = run_command([archive, "/S"], timeout=900)
        if completed.returncode != 0:
            completed = run_command([archive, "/VERYSILENT", "/NORESTART"], timeout=900)
        if completed.returncode != 0:
            raise RuntimeError("Geekbench Windows installer failed")
        deadline = time.time() + 120
        while time.time() < deadline:
            installed = find_windows_geekbench()
            if installed:
                return installed, preview
            time.sleep(2)
        raise RuntimeError("Geekbench installed, but geekbench6.exe was not found")

    extract_root = install_root / "extract"
    if extract_root.exists():
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True)

    if kind == "mac":
        extract_zip_preserving_metadata(archive, extract_root)
        executable = extract_root / "Geekbench 6.app" / "Contents" / "Resources" / "geekbench6"
    else:
        with tarfile.open(archive) as tar_handle:
            tar_handle.extractall(extract_root)
        matches = sorted(extract_root.glob("Geekbench-*/geekbench6"))
        if not matches:
            raise RuntimeError("geekbench6 binary was not found after extraction")
        executable = matches[0]

    ensure_executable(executable)
    return executable, preview


def parse_geekbench_output(output: str) -> dict[str, Any]:
    single = None
    multi = None
    single_match = re.search(r"Single[- ]Core Score\s+([0-9]+)", output, re.IGNORECASE)
    multi_match = re.search(r"Multi[- ]Core Score\s+([0-9]+)", output, re.IGNORECASE)
    if single_match:
        single = int(single_match.group(1))
    if multi_match:
        multi = int(multi_match.group(1))

    urls = re.findall(r"https://browser\.geekbench\.com/v6/cpu/[^\s)]+", output)
    version_match = re.search(r"Geekbench\s+([0-9][0-9.]*)(?:\s+Preview)?", output)
    return {
        "single_core_score": single,
        "multi_core_score": multi,
        "browser_url": urls[0] if urls else None,
        "detected_version": version_match.group(1) if version_match else None,
    }


def run_geekbench(config: dict[str, Any]) -> dict[str, Any]:
    if config["arch"] == "x86":
        return {
            "status": "skipped",
            "reason": "Geekbench 6 does not provide a 32-bit Linux x86 build.",
        }
    try:
        executable, preview = install_geekbench(config["geekbench_version"])
        command = [executable, "--cpu"]
        log("Running Geekbench CPU benchmark.")
        completed = run_command(command, timeout=3600, cwd=executable.parent, quiet=True)
        output = completed.stdout or ""
        print(output)
        parsed = parse_geekbench_output(output)
        result: dict[str, Any] = {
            "status": "success" if completed.returncode == 0 else "failed",
            "return_code": completed.returncode,
            "downloaded_version": config["geekbench_version"],
            "preview_build": preview,
            **parsed,
        }
        if completed.returncode != 0:
            result["output_tail"] = "\n".join(output.splitlines()[-80:])
        if completed.returncode != 0 and (parsed["single_core_score"] or parsed["multi_core_score"]):
            result["status"] = "failed_after_scores"
        return result
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "downloaded_version": config["geekbench_version"]}


def package_manager_prefix() -> list[str]:
    if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    return ["sudo"]


def find_executable(names: list[str]) -> Path | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    if os.name == "nt":
        candidates = [
            Path(r"C:\ProgramData\chocolatey\bin\fio.exe"),
            Path(r"C:\Program Files\fio\fio.exe"),
            Path(r"C:\tools\fio\fio.exe"),
        ]
        for pattern in [r"C:\Program Files*\fio*\fio.exe", r"C:\tools\fio*\fio.exe"]:
            candidates.extend(Path(path) for path in glob.glob(pattern))
        for candidate in candidates:
            if candidate.exists():
                return candidate
    return None


def install_fio() -> Path:
    fio = find_executable(["fio", "fio.exe"])
    if fio:
        return fio

    system = platform.system()
    if system == "Linux":
        prefix = package_manager_prefix()
        run_command(prefix + ["apt-get", "update"], timeout=600, check=True, capture=False)
        run_command(prefix + ["apt-get", "install", "-y", "fio"], timeout=900, check=True, capture=False)
    elif system == "Darwin":
        run_command(["brew", "install", "fio"], timeout=1800, check=True, capture=False)
    elif system == "Windows":
        run_command(["choco", "install", "fio", "-y", "--no-progress"], timeout=1800, check=True, capture=False)
    else:
        raise RuntimeError(f"fio installation is not supported on {system}")

    fio = find_executable(["fio", "fio.exe"])
    if not fio:
        raise RuntimeError("fio installation completed but fio was not found on PATH")
    return fio


def fio_metric(job: dict[str, Any], op: str) -> dict[str, Any]:
    data = job.get(op, {})
    bw_bytes = data.get("bw_bytes")
    if bw_bytes is None and data.get("bw") is not None:
        bw_bytes = float(data["bw"]) * 1024.0
    latency_ns = data.get("clat_ns", {}).get("mean")
    return {
        "bandwidth_bytes_per_second": float(bw_bytes) if bw_bytes is not None else None,
        "bandwidth_mib_per_second": (float(bw_bytes) / 1048576.0) if bw_bytes is not None else None,
        "iops": float(data["iops"]) if data.get("iops") is not None else None,
        "mean_completion_latency_ms": (float(latency_ns) / 1000000.0) if latency_ns is not None else None,
    }


def run_fio_once(
    fio: Path,
    *,
    name: str,
    filename: Path,
    rw: str,
    bs: str,
    size_mb: int,
    runtime_seconds: int | None,
    direct: bool,
) -> dict[str, Any]:
    command: list[str | os.PathLike[str]] = [
        fio,
        f"--name={name}",
        f"--filename={filename}",
        f"--rw={rw}",
        f"--bs={bs}",
        f"--size={size_mb}m",
        "--ioengine=sync",
        "--numjobs=1",
        "--group_reporting=1",
        "--output-format=json",
        f"--direct={1 if direct else 0}",
    ]
    if runtime_seconds is not None:
        command.extend(["--time_based=1", f"--runtime={runtime_seconds}"])
    completed = run_command(command, timeout=(runtime_seconds or 300) + 600, quiet=True)
    if completed.returncode != 0:
        raise RuntimeError(f"fio {name} failed with direct={direct}")
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"fio {name} did not return JSON: {exc}") from exc
    op = "read" if "read" in rw else "write"
    job = raw["jobs"][0]
    return {
        "status": "success",
        "rw": rw,
        "block_size": bs,
        "direct_io": direct,
        **fio_metric(job, op),
    }


def run_fio_job(
    fio: Path,
    *,
    name: str,
    filename: Path,
    rw: str,
    bs: str,
    size_mb: int,
    runtime_seconds: int | None,
) -> dict[str, Any]:
    try:
        return run_fio_once(
            fio,
            name=name,
            filename=filename,
            rw=rw,
            bs=bs,
            size_mb=size_mb,
            runtime_seconds=runtime_seconds,
            direct=True,
        )
    except Exception as direct_error:
        log(f"fio {name} direct I/O failed; retrying without direct I/O: {direct_error}")
        result = run_fio_once(
            fio,
            name=name,
            filename=filename,
            rw=rw,
            bs=bs,
            size_mb=size_mb,
            runtime_seconds=runtime_seconds,
            direct=False,
        )
        result["direct_io_fallback_reason"] = str(direct_error)
        return result


def benchmark_disk(config: dict[str, Any]) -> dict[str, Any]:
    try:
        fio = install_fio()
        base_temp = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
        disk_dir = base_temp / "github-runner-benchmark-disk"
        disk_dir.mkdir(parents=True, exist_ok=True)
        filename = disk_dir / f"{config['id']}-fio-testfile"
        if filename.exists():
            filename.unlink()

        log("Running fio disk bandwidth and 4 KiB IOPS benchmark.")
        tests = {
            "sequential_write": run_fio_job(
                fio,
                name="sequential_write",
                filename=filename,
                rw="write",
                bs="1m",
                size_mb=config["disk_size_mb"],
                runtime_seconds=None,
            ),
            "sequential_read": run_fio_job(
                fio,
                name="sequential_read",
                filename=filename,
                rw="read",
                bs="1m",
                size_mb=config["disk_size_mb"],
                runtime_seconds=None,
            ),
            "random_write_4k": run_fio_job(
                fio,
                name="random_write_4k",
                filename=filename,
                rw="randwrite",
                bs="4k",
                size_mb=config["disk_size_mb"],
                runtime_seconds=config["disk_runtime_seconds"],
            ),
            "random_read_4k": run_fio_job(
                fio,
                name="random_read_4k",
                filename=filename,
                rw="randread",
                bs="4k",
                size_mb=config["disk_size_mb"],
                runtime_seconds=config["disk_runtime_seconds"],
            ),
        }
        try:
            filename.unlink()
        except FileNotFoundError:
            pass
        return {
            "status": "success",
            "tool": str(fio),
            "size_mb": config["disk_size_mb"],
            "random_runtime_seconds": config["disk_runtime_seconds"],
            "tests": tests,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def result_path(config: dict[str, Any]) -> Path:
    return ARTIFACT_DIR / f"{config['id']}.json"


def markdown_path(config: dict[str, Any]) -> Path:
    return ARTIFACT_DIR / f"{config['id']}.md"


def metric(value: Any, precision: int = 1) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    return str(value)


def write_markdown_summary(config: dict[str, Any], result: dict[str, Any]) -> str:
    target = result["runner_target"]
    lines = [
        f"# {target['display']}",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Runner label | `{target['runner']}` |",
        f"| Target | `{target['platform']} {target['arch']}` |",
        f"| Host OS | `{result['system']['os']}` |",
        f"| Host machine | `{result['system']['machine']}` |",
        f"| CPU count | `{result['system']['cpu_count']}` |",
    ]
    if target["build_in_container"]:
        lines.extend(
            [
                f"| Container image | `{target['container_image']}` |",
                f"| Container platform | `{target['container_platform']}` |",
            ]
        )

    geekbench = result.get("geekbench", {})
    lines.extend(["", "## Geekbench CPU", ""])
    if geekbench.get("status") == "success":
        lines.extend(
            [
                "| Single-core | Multi-core | Browser URL |",
                "| ---: | ---: | --- |",
                f"| {metric(geekbench.get('single_core_score'), 0)} | {metric(geekbench.get('multi_core_score'), 0)} | {geekbench.get('browser_url') or 'not uploaded'} |",
            ]
        )
    else:
        detail = geekbench.get("reason") or geekbench.get("error") or geekbench.get("status", "unknown")
        lines.append(f"Status: `{geekbench.get('status', 'unknown')}`. {detail}")

    disk = result.get("disk", {})
    lines.extend(["", "## Disk", ""])
    if disk.get("status") == "success":
        lines.extend(
            [
                "| Test | Bandwidth MiB/s | IOPS | Mean latency ms | Direct I/O |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for name, data in disk["tests"].items():
            lines.append(
                f"| `{name}` | {metric(data.get('bandwidth_mib_per_second'))} | {metric(data.get('iops'))} | {metric(data.get('mean_completion_latency_ms'), 3)} | `{data.get('direct_io')}` |"
            )
    else:
        detail = disk.get("error") or disk.get("status", "unknown")
        lines.append(f"Status: `{disk.get('status', 'unknown')}`. {detail}")

    markdown = "\n".join(lines) + "\n"
    markdown_path(config).write_text(markdown, encoding="utf-8")
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as handle:
                handle.write(markdown)
                handle.write("\n")
        except OSError as exc:
            log(f"Could not append to GITHUB_STEP_SUMMARY: {exc}")
    return markdown


def write_result(config: dict[str, Any], result: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    result["finished_at_unix"] = int(time.time())
    result_path(config).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown_summary(config, result)


def benchmark_failed(result: dict[str, Any]) -> bool:
    return result.get("geekbench", {}).get("status") in {"failed", "failed_after_scores"} or result.get("disk", {}).get("status") == "failed"


def run_inside_container() -> int:
    config = config_from_env()
    config["build_in_container"] = True
    result = create_base_result(config)
    if config["run_geekbench"]:
        result["geekbench"] = {
            "status": "skipped",
            "reason": "Geekbench 6 is not available for the 32-bit linux/386 container target.",
        }
    if config["run_disk"]:
        result["disk"] = benchmark_disk(config)
    write_result(config, result)
    return 1 if benchmark_failed(result) else 0


def docker_run_container(config: dict[str, Any]) -> int:
    if platform.system() != "Linux":
        raise RuntimeError("Container benchmark targets are only supported from Linux runners")
    if not shutil.which("docker"):
        raise RuntimeError("Docker is required for container benchmark targets")

    workspace = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd())).resolve()
    runner_temp = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())).resolve()
    env_args: list[str] = []
    for key in [
        "BENCHMARK_ID",
        "BENCHMARK_DISPLAY",
        "BENCHMARK_PLATFORM",
        "BENCHMARK_ARCH",
        "BENCHMARK_RUNNER",
        "BENCHMARK_CONTAINER_IMAGE",
        "BENCHMARK_CONTAINER_PLATFORM",
        "BENCHMARK_RUN_GEEKBENCH",
        "BENCHMARK_RUN_DISK",
        "BENCHMARK_DISK_SIZE_MB",
        "BENCHMARK_DISK_RUNTIME_SECONDS",
        "GEEKBENCH_VERSION",
        "GITHUB_ACTION",
        "GITHUB_ACTOR",
        "GITHUB_EVENT_NAME",
        "GITHUB_JOB",
        "GITHUB_REF",
        "GITHUB_REPOSITORY",
        "GITHUB_RUN_ATTEMPT",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_NUMBER",
        "GITHUB_SHA",
        "RUNNER_ARCH",
        "RUNNER_ENVIRONMENT",
        "RUNNER_NAME",
        "RUNNER_OS",
    ]:
        if key in os.environ:
            env_args.extend(["-e", f"{key}={os.environ[key]}"])
    env_args.extend(["-e", "BENCHMARK_BUILD_IN_CONTAINER=true", "-e", "RUNNER_TEMP=/runner-temp"])

    script = (
        "apt-get update && "
        "apt-get install -y --no-install-recommends ca-certificates fio python3 && "
        "python3 scripts/runner_benchmark.py --inside-container"
    )
    command = [
        "docker",
        "run",
        "--rm",
        "--platform",
        config["container_platform"],
        "-v",
        f"{workspace}:/work",
        "-v",
        f"{runner_temp}:/runner-temp",
        "-w",
        "/work",
        *env_args,
        config["container_image"],
        "bash",
        "-lc",
        script,
    ]
    completed = run_command(command, timeout=3600, capture=False)

    markdown = markdown_path(config)
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file and markdown.exists():
        with open(summary_file, "a", encoding="utf-8") as handle:
            handle.write(markdown.read_text(encoding="utf-8"))
            handle.write("\n")
    return completed.returncode


def main() -> int:
    if "--inside-container" in sys.argv:
        return run_inside_container()

    config = config_from_env()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Benchmark target: {config['display']} on {config['runner']}")

    if config["build_in_container"]:
        return docker_run_container(config)

    result = create_base_result(config)
    if config["run_geekbench"]:
        result["geekbench"] = run_geekbench(config)
    if config["run_disk"]:
        result["disk"] = benchmark_disk(config)
    write_result(config, result)
    return 1 if benchmark_failed(result) else 0


if __name__ == "__main__":
    raise SystemExit(main())
