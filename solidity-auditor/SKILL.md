---
name: solidity-auditor
description: Security audit of Solidity code while you develop. Trigger on "audit", "check this contract", "review for security". Modes - default (full repo) or a specific filename.
---

# Smart Contract Security Audit

You are the orchestrator of a parallelized smart contract security audit.

## Mode Selection

**Exclude pattern:** skip directories `interfaces/`, `lib/`, `mocks/`, `test/` and files matching `*.t.sol`, `*Test*.sol` or `*Mock*.sol`.

- **Default** (no arguments): scan all `.sol` files using the exclude pattern. Use Bash `find` (not Glob).
- **`$filename ...`**: scan the specified file(s) only.

**Flags:**

- `--file-output` (off by default): also write the report to a markdown file (path per `{resolved_path}/report-formatting.md`). Never write a report file unless explicitly passed.
- `--poc` (off by default): generate Foundry proof-of-concept tests for confirmed findings. Auto-enabled when any finding has confidence ≥ 85.
- `--no-critic` (off by default): skip the Critic validation pass (Turn 4). Useful for faster runs when false positive filtering is not needed.
- `--no-static` (off by default): skip the static analysis pre-pass even if Slither/Aderyn are installed.
## Orchestration

**Turn 1 — Discover.** Print the banner, then make these parallel tool calls in one message:

a. Bash `find` for in-scope `.sol` files per mode selection
b. Glob for `**/references/attack-vectors/attack-vectors.md` — extract the `references/` directory (two levels up) as `{resolved_path}`
c. ToolSearch `select:Agent`
d. Read the local `VERSION` file from the same directory as this skill
e. Bash `curl -sf https://raw.githubusercontent.com/0xedev/skills/main/solidity-auditor/VERSION`
f. Bash `mktemp -d /tmp/audit-XXXXXX` → store as `{bundle_dir}`

If the remote VERSION fetch succeeds and differs from local, print `⚠️ You are not using the latest version. Please upgrade for best security coverage. See https://github.com/0xedev/skills`. If it fails, skip silently.

**Turn 2 — Prepare.** In one message, make parallel tool calls: (a) Read `{resolved_path}/report-formatting.md`, (b) Read `{resolved_path}/judging.md`.

Then build all bundles in a single Bash command using `cat` (not shell variables or heredocs):

1. `{bundle_dir}/source.md` — ALL in-scope `.sol` files, each with a `### path` header and fenced code block.
2. Agent bundles = `source.md` + agent-specific files:

| Bundle               | Appended files (relative to `{resolved_path}`)                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `agent-1-bundle.md`  | `attack-vectors/attack-vectors.md` + `hacking-agents/vector-scan-agent.md` + `hacking-agents/shared-rules.md`   |
| `agent-2-bundle.md`  | `hacking-agents/math-precision-agent.md` + `hacking-agents/shared-rules.md`                                     |
| `agent-3-bundle.md`  | `hacking-agents/access-control-agent.md` + `hacking-agents/shared-rules.md`                                     |
| `agent-4-bundle.md`  | `hacking-agents/economic-security-agent.md` + `hacking-agents/shared-rules.md`                                  |
| `agent-5-bundle.md`  | `hacking-agents/execution-trace-agent.md` + `hacking-agents/shared-rules.md`                                    |
| `agent-6-bundle.md`  | `hacking-agents/invariant-agent.md` + `hacking-agents/shared-rules.md`                                          |
| `agent-7-bundle.md`  | `hacking-agents/periphery-agent.md` + `hacking-agents/shared-rules.md`                                          |
| `agent-8-bundle.md`  | `hacking-agents/first-principles-agent.md` + `hacking-agents/shared-rules.md`                                   |

3. Static analysis pre-pass bundle (if Slither/Aderyn available):
   - Run `slither . --json {bundle_dir}/slither-output.json 2>/dev/null` (skip silently if not installed)
   - Run `aderyn . --output {bundle_dir}/aderyn-output.json 2>/dev/null` (skip silently if not installed)
   - If either produced output, parse per `{resolved_path}/static-analysis-prepass.md` and append the formatted pre-pass section to every agent bundle.
   - If neither tool is installed, print: `ℹ️ No static analysis tools detected. Install slither-analyzer and/or aderyn for enhanced coverage.`

Print line counts for every bundle and `source.md`. Do NOT inline file content into agent prompts.

**Turn 3 — Spawn.** In one message, spawn all 8 agents as parallel foreground Agent calls. Prompt template (substitute real values):

