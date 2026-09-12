# Review record

## External second opinion

Attempted the requested Codex and Antigravity CLI reviews against 1,238 lines of new portable source/test diff. `codex` returned command not found; `agy` was also absent, including after adding its documented user installation path. No external model review result exists. The independent research agents reviewed upstream architecture, not the final code diff.

For a future configured development environment, the Codex CLI installation command is `npm i -g @openai/codex`; Antigravity is available from [its official site](https://antigravity.google). These tools also require their own working account/authentication. No installation or account setup is needed to run the included tests.

## Agentic Actions audit

Analyzed all nine project workflows, including `android-phonexr.yml`, `android-phonexr-tests.yml` and `windows-phonexr.yml`, plus the earlier six: `portable-checks.yml`, `windows-protocol.yml`, `windows-baseline.yml`, `android-baseline.yml`, `windows-streamer.yml`, and `android-smoke.yml`. No AI action steps, local composite actions, reusable workflow calls, or AI CLI invocations were found. The workflow uses read-only repository access, disables persisted checkout credentials, pins checkout to the verified v4.2.2 commit, and runs fixed local commands. No untrusted event text is interpolated into shell code. This is a static scope result, not a general dependency audit. Actual CI results are linked in STATUS.md. The emulator workflow invokes a pinned Android emulator action and grants the ephemeral runner user access to its KVM device; it contains no AI integration.

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

A regression modeled that exact Windows error while using a real loopback socket and verified a subsequent valid packet. It failed before the fix, then passed after the receiver began dropping WSAEMSGSIZE/EMSGSIZE within its bounded receive loop. Other socket failures still propagate. This is an error-handling correction; The 15-test suite subsequently passed on Windows Server 2022 in [run 34193762726](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34193762726). The oversized-error case remains explicitly injected for determinism; it is not a privilege-escalation finding.

## Native integration review, 2026-09-09

The requested external Codex/Antigravity review was attempted again on the new hand sender/receiver changes. Both executables remain unavailable (`FileNotFoundError`), so no external second-opinion verdict is claimed. The checks below are local source review and executable regressions.

Confirmed corrections:

- The upstream Android Gradle task set `ignoreFailures = true`. Run 34314584153 reported success despite a failed ALVR screenshot test. Its green status is not accepted as evidence that all tests passed. The derivative now sets false, selects the four PhoneXR component tests explicitly, and independently checks JUnit XML for all four successful, unskipped results. The upstream screenshot test needs a separate streaming setup and is outside this suite.
- Protocol v1 derived the GCM nonce from a fixed prefix and persisted sequence. Clearing Android app data and reusing the same pairing could repeat those nonces. Protocol v2 authenticates a fresh random 96-bit nonce per packet instead; durable sequence blocks still provide restart-safe replay progression. Clearing app data requires a fresh PC session. This is a cryptographic lifecycle correction, not evidence of an observed exploit.
- The original bridge pinned the sender's full UDP endpoint. An authenticated Android app restart could change source port and lose connectivity. The receiver now retains the IP restriction and authenticates the new port before updating the endpoint; valid and tampered reconnect regressions pass.
- AR fallback is explicitly published before availability checks on resume, preventing a prior pause from leaving unsupported-AR devices stuck in the AR freeze state. Setup controls now scroll on short/landscape displays.

### False-positive check: unkeyed hand-state injection

Claim: a network sender without the pairing key can change accepted hand coordinates and drive the Windows input path.

Trace: bounded UDP receive -> paired-IP check -> header/length/session -> sequence precheck -> AES-GCM authentication over header and ciphertext -> numeric, age, identity and landmark schema gates -> receiver state update -> current panel snapshot and explicit input-enable gates -> ContactEngine/Manipulator -> checked Windows sink or revision-checked Desktop+ command. The sequence and peer are updated only after successful authenticated decoding. No unauthenticated raw-coordinate branch was found in this path.

Evidence: altered ciphertext fails with InvalidTag and leaves the accepted sequence unchanged; session mismatch and replay fail; a changed source port with invalid authentication cannot replace the peer. These regressions exercise the receiver/caller boundary. Sink tests model touch failures without injecting physical Windows input.

Verdict: FALSE POSITIVE for this specific unkeyed accepted-hand-state claim under the stated no-key threat model. This does not cover a stolen pairing URI, malicious authenticated phone, compromised PC, cryptographic-library compromise, or absolute network freshness. The relative timestamp filter cannot establish the true age of the first received packet. There is no independent clock synchronization/challenge protocol, so this build is not certified for hostile-network freshness.

The native snapshot regression includes the actual production header with narrow JNI/Cardboard test doubles. It checks capture-time preservation, stale/future-time rejection, frozen rendering, recovery, invalid pose rejection and Cardboard fallback. It does not emulate ARCore, ALVR prediction, GPU rendering or physical tracking.

### Native dependency loading defects caught by strict tests

Run 34363342655 executed four selected tests and correctly failed: OpenCV attempted to load `libopencv_java4100.so`, while the official Android AAR contains `libopencv_java4.so`; MediaPipe 0.10.14 contains ARM64, ARMv7 and x86 libraries but no x86_64 library. The production OpenCV call now uses its actual Android library name. The component fixture runs the same production Java sources/model on API30 x86, and the arm64 APK verifier additionally requires OpenCV, MediaPipe, ARCore and the exact model. This is an explicit change of component-test architecture, not a claim that MediaPipe works on x86_64 or that the full headset runtime was emulated.

Direct AAR archive inspection established those filenames/ABIs. Previous compile-only PhoneXR APKs must not be used as evidence of working hand inference because the OpenCV loader defect also affected the phone path.

The corrected component fixture subsequently passed all four tests in [run 34365142111](https://github.com/guy-halevy/AR-PC-2-phone/actions/runs/34365142111). The independent XML gate listed each expected method and accepted none as skipped. This verifies the model/geometry/encryption/clock components on Android 11 x86, not physical hand detection accuracy or the arm64 headset runtime.

## Stereo rendering and companion completion, 2026-09-12

The renderer now projects up to two hand skeletons into the two matching ALVR eye views before Cardboard distortion, with a 150 ms freshness gate, explicit clearing on tracking loss and a setup toggle. A GPU fixture executes the actual renderer against EGL/GLES3 textures and checks pixels, stereo disparity, stale suppression and restored GL state. Its result is tracked in STATUS.md.

Independent source review confirmed the upstream `alvr_get_frame` caller allocated one view structure while the pinned Rust API writes two. The derivative now allocates two. The adjacent write through a Cardboard parameter pointer after its destruction was removed. These are concrete memory-lifetime corrections; physical exploitation was not attempted.

Native lifecycle repairs stop/join the input worker before teardown, serialize lifecycle/configuration access, release the JNI Activity global reference, and run GPU teardown on the GL thread before surface pause. A harness extracts the prepared teardown functions and checks repeated live-worker destruction and EGL guards under sanitizers in CI. Local sanitizer execution is limited by this sandbox's process-inspection restrictions; that limitation is not counted as a test pass.

The Windows companion exposes local pairing, input controls and launch buttons. The per-user installer makes no automatic firewall changes and does not initialize input during install tests. Its first CI build passed install, GUI self-test and uninstall; the extended ALVR bundle is tracked separately in STATUS.md. SteamVR remains a separately installed runtime.
