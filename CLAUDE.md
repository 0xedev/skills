# CLAUDE.md

Instructions for Claude when contributing to this repository.

## What This Repo Is

A library of Claude AI skills for Solidity security auditing. Enhanced fork of [pashov/skills](https://github.com/pashov/skills) with research-backed improvements.

## Structure

```
solidity-auditor/   # Security review with 8 hacking agents + critic + PoC generator
x-ray/              # Pre-audit scan with threat model, invariants, call-graph profiling
CLAUDE.md           # This file (read by Claude Code)
```

## Key Enhancements (vs upstream)

1. **Critic Agent** — adversarial meta-agent that re-evaluates and filters findings
2. **PoC Generator** — writes Foundry tests proving confirmed vulnerabilities
3. **Static Analysis Pre-Pass** — Slither/Aderyn integration for structured context
4. **20 New Attack Vectors** — covering 2024-2026 exploit patterns (267-286)
5. **Enhanced Eval System** — precision/recall/F1, per-category tracking, regression detection
6. **X-Ray Call-Graph Profiling** — inter-procedural context for invariant synthesis

## Rules

- One skill, one purpose.
- No fabricated examples — outputs must reflect real model responses.
- No secrets, API keys, or personal data.
- New attack vectors must follow the `**D:**` / `**FP:**` format exactly.
- New agents must output structured blocks per `shared-rules.md`.
- Critic agent output replaces raw agent output — it is the definitive finding set.
- PoC generator only attempts findings with confidence ≥ 80.
- Static analysis pre-pass is optional — all agents function without it.
