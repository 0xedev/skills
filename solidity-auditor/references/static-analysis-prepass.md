# Static Analysis Pre-Pass

Run automated static analysis tools before the LLM agents to provide structured context and catch pattern-based vulnerabilities that don't require deep reasoning.

This integration is based on the IRIS pattern (2405.17238) — using LLM to refine and extend static analysis results, not replace them.

## When to run

Execute as part of Turn 2 (Prepare), in parallel with bundle building. Only if the tool is installed.

## Slither integration

If `slither` is available on PATH, run:

```bash
cd {project_root} && slither . --json /tmp/slither-output.json 2>/dev/null
```

Parse the JSON output and extract:

1. **Detector findings** — organized by severity (High/Medium/Low/Info)
2. **Call graph** — which functions call which (for inter-procedural context)
3. **State variable readers/writers** — which functions read/write each storage variable
4. **Inheritance graph** — which contracts inherit from which
5. **Taint analysis** — which user-controlled inputs flow to sensitive operations

Format as a structured pre-analysis section appended to each agent bundle:

```markdown
# Static Analysis Pre-Pass (Slither)

## High-Severity Detectors
- [detector-name]: Contract.function (line N) — [description]

## State Variable Access Map
| Variable | Writers | Readers |
|----------|---------|---------|
| owner | initialize(), transferOwnership() | onlyOwner modifier |

## Call Graph (security-relevant paths)
- ExternalCall: Contract.function:L42 → IExternal.call()
- DelegateCall: Proxy.fallback:L15 → Implementation.delegatecall()

## Taint Flows
- msg.sender → Contract.function:param → storage.write
- msg.value → Contract.function → external.call{value: ...}
```

## If Slither is not available

Skip the pre-pass silently. Print a one-line note in the banner:
```
ℹ️ Slither not detected — running without static analysis pre-pass. Install for enhanced coverage: pip install slither-analyzer
```

The agents function independently without the pre-pass. It enhances, not gates.

## Aderyn integration (optional secondary)

If `aderyn` is available:

```bash
cd {project_root} && aderyn . --output /tmp/aderyn-output.json 2>/dev/null
```

Merge Aderyn findings with Slither findings, deduplicating by location.

## How agents use the pre-pass

Each agent gets the pre-pass appended to their bundle. They should:

1. **Validate** — confirm or reject each static analysis finding in their domain
2. **Extend** — use call graph and taint flows as starting points for deeper analysis
3. **Focus** — prioritize functions flagged by static analysis for manual review
4. **NOT blindly trust** — static analysis has ~90% false positive rate; every finding needs LLM validation

Agents MUST NOT copy static analysis findings verbatim into their output. They must either:
- Confirm the finding with their own analysis and cite the static tool as supporting evidence
- Reject the finding with a concrete reason (guard found, false positive pattern, etc.)
- Use the finding as a lead to discover a deeper issue the static tool couldn't detect
