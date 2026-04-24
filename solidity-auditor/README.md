# Solidity Auditor

A security agent with a simple mission — findings in minutes, not weeks.

Built for:

- **Solidity devs** who want a security check before every commit
- **Security researchers** looking for fast wins before a manual review
- **Just about anyone** who wants an extra pair of eyes.

Not a substitute for a formal audit — but the check you should never skip.

## Demo

_Portrayed below: finding multiple high-confidence vulnerabilities in a codebase_

![Running solidity-auditor in terminal](../static/skill_pag.gif)

## What's New (Enhanced Fork)

| Feature | Description | Research Basis |
|---------|-------------|----------------|
| 🛡️ **Critic Agent** | Adversarial 9th agent that re-evaluates all findings, eliminates FPs | [GPTLens](https://arxiv.org/abs/2310.01152), [iAudit](https://arxiv.org/abs/2403.16073) |
| 🔬 **PoC Generator** | Writes Foundry tests proving confirmed vulnerabilities | [SAILOR](https://arxiv.org/abs/2604.06506) |
| 🔍 **Static Pre-Pass** | Optional Slither/Aderyn integration for structured context | [IRIS](https://arxiv.org/abs/2405.17238) |
| 🧬 **20 New Vectors** | L2, EIP-7702, EIP-4844, restaking, hooks, intents (267-286) | 2024-2026 exploit analysis |
| 📊 **Enhanced Evals** | Precision/F1/per-category tracking/regression detection | [FORGE](https://arxiv.org/abs/2506.18795) |

## Usage

```
Install https://github.com/0xedev/skills/ and run solidity auditor on the codebase
```

```
run solidity auditor on *specified files*
run solidity auditor with --poc on the codebase
```

```
update skill to latest version
```

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--file-output` | off | Write report to markdown file |
| `--poc` | off | Generate Foundry PoC tests (auto-enabled for confidence ≥ 85) |
| `--no-critic` | off | Skip Critic validation pass for faster runs |
| `--no-static` | off | Skip static analysis pre-pass |

## How It Works

```
Turn 1: Discover    → Find .sol files, resolve paths, check version
Turn 2: Prepare     → Build source + agent bundles (+ optional Slither pre-pass)
Turn 3: Spawn       → 8 specialized agents run in parallel
Turn 4: Critique    → Critic agent adversarially validates all findings  ← NEW
Turn 5: Report      → Deduplicate, gate-evaluate, format final report
Turn 6: PoC         → Generate Foundry tests for confirmed findings     ← NEW
```

### Agents

| # | Agent | Specialty |
|---|-------|-----------|
| 1 | Vector Scan | Known pattern matching against 286 vectors |
| 2 | Math Precision | Integer arithmetic, rounding, overflow |
| 3 | Access Control | Permission models, privilege escalation |
| 4 | Economic Security | External deps, token behavior, value flows |
| 5 | Execution Trace | Execution flow, encoding, state transitions |
| 6 | Invariant | Conservation laws, state couplings |
| 7 | Periphery | Libraries, helpers, base contracts |
| 8 | First Principles | Implicit assumption violation |
| 🛡️ | **Critic** | Adversarial re-evaluation of all findings |
| 🔬 | **PoC Generator** | Foundry test generation for confirmed bugs |

## Tips

- **Target hot contracts.** Rather than scanning an entire repo, point the tool at the 2-5 contracts you're actively changing. Smaller scope means denser context for each agent and higher-signal findings.
- **Run more than once.** LLM output is non-deterministic — each run can surface different vulnerabilities. Two or three passes over the same code often catch things a single pass misses.
- **Install Slither.** `pip install slither-analyzer` gives the agents structured call graphs and taint flows as additional context, significantly improving inter-procedural analysis.
- **Use `--poc` for high-confidence findings.** The PoC generator turns audit findings into executable evidence — essential for communicating vulnerabilities to dev teams.
