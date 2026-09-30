# M1 physical test results - 2026-09-29

Release candidate: `barnCompute==0.1.0a1`. The local repository was at
`072ac4c` when this record was written. Results below are from user-shared
Mac and Windows terminal output during a two-machine phone-hotspot test.
This file records observations, not an M1 acceptance verdict.

## Setup and connectivity

| Check | Result | Evidence |
| --- | --- | --- |
| Installed CLI version | PASS | Mac `$HOME/.venv-m1-release/bin/barn --version` and Windows `.venv-m1-release\Scripts\barn.exe --version` both printed `0.1.0a1`. Version output alone does not establish installation provenance. |
| Windows installed wheel content | PASS | Official TestPyPI release JSON listed wheel SHA-256 `f1cbc28f916749b15cc46a2e5ab7760ad27d9693153c76e36ec2d070f85acd86`. A fresh wheel download to ignored `local-state` matched that hash; all 30 checked wheel entries except `RECORD` matched the files in the Windows release environment byte-for-byte. The original pip install URL/log was not recovered. |
| Mac installed wheel content | PASS | A fresh Mac download from the same TestPyPI release matched published wheel SHA-256 `f1cbc28f916749b15cc46a2e5ab7760ad27d9693153c76e36ec2d070f85acd86`; all 30 checked wheel entries except `RECORD` matched the files in the Mac release environment byte-for-byte. The original pip install URL/log was not recovered. |
| Coordinator and CA | PASS | Mac coordinator initialized with Barn ID `e8082a26-b933-4e06-bf44-a5b132370757` at `172.20.10.3`. Exported public CA certificate fingerprint was `62afa00097bb82bc36be9bbb7a501e7a68c9c489c450d2b9bcea600674b6e42b`; Windows calculated the same certificate fingerprint after transfer. |
| Coordinator TCP | PASS | Windows `Test-NetConnection 172.20.10.3 -Port 8443` reported `TcpTestSucceeded : True` from `172.20.10.10`. |
| Node enrollment | PASS | Windows node `f5df8658-d400-4044-b1e9-7dfd0887373e` was approved after its pending identity fingerprint `b09feb90cbaf00261b5ce01d4d6bcd9f88ca6aaa4b0017b03c134b3c2f45c504` matched node initialization. Mac node `08cb7bc6-bcd6-43f9-b9a4-7e595d67ca3b` reported `APPROVED`; its initialization fingerprint was `d2950700fb7e17a6f33942a1227e1464f6dd9e39684677910a84aebc36a583b2`. The Mac pending listing was not captured in this conversation. |
| Registry and peer TCP | PASS | Both registry refreshes listed MacNode `ONLINE` at `172.20.10.3:8445` and WindowsNode `ONLINE` at `172.20.10.10:8445`. Mac `nc` reached Windows TCP 8445; Windows `Test-NetConnection` reached Mac TCP 8445. |

## Direct physical transfers

