# X-Ray

Know your protocol before auditors do.

Built for:

- **Protocol teams** preparing for an audit — fix the obvious so auditors can focus on what matters
- **Security researchers** starting a new engagement — get the full picture in minutes

Not a vulnerability scanner — it's the briefing you read before opening the first file.

## What You Get

One command produces:

| Output | What's Inside |
|--------|--------------|
| `x-ray.md` | Protocol overview, threat model, test gaps, git history, readiness verdict |
| `entry-points.md` | Every state-changing function classified by access level with call chains |
| `invariants.md` | Full invariant map — enforced guards, single-contract invariants, cross-contract trust assumptions, and higher-order economic properties |
| `architecture.svg` | Visual architecture diagram — contracts, actors, trust boundaries |

## What's New (Enhanced Fork)

- **Call-graph profiling** — optional Slither-powered inter-procedural context extraction. Maps callers, callees, and shared state per function. Enhances invariant synthesis and attack surface identification. Based on [CPRVul](https://arxiv.org/abs/2602.06751).
- **Static analysis integration** — Slither findings feed into threat model as corroborating evidence, without requiring agents to re-discover pattern-based issues.

## Demo

_Part of an X-Ray report generation shown below_

![Running x-ray in terminal](../static/x_ray.gif)

## Usage

```
Install latest https://github.com/0xedev/skills/ and run x-ray on the codebase
```

## Tips

- **Start with the verdict.** The report ends with a tier (FORTIFIED → EXPOSED) and 3-5 action items. If you only read one section, read that.
- **Use entry-points.md as your map.** Start with permissionless functions — those are the highest-risk surface.
- **Check the action items.** The final section highlights concrete next steps — whether you're preparing for an audit or starting one.
- **Install Slither for deeper analysis.** `pip install slither-analyzer` enables call-graph profiling and state variable mapping, significantly improving invariant synthesis quality.
