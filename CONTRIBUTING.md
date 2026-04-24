# Contributing to Pashov Audit Group Skills (Enhanced Fork)

## Pull Request Process

1. Fork the repo and create a branch from `main`.
2. Make your changes — attack vectors, agent prompts, report formatting, or documentation.
3. Ensure your branch is up to date with `main` before opening a PR.
4. Do not edit `VERSION` — it is bumped automatically on merge via CI.
5. Fill in the PR template. A maintainer will review within 5 business days.

### PR checklist

- [ ] No API keys, tokens, or sensitive data
- [ ] No fabricated examples — outputs must reflect real model responses
- [ ] Skill works with Claude Code CLI, VS Code, and Cursor
- [ ] New attack vectors follow `**N. Title**` + `**D:**` / `**FP:**` format
- [ ] New agents output structured blocks per `shared-rules.md`
- [ ] Eval benchmarks updated if adding new vulnerability categories

## What to Contribute

- **Attack vectors** — add new vectors to `solidity-auditor/references/attack-vectors/attack-vectors.md` following the existing `**D:**` / `**FP:**` format. Number sequentially from the last entry.
- **Agent prompts** — improve triage accuracy, reduce false positives, tighten output format.
- **Critic agent tuning** — improve the scoring formula, add new validation heuristics, reduce false positive pass-through rate.
- **PoC templates** — add common exploit patterns to the PoC generator's strategy library.
- **Report formatting** — improve the output structure or fix template issues.
- **Eval benchmarks** — add new ground truth files from public audit contests (Sherlock, Code4rena, Immunefi). Must include `repo_url`, findings with `id`, `severity`, `contract`, `function`, `bug_class`, and `description`.
- **Static analysis integration** — improve Slither/Aderyn output parsing and agent context formatting.
- **Bug fixes** — if the skill produces incorrect output, open an issue or PR with a fix.

## Adding a New Agent

1. Create `solidity-auditor/references/hacking-agents/your-agent.md`
2. Follow the structure of existing agents: role description → attack surfaces → output fields
3. Include `shared-rules.md` in the agent's bundle definition
4. Add the bundle to the orchestration table in `SKILL.md`
5. Update the agent count references in README and SKILL.md

## Adding Eval Benchmarks

1. Create `solidity-auditor/evals/benchmarks/{name}.md` with YAML frontmatter
2. Include `repo_url`, optional `repo_ref` and `contracts_dir`
3. List ground truth findings in the standard format (see existing benchmarks)
4. Add the benchmark name to the runner's sequential order in `runner.md`
5. Run the eval locally and verify the comparison produces sensible results

## Reporting Bugs

Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) issue template and include:

- Which skill is affected and how you invoked it.
- The Claude model used (e.g., claude-sonnet-4-6).
- The input you gave and the output you got.
- What you expected instead.
