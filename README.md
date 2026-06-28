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
| macOS x64 | `macos-15-intel` | Native host benchmark. |
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
Last updated: 2026-06-28 09:13:37 UTC

| Target | Runner | Host | CPUs | Geekbench single | Geekbench multi | Geekbench URL | Seq read MiB/s | Seq write MiB/s | 4K read IOPS | 4K write IOPS |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Linux arm64 | `ubuntu-22.04-arm` | Linux-6.8.0-1059-azure-aarch64-with-glibc2.35 / aarch64 | 4 | 1642 | 5420 | [result](https://browser.geekbench.com/v6/cpu/18511286) | 441.6 | 154.6 | 7270 | 790 |
| Linux x64 | `ubuntu-22.04` | Linux-6.8.0-1059-azure-x86_64-with-glibc2.35 / x86_64 | 4 | 1543 | 3588 | [result](https://browser.geekbench.com/v6/cpu/18511293) | 442.5 | 443.9 | 7259 | 12644 |
| Linux x86 | `ubuntu-22.04` | Linux-6.8.0-1059-azure-x86_64-with-glibc2.36 / x86_64 | 4 | skipped | skipped |  | 442.7 | 444.4 | 6614 | 11024 |
| Windows arm64 | `windows-11-arm` | Windows-11-10.0.26200-SP0 / ARM64 | 4 | 1646 | 5447 | [result](https://browser.geekbench.com/v6/cpu/18511290) | 442.5 | 165.9 | 6109 | 996 |
| Windows x64 | `windows-2022` | Windows-2022Server-10.0.20348-SP0 / AMD64 | 4 | 1957 | 4445 | [result](https://browser.geekbench.com/v6/cpu/18511289) | 537.5 | 267.7 | 9995 | 19233 |
| macOS arm64 | `macos-26` | macOS-26.4-arm64-arm-64bit / arm64 | 3 | 2041 | 3805 | [result](https://browser.geekbench.com/v6/cpu/18511288) | 4491.2 | 2639.2 | 10170 | 13655 |
| macOS x64 | `macos-15-intel` | macOS-15.7.7-x86_64-i386-64bit / x86_64 | 4 | known_issue | known_issue |  | 1544.5 | 631.3 | 2790 | 7507 |
<!-- BENCHMARK_RESULTS_END -->
