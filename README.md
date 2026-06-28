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
Last updated: 2026-06-28 09:00:23 UTC

| Target | Runner | Host | CPUs | Geekbench single | Geekbench multi | Geekbench URL | Seq read MiB/s | Seq write MiB/s | 4K read IOPS | 4K write IOPS |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Linux arm64 | `ubuntu-22.04-arm` | Linux-6.8.0-1059-azure-aarch64-with-glibc2.35 / aarch64 | 4 | 1652 | 5507 | [result](https://browser.geekbench.com/v6/cpu/18511184) | 439.9 | 160.4 | 7771 | 687 |
| Linux x64 | `ubuntu-22.04` | Linux-6.8.0-1059-azure-x86_64-with-glibc2.35 / x86_64 | 4 | 1594 | 3659 | [result](https://browser.geekbench.com/v6/cpu/18511189) | 439.9 | 441.4 | 7170 | 13041 |
| Linux x86 | `ubuntu-22.04` | Linux-6.8.0-1059-azure-x86_64-with-glibc2.36 / x86_64 | 4 | skipped | skipped |  | 439.5 | 442.1 | 8151 | 13292 |
| Windows arm64 | `windows-11-arm` | Windows-11-10.0.26200-SP0 / ARM64 | 4 | 1605 | 5353 | [result](https://browser.geekbench.com/v6/cpu/18511190) | 381.8 | 133.9 | 5695 | 594 |
| Windows x64 | `windows-2022` | Windows-2022Server-10.0.20348-SP0 / AMD64 | 4 | 1465 | 3397 | [result](https://browser.geekbench.com/v6/cpu/18511195) | 439.3 | 442.1 | 7216 | 11797 |
| macOS arm64 | `macos-26` | macOS-26.4-arm64-arm-64bit / arm64 | 3 | 2349 | 5566 | [result](https://browser.geekbench.com/v6/cpu/18511182) | 7366.9 | 4376.1 | 26655 | 20646 |
| macOS x64 | `macos-26-intel` | macOS-26.4-x86_64-i386-64bit / x86_64 | 4 | known_issue | known_issue |  | 1508.1 | 1319.6 | 3791 | 5555 |
<!-- BENCHMARK_RESULTS_END -->
