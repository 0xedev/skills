# Eval Compare

Compare an audit report against ground truth findings. You will be given two files:

1. **Ground truth** — the benchmark file with known findings
2. **Report** — the audit output (`final-report.md` or `full-output.txt`)

## Steps

1. Read the ground truth file. Parse each `FINDING` line and its `description:` line.
2. Read the report file. Identify three sections:
   - **Findings** — between `## Findings` and `## Leads`
   - **Leads** — from `## Leads` to `## Proof of Concept Tests` (or end of file)
   - **PoCs** — from `## Proof of Concept Tests` to end of file (if present)
3. For each ground truth finding, determine if the report caught it. Use semantic matching — the report doesn't need to use the exact same words, but must describe the same vulnerability in the same contract/function. Classify each as:
   - **FOUND** — the vulnerability appears in the Findings section. The report identifies the same contract, the same function or entry point, and the same root cause (even if described differently).
   - **LEAD** — the vulnerability appears only in the Leads section with the same criteria above.
   - **MISSED** — not present in either section.
4. For each FOUND finding, check if a PoC was generated for it (match by finding number or contract.function).
5. Count **false positives**: findings in the report that don't match ANY ground truth entry. Classify as FP-HIGH, FP-MEDIUM, FP-LOW based on the report's confidence score.
6. Classify each finding by **bug category** for per-category analysis:
   - `access-control`: permission, auth, role, initialization, proxy
   - `math-precision`: rounding, overflow, truncation, decimals, division
   - `reentrancy`: reentrancy, callback, hook, cross-function
   - `input-validation`: missing check, validation, require, boundary
   - `token-handling`: erc20, transfer, approval, fee-on-transfer, permit
   - `state-management`: state, ordering, race, stale, coupling
   - `economic`: flash loan, oracle, MEV, sandwich, incentive
   - `cross-chain`: bridge, message, chain, relay, nonce
   - `dos`: gas, revert, block, loop, grief
   - `other`: everything else

## Output

Write `summary.md` to the run directory with this exact format:

```
## Eval Results

| Metric | Value |
|--------|-------|
| Recall (findings) | {found} / {total} ({pct}%) |
| Recall+Leads | {found+leads} / {total} ({pct}%) |
| In leads only | {leads} |
| Missed | {missed} |
| High recall | {high_found} / {high_total} ({pct}%) |
| Medium recall | {med_found} / {med_total} ({pct}%) |
| Reported findings | {count from report} |
| False positives | {fp_count} (H:{fp_high} M:{fp_med} L:{fp_low}) |
| Precision | {found} / ({found} + {fp_count}) ({pct}%) |
| F1 Score | {f1:.1f}% |
| PoCs generated | {poc_count} / {found} confirmed |
| PoCs proven | {poc_proven} / {poc_count} attempted |

### Per-Category Breakdown

| Category | Found | Lead | Missed | Total | Recall |
|----------|-------|------|--------|-------|--------|
| access-control | {n} | {n} | {n} | {n} | {pct}% |
| math-precision | {n} | {n} | {n} | {n} | {pct}% |
| input-validation | {n} | {n} | {n} | {n} | {pct}% |
| token-handling | {n} | {n} | {n} | {n} | {pct}% |
| state-management | {n} | {n} | {n} | {n} | {pct}% |
| economic | {n} | {n} | {n} | {n} | {pct}% |
| cross-chain | {n} | {n} | {n} | {n} | {pct}% |
| other | {n} | {n} | {n} | {n} | {pct}% |

### Per-Finding Breakdown

| Status | Severity | ID | Contract.Function | Bug Class | Category | PoC |
|--------|----------|----|-------------------|-----------|----------|-----|
| FOUND | High | H-1 | Contract.function | bug-class | category | ✅/❌/— |
| LEAD | Medium | M-2 | Contract.function | bug-class | category | — |
| MISSED | Medium | M-3 | Contract.function | bug-class | category | — |

### False Positives

| Confidence | Contract.Function | Bug Class | Why FP |
|------------|-------------------|-----------|--------|
| [85] | Contract.function | bug-class | brief explanation |

### Regression Check

[Compare against previous run in same benchmark directory if one exists. Flag:]
- New misses (found before, missed now)
- New finds (missed before, found now)
- Confidence changes > 10 points
- Category-level recall changes > 20%
```

## Rules

- Match semantically, not by keyword grep. "Fee bypass because low-level call to placeholder succeeds" matches "native-erc20-confusion" even without those exact words.
- A finding in the Leads section is NOT a finding — it's a lead. Don't count it toward recall.
- If the report describes the same root cause but attributes it to a different function in the same contract, still count it as FOUND.
- If the report merges two ground-truth findings into one reported finding, count both as FOUND.
- F1 = 2 × (Precision × Recall) / (Precision + Recall). Use finding-level recall (not recall+leads).
- For regression checks: read the most recent `summary.md` in sibling directories of the same benchmark. If none exists, skip the regression section.