| Check | Result | Evidence |
| --- | --- | --- |
| Mac to Windows, 100 MiB | PASS | Deterministic source file ID `c7ae2301-a0a6-4e6b-a6ef-9ef6b7ee29a5`, share `5d7a8241-d4b7-48d5-bce4-f612585915cb`. Windows fetch reported `Transport: direct`; full destination SHA-256 matched source: `58ccc68aa3be8ed25a1f2fadb7c43a3af56367171841a0d5a27a7997eeab18e4`. |
| Windows to Mac, 100 MiB | PASS after retry | Source file ID `f52ff225-95fd-4f98-9f29-a531b3e052e3`, share `2a01e336-e3c0-4c25-915a-7ae5358d989c`. First fetch reported `CONFIGURATION: Direct peer connection failed` and created no destination. The Windows agent logged `Coordinator connection failed; retrying with verified TLS`. Windows Python and Mac Python later both received HTTP 200 from the Windows peer health endpoint with CA verification. Retrying the same share reported `Transport: direct`; destination SHA-256 matched source: `58ccc68aa3be8ed25a1f2fadb7c43a3af56367171841a0d5a27a7997eeab18e4`. Cause of the transient failure was not established. |
| Existing destination | PASS | Re-fetching Mac share to the existing Windows destination returned `CONFIGURATION: Destination already exists`; the destination's full SHA-256 remained unchanged. |
| Boundary files Mac to Windows | PASS | Direct fetches for 0, 1, 1,048,576 and 1,048,577 bytes each reported `Transport: direct`; Windows size and SHA-256 matched the deterministic Mac source for every case. Hashes, in size order: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, `bceef655b5a034911f1c3718ce056531b45ef03b4c7b1f15629e867294011a7d`, `4b7360f7dd98e7fee5f5cda734a441e9d8243bbca294333db93569bec075ea4a`, `cbf7cf21b08857224321077e9cd5e46bc4ea9df262f53bbd0829533c548cf6af`. |
| Windows agent restart and repeat export | PASS, chunk reuse unverified | Before restart, transfer `5d7a8241-d4b7-48d5-bce4-f612585915cb` had 100 completed chunks and `exported=true`. The agent restarted and listened again on TCP 8445. A subsequent export to a new Windows path had the expected 100 MiB SHA-256; `barn status` reported the same transfer ID and `transport=direct`. The journal still listed all 100 chunks. Source request logs were not captured, so this alone does not prove that all chunks were reused. |
| Missing chunk repair | PASS | In disposable Windows transfer state, `chunk-00000042.bin` was moved to a separate backup path. The next fetch restored the chunk. Read-only checks on Windows confirmed the repaired export was 104,857,600 bytes with SHA-256 `58ccc68aa3be8ed25a1f2fadb7c43a3af56367171841a0d5a27a7997eeab18e4`; the restored chunk and backup both had SHA-256 `4b7360f7dd98e7fee5f5cda734a441e9d8243bbca294333db93569bec075ea4a`. Exact peer chunk-request logs were not captured. |
| Cancel and resume control | PASS for completed journal | Windows cancelled transfer `5d7a8241-d4b7-48d5-bce4-f612585915cb`. The journal had `cancelled=true`, and an attempted fetch created no output. After `transfer resume`, the journal had `cancelled=false`; a new 104,857,600-byte export had the expected SHA-256. The CLI's exact error text on the cancelled fetch was not captured, and interruption during active download remains untested. |
| Revoked share | PASS | Mac revoked disposable 1-byte share `b8c40728-b86d-4648-af21-bf57e94cc044`. A subsequent Windows CLI fetch returned `NOT_AUTHORISED: Share is expired or revoked`; exit code was nonzero and no destination file was created. |
| Wrong recipient | PASS | MacNode attempted to fetch 0-byte share `2573db08-0fd7-4ee8-901a-50737f4009cf`, addressed to WindowsNode. The Mac CLI returned `NOT_AUTHORISED: Share is addressed to another node`; no destination file was created. |
| Expired share | PASS | Disposable 0-byte share `68a90ea6-3748-4265-9df2-780b2538f518` expired at `2026-09-29T03:09:05.718875Z`. A new Windows fetch after that timestamp returned `NOT_AUTHORISED: Share is expired or revoked`; no destination file was created. |
| Corrupt chunk repair | PASS | Windows saved a backup of `chunk-00000043.bin`, then flipped one byte. The chunk SHA-256 changed from `4b7360f7dd98e7fee5f5cda734a441e9d8243bbca294333db93569bec075ea4a` to `f4d5a759b307da1ff8b0776a18b1ae98609812f7ad68cedd41086f86eadac415`. A direct re-fetch to a new destination restored the original chunk hash and produced the expected 100 MiB file SHA-256 `58ccc68aa3be8ed25a1f2fadb7c43a3af56367171841a0d5a27a7997eeab18e4`. |
| Disposable node revocation | PASS | Windows initialized and enrolled node `9b5fa2af-a9c8-45c9-8774-73bbb88aa979` on peer port 8446. Before revocation it was `ONLINE` and directly fetched a 0-byte share, with the expected SHA-256. Mac revoked only that node. The registry then showed it `REVOKED` while MacNode and WindowsNode remained `ONLINE`. Subsequent Windows CLI fetch and heartbeat using the revoked state both returned `NOT_AUTHORISED: Node is not an active Barn member`; no new destination file was created. |
| Timed direct transfer | PASS | A fresh share `548f6a1b-b80b-437e-a382-80e06186bedd` transferred 100 MiB from Mac to Windows in 41.92 seconds. The destination was 104,857,600 bytes, its SHA-256 matched the source, and Windows `barn status` reported `transport=direct`. This is one observed run, not a throughput guarantee. |
| Interrupted transfer across coordinator and agent restart | PASS | Fresh share `99554947-7f2a-4fdc-8428-8b0cf347a4f2` was interrupted with 15 of 100 chunks in its Windows journal, `exported=false`, and no destination file. Mac coordinator and WindowsNode agent were restarted using existing state. A subsequent direct fetch exported 104,857,600 bytes with the expected SHA-256; the journal then had 100 chunks and `exported=true`. Windows chunk 0 and 14 modification times remained around 03:39 UTC, while newly fetched chunk 15 and 99 had times around 03:44 UTC, supporting physical reuse of the first 15 saved chunks. Source peer request logs were not retained. |
| Cancellation during incomplete transfer | PASS | Fresh share `ebfb9651-8afd-4476-a7d9-fd2364df4cc3` was interrupted with 42 of 100 chunks saved and `exported=false`. `transfer cancel` made a retry return `CONFIGURATION: Transfer is cancelled; resume it first`, with no destination file. `transfer resume` allowed a direct fetch to complete; the 100 MiB destination SHA-256 matched the source, and the journal ended with 100 chunks, `cancelled=false`, `exported=true`. Saved chunks 0 and 41 kept pre-resume modification times; chunk 42 onward had later times. |
| Concurrent direct transfers | PASS | Mac fetched Windows share `43898c2c-5ed6-4d97-8737-2f1054ff0c63` from 04:16:23Z to 04:17:35Z while Windows fetched Mac share `8979c11d-cbf2-45d0-80d1-0ecd3ddbcb70` from 04:16:27.221Z to 04:17:48.050Z, an overlap of about 68 seconds. Both reported direct transport, produced 104,857,600-byte destinations, and matched SHA-256 `58ccc68aa3be8ed25a1f2fadb7c43a3af56367171841a0d5a27a7997eeab18e4`. An earlier background-command attempt on Mac did not run because the shell awaited an unmatched quote; it is not counted as a concurrency test. |

## Resource snapshot

These measurements were taken after the timed transfer, not synchronously
during its peak. Windows' reported process peak is since the agent started.

| Host | Observation |
| --- | --- |
| Windows | Peer agent working set 59.0 MiB, lifetime peak working set 64.8 MiB; node state 706.1 MiB; C: free 26.71 GiB. |
| Mac | Coordinator RSS 28,128 KiB; Mac node RSS 13,856 KiB; coordinator state 244 KiB; Mac node state 402 MiB; data volume free 5.9 GiB (97% used). |

## Remaining gates

- NOT RUN: Synchronized peak memory/disk observations during concurrent transfer. Post-transfer resource snapshots and individual elapsed times are recorded above.
- NOT RUN: Public WSS relay, forced relay, blocked-direct fallback, outage/recovery, and 100 MiB relay transfers. No relay server, domain, or TLS certificate is available for this run.
- INCOMPLETE: Original install download URLs/logs for both hosts were not retained in this record. Matching installed files establish content equivalence to the TestPyPI wheel, not the historical install source.
- M1 acceptance remains pending. Existing local automated results do not replace the outstanding physical and public-relay gates.
