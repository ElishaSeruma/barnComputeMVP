# M1 C3 synchronized resource results - 2026-10-01

## Verdict

**RETEST REQUIRED.** A synchronized bidirectional physical transfer completed
successfully on the second attempt, with matching size/hash and bounded sampled
memory. The run exposed a retained 100 MiB `assembled.tmp` for each completed
transfer. Because transfer IDs accumulate, this is an unbounded disk-growth
defect relative to C3's pass condition. C3 is therefore not closed.

The defect is being corrected in source. The C3 transfer/resource run must be
repeated using a newly identified corrected artifact. The immutable published
`0.1.0a1` artifact must not be replaced or credited with the fix.

## Setup

- Barn ID: `59be8fa9-62d2-4e6d-83e1-494544026459`.
- Public CA SHA-256: `5fdf961ab0b3ddfc29d9e6e42d91943dd5372ff64f803677a90fa7d53902cae5`.
- Mac: `172.20.10.3`, coordinator plus node
  `25ae5cc9-3c6e-4310-8b89-267ed86e2f0e` on peer port 8455.
- Windows: `172.20.10.10`, node
  `b76031b8-e76f-4931-96c9-de5e9814d9a2` on peer port 8455.
- Both nodes were explicitly enrolled/approved, appeared `ONLINE`, and peer TCP
  connectivity passed in both directions.
- Both files were deterministic 104,857,600-byte fixtures with SHA-256
  `58ccc68aa3be8ed25a1f2fadb7c43a3af56367171841a0d5a27a7997eeab18e4`.
- Physical transport: direct HTTPS over the previously used phone hotspot.
- Published package: `barnCompute==0.1.0a1`; provenance is recorded separately
  in `M1_C2_PROVENANCE_2026-10-01.md`.

## First synchronized attempt

Both directions started at `2026-10-01T03:16:10Z`.

- Windows to Mac passed: direct, 104,857,600 bytes, matching SHA-256,
  76 seconds, ending at `03:17:26Z`.
- Mac to Windows failed after substantial partial progress with
  `CONFIGURATION: Direct peer connection failed` around `03:17:39Z`.
- Mac coordinator and node agent printed no corresponding error and remained
  running. Root cause was not established; do not infer one.
- The partial Windows journal and measurements were preserved.

This is a failed observation followed by a successful retry, consistent with
the earlier unexplained one-time Windows recipient failure. It remains a known
issue if it reproduces again.

## Successful synchronized retry

Fresh shares created fresh transfer IDs and output paths. The transfers began
within 0.18 seconds of each other and overlapped for approximately 71.8 seconds.

| Measurement | Mac host | Windows host |
| --- | ---: | ---: |
| Direction received | Windows to Mac | Mac to Windows |
| Start UTC | `03:24:53Z` | `03:24:53.1768933Z` |
| End UTC | `03:26:05Z` | `03:26:33.0416505Z` |
| Elapsed | 72 s | 99.859 s |
| Fetch exit | 0 | 0 |
| Transport | direct | direct |
| Output bytes | 104,857,600 | 104,857,600 |
| Output SHA-256 | expected/matched | expected/matched |
| Samples | 132 | 180 |
| Coordinator peak RSS | 37,392 KiB | coordinator runs on Mac |
| Node peak RSS/working set | 45,984 KiB | 74,752,000 bytes |
| Free disk before | 9,766,668 KiB | 18,472,083,456 bytes |
| Minimum sampled free disk | 9,357,416 KiB | 18,451,664,896 bytes |
| Free disk after | 9,357,336 KiB | 18,454,810,624 bytes |
| Node-state size before | 409,720 KiB | 170,972,301 bytes |
| Maximum/final node state | 716,944 KiB | 485,563,278 bytes final; 485,563,174 sampled max |

Windows post-run node working set was 71,655,424 bytes, below its sampled peak.
Mac post-run RSS was 34,832 KiB for the coordinator and 17,440 KiB for the
node, both below their sampled peaks. Measurements are observations, not
performance promises.

The Windows free-space delta is much smaller than the sum of logical file
lengths in node state. Logical state totals can count hard-linked content more
than once and therefore must not be interpreted as unique physical allocation.
Both disk measurements are retained as observed rather than reconciled by an
invented explanation.

## Blocking defect

Windows post-run inspection found:

```text
node/transfers/9de52aaa-f3aa-4f4a-bd6c-1061eba15d37/assembled.tmp
```

The file is the completed 100 MiB assembly. The approximately 300 MiB logical
node-state growth per fresh transfer is consistent with retained chunks,
received managed copy, and retained assembly. Transfer chunks and managed copies
are required for current M1 resume/storage semantics; `assembled.tmp` is not.

The source fix removes the assembly in a `finally` block after success or
failure and rejects an existing destination before assembly. Existing
no-clobber and concurrent-destination tests are extended to assert that both
assembly and publication temporary files are absent. A corrected-artifact
physical rerun must demonstrate no retained transfer `.tmp` files and bounded
post-run state growth before C3 can pass.

Local source verification on Windows after packaging the fix with the C5
control path as the unpublished `0.1.0a2` correction candidate:

- Ruff focused check: PASS.
- Focused share/transfer suite: 18 passed, 1 known Starlette deprecation
  warning, 37.22 seconds.
- Definitive full suite: 84 passed, zero failures/skips, 1 known warning,
  363.23 seconds.
- Coverage: 82% (2,603 of 3,167 statements covered).
- Build, Twine and archive screening: PASS.
- Fresh dependency-complete Windows wheel install: `pip check`, version and
  import-from-`site-packages` PASS.
- Wheel SHA-256:
  `eb27cfcc301cbf4272b16139383f97ce779b13876c7b9d6722b3e1d3f06fcd99`.
- JUnit and coverage data are retained under ignored `local-state` paths
  `m1-a2-2026-10-01.xml` and `.coverage-m1-a2-2026-10-01`.

A corrected wheel and Windows clean install now exist. No publication, Mac
install/suite or physical corrected-artifact rerun is claimed yet. C3 remains
RETEST REQUIRED until the same wheel is installed on both physical hosts and
the synchronized run leaves no transfer `.tmp` files.

A later exact-source full-suite rerun reached 82 passes before two real-WSS
tests timed out during WebSocket opening. An isolated retry then failed while
Uvicorn called `platform.system()` with Windows error `0x8007000e` (out of
memory). The same pre-admission data/control tests had passed earlier, including
the 84-test full run above. This host-resource event is retained as a test
environment limitation, not converted into a product PASS; rerun the full suite
when sufficient Windows memory is available.

Mac post-run inspection independently found two retained assemblies, one for
each successful Windows-to-Mac transfer:

```text
node/transfers/54ee82b8-5a00-4bd2-8463-cbd1d6e9f8e0/assembled.tmp
node/transfers/e5efecc3-c9c5-4381-8549-ffd51e7d6fdc/assembled.tmp
```

No other `.tmp` path was reported by the Mac check. The duplicate reproduction
on both operating systems confirms a shared export-lifecycle defect rather than
a platform-specific observation.

## Retained evidence

Windows evidence is under ignored local state
`local-state/m1-c3-hotspot-2026-10-01`, including both resource CSVs, fetch logs,
retry summary JSON, output file, transfer journal and private test state.

Mac evidence remains under private owner state
`$HOME/barncompute-m1-c3-hotspot-2026-10-01`, including both resource CSVs,
fetch logs, outputs and private Barn/node state. Private keys and complete state
directories must not be committed or shared.