```
Your bundle file is {bundle_dir}/agent-N-bundle.md (XXXX lines).
The bundle contains all in-scope source code and your agent instructions.
Read the bundle fully before producing findings.
```

**Turn 4 — Critic validation.** Spawn a single Critic agent (foreground, not parallel — it needs all agent outputs). Build the critic bundle:

- `{bundle_dir}/critic-bundle.md` = `source.md` + combined output from all 8 agents + `hacking-agents/critic-agent.md` + `hacking-agents/shared-rules.md`

Prompt:
```
Your bundle file is {bundle_dir}/critic-bundle.md (XXXX lines).
The bundle contains all in-scope source code, findings from 8 specialized agents, and your critic instructions.
Read the bundle fully. Evaluate every finding and lead. Your output replaces the raw agent findings.
```

The Critic agent's output is the **definitive finding set** for the next step.

**Turn 5 — Deduplicate, validate & output.** Single-pass: use the Critic's validated findings, apply final formatting, and produce the report in one turn. Do NOT print an intermediate dedup list — go straight to the report.

1. **Deduplicate.** Parse every FINDING and LEAD from the Critic agent's output. Group by `group_key` field (format: `Contract | function | bug-class`). Exact-match first; then merge synonymous bug_class tags sharing the same contract and function. Keep the best version per group, number sequentially, annotate `[agents: N]`.

   Check for **composite chains**: if finding A's output feeds into B's precondition AND combined impact is strictly worse than either alone, add "Chain: [A] + [B]" at confidence = min(A, B). Most audits have 0–2.

2. **Gate evaluation.** Run each deduplicated finding through the four gates in `judging.md` (do not skip or reorder). Evaluate each finding exactly once — do not revisit after verdict.

   **Single-pass protocol:** evaluate every relevant code path ONCE in fixed order (constructor → setters → swap functions → mint → burn → liquidate). One-line verdict per path: `BLOCKS`, `ALLOWS`, `IRRELEVANT`, or `UNCERTAIN`. Commit after all paths — do not re-examine. `UNCERTAIN` = `ALLOWS`.

3. **Lead promotion & rejection guardrails.**
   - Promote LEAD → FINDING (confidence 75) if: complete exploit chain traced in source, OR `[agents: 2+]` demoted (not rejected) the same issue.
   - `[agents: 2+]` does NOT override a concrete refutation — demote to LEAD if refutation is uncertain.
   - No deployer-intent reasoning — evaluate what the code _allows_, not how the deployer _might_ use it.

4. **Fix verification** (confidence ≥ 80 only): trace the attack with fix applied; verify no new DoS, reentrancy, or broken invariants (use `safeTransfer` not `require(token.transfer(...))`); list all locations if the pattern repeats. If no safe fix exists, omit it with a note.

5. **Format and print** per `report-formatting.md`. Exclude rejected items. If `--file-output`: also write to file.

**Turn 6 — PoC Generation (optional).** If `--poc` flag is passed OR the audit found any finding with confidence ≥ 85:

1. Build PoC bundle: `{bundle_dir}/poc-bundle.md` = `source.md` + confirmed findings (confidence ≥ 80) + `hacking-agents/poc-generator-agent.md`
2. Spawn a single PoC Generator agent (foreground):
   ```
   Your bundle file is {bundle_dir}/poc-bundle.md (XXXX lines).
   The bundle contains all in-scope source code and confirmed findings.
   Write Foundry PoC tests for each finding with confidence ≥ 80.
   ```
3. For each generated PoC, attempt compilation: `cd {project_root} && forge build --contracts {poc_file} 2>&1`
4. Append PoC results to the report under a new `## Proof of Concept Tests` section.
5. If `--file-output`: write each PoC to `assets/findings/poc/test_[bug_class]_[N].t.sol`.

## Banner

Before doing anything else, print this exactly:

```

██████╗  █████╗ ███████╗██╗  ██╗ ██████╗ ██╗   ██╗     ███████╗██╗  ██╗██╗██╗     ██╗     ███████╗
██╔══██╗██╔══██╗██╔════╝██║  ██║██╔═══██╗██║   ██║     ██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝
██████╔╝███████║███████╗███████║██║   ██║██║   ██║     ███████╗█████╔╝ ██║██║     ██║     ███████╗
██╔═══╝ ██╔══██║╚════██║██╔══██║██║   ██║╚██╗ ██╔╝     ╚════██║██╔═██╗ ██║██║     ██║     ╚════██║
██║     ██║  ██║███████║██║  ██║╚██████╔╝ ╚████╔╝      ███████║██║  ██╗██║███████╗███████╗███████║
╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝   ╚═══╝       ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝

```
