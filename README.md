# GitHub Runner Benchmarks

This repository benchmarks the GitHub runner targets used by Malterlib's LLVM distribution workflow in `/Source/Malterlib/.github/workflows/Build_LLVM_Distribution_Select.sh`.

The workflow runs:

- Geekbench 6 CPU benchmark where a supported Geekbench build exists.
- `fio` sequential read/write bandwidth.
- `fio` 4 KiB random read/write IOPS.

## Runner Matrix

| Target | Runner | Notes |
| --- | --- | --- |
| Linux x64 | `ubuntu-22.04` | Native host benchmark. |
| Linux arm64 | `ubuntu-22.04-arm` | Uses Geekbench Linux ARM preview build. |
| Linux x86 | `ubuntu-22.04` | Runs disk tests inside the same Debian 12 `linux/386` container target used by the LLVM workflow. Geekbench is skipped because Geekbench 6 has no 32-bit Linux x86 build. |
| macOS arm64 | `macos-26` | Native host benchmark. |
| macOS x64 | `macos-26-intel` | Native host benchmark. |
| Windows x64 | `windows-2022` | Native host benchmark. |
| Windows arm64 | `windows-11-arm` | Native host benchmark. |

## Usage

Run **Benchmark GitHub Runners** from the GitHub Actions workflow dispatch page. The dispatch form lets you enable/disable targets, Geekbench, disk tests, and the `fio` disk size/runtime.

Geekbench runs in trial mode, which uploads CPU results to the Geekbench Browser when the benchmark succeeds.

Each matrix job uploads an artifact named `github-runner-benchmark-<target>` containing:

- `<target>.json` with machine-readable benchmark data.
- `<target>.md` with the same result summarized for humans.

## Benchmark Results

<!-- BENCHMARK_RESULTS_START -->
No benchmark results have been published yet.
<!-- BENCHMARK_RESULTS_END -->
