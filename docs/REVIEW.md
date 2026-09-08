# Review record

## External second opinion

Attempted the requested Codex and Antigravity CLI reviews against 1,238 lines of new portable source/test diff. `codex` returned command not found; `agy` was also absent, including after adding its documented user installation path. No external model review result exists. The independent research agents reviewed upstream architecture, not the final code diff.

For a future configured development environment, the Codex CLI installation command is `npm i -g @openai/codex`; Antigravity is available from [its official site](https://antigravity.google). These tools also require their own working account/authentication. No installation or account setup is needed to run the included tests.

## Agentic Actions audit

Analyzed the one root workflow in this project: `portable-checks.yml`. No AI action steps, local composite actions, reusable workflow calls, or AI CLI invocations were found. The workflow uses read-only repository access, disables persisted checkout credentials, pins checkout to the verified v4.2.2 commit, and runs fixed local commands. No untrusted event text is interpolated into shell code. This is a static scope result, not a claim that GitHub execution passed.

Also inspected the separate upstream workflow roots: four in PhoneVR and one in Desktop+. No AI action/CLI invocation or local/reusable workflow indirection was identified. The agentic-actions-specific audit therefore ends at its no-AI boundary; it is not a general security certification of those upstream pipelines or their third-party dependencies.

## False-positive check: unauthenticated pose spoofing

Claim considered: a sender without the pairing key can submit arbitrary UDP pose coordinates which become the receiver's accepted tracking state.

Threat model: a party able to reach the bound UDP socket, without the random 32-byte key. Default bind is loopback; network reachability requires an explicit bind setting. This is a diagnostic process with no SteamVR or Windows input sink.

Trace: `recvfrom` -> exact packet length -> HMAC comparison -> magic/version/reserved fields -> finite/range/quaternion validation -> expected session -> processing age -> sequence and timestamp checks -> accepted state. The HMAC covers the complete 68-byte body and is compared before fields are interpreted. The caller does not have an alternate unauthenticated path.

Executable evidence: the tamper-every-byte and wrong-key test, session gate tests, replay tests and actual loopback invalid-traffic watchdog case pass. An unkeyed altered packet reaches the decoder but does not reach state mutation. A key holder is the authenticated sender and is outside this claim; a stolen key or reused session across receiver restarts is not covered by the rejection result.

All standard verification phases were applied: caller/data-flow tracing, attacker control, impact, test proof, contrary-evidence review and gate review. Bounds are fixed at 100 bytes; parsing uses managed Python bytes/struct. There is no concurrent mutation or secondary authorization bypass. The false-positive checklist's validation, branch, source-trust, API bounds, concurrency and concrete-impact checks agree with this trace.

Verdict: **FALSE POSITIVE for the specific unauthenticated accepted-pose claim.** The reachability gate to accepted state fails. This does not establish encryption, full network freshness, or production readiness. Counts: 0 true positives, 1 false positive for this checked security claim.

## Confirmed robustness correction

Windows `recvfrom` can raise WSAEMSGSIZE when a UDP datagram exceeds the buffer; Linux commonly returns truncated data. The original receiver only caught BlockingIOError, so the Windows error could stop the diagnostic process before protocol rejection. [Microsoft contract](https://learn.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-recvfrom).

A regression modeled that exact Windows error while using a real loopback socket and verified a subsequent valid packet. It failed before the fix, then passed after the receiver began dropping WSAEMSGSIZE/EMSGSIZE within its bounded receive loop. Other socket failures still propagate. This is an error-handling correction; Windows execution and any claim of code execution or privilege escalation remain unestablished.
