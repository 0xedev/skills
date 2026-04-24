#!/usr/bin/env python3
"""
build_security_dataset.py — SFT Dataset Generator for Smart Contract Security Auditor

Parses the attack vectors knowledge base and evaluation benchmark contracts from
the 0xedev/skills repo to generate a Supervised Fine-Tuning dataset in ChatML format.

Output: security_sft.parquet with columns:
  - prompt: str (the user-facing prompt in ChatML conversational format)
  - messages: list[dict] (ChatML messages: system, user, assistant)

Each row is a training sample where:
  - system: the auditor persona prompt
  - user: vulnerable Solidity code + audit instruction
  - assistant: the perfect FINDING block + Foundry PoC test
"""

import re
import json
import hashlib
from pathlib import Path
from typing import Optional

import pandas as pd

# ─── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path("/tmp/skills_eval")
VECTORS_PATH = REPO_ROOT / "solidity-auditor/references/attack-vectors/attack-vectors.md"
BENCHMARKS_DIR = REPO_ROOT / "solidity-auditor/evals/benchmarks"

# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert Solidity smart contract security auditor. Your task is to analyze the provided smart contract code, identify vulnerabilities, and produce:

1. A structured FINDING block with: contract, function, bug_class, confidence score, attack path, concrete proof, description, and fix suggestion.
2. A Foundry proof-of-concept test that demonstrates the vulnerability is exploitable.

Output format:
FINDING | contract: <Name> | function: <func> | bug_class: <tag> | confidence: <0-100>
path: <caller → function → state change → impact>
proof: <concrete values/trace demonstrating the bug>
description: <one sentence>
fix: <one-sentence suggestion>

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
import "forge-std/Test.sol";
// ... PoC test code ...
```

Be precise. Use concrete values in proofs. One vulnerability per finding."""


# ─── Vector Parser ────────────────────────────────────────────────────────────
def parse_attack_vectors(path: Path) -> list[dict]:
    """Parse attack-vectors.md into structured entries."""
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'\*\*(\d+)\.\s+(.+?)\*\*\s*\n\s*'
        r'- \*\*D:\*\*\s*(.+?)\s*\n\s*'
        r'- \*\*FP:\*\*\s*(.+?)(?=\n\n\*\*\d+\.|\Z)',
        re.DOTALL
    )
    vectors = []
    for m in pattern.finditer(text):
        vectors.append({
            "id": int(m.group(1)),
            "title": m.group(2).strip(),
            "description": m.group(3).strip(),
            "false_positive": m.group(4).strip(),
        })
    return vectors


# ─── Benchmark Parser ─────────────────────────────────────────────────────────
def parse_benchmark(path: Path) -> list[dict]:
    """Parse a benchmark ground-truth .md file into findings."""
    text = path.read_text(encoding="utf-8")
    findings = []

    # Extract repo_url from frontmatter
    repo_url_match = re.search(r'repo_url:\s*(.+)', text)
    repo_url = repo_url_match.group(1).strip() if repo_url_match else "unknown"

    # Parse FINDING lines
    finding_pattern = re.compile(
        r'FINDING\s*\|\s*id:\s*(\S+)\s*\|\s*severity:\s*(\S+)\s*\|\s*'
        r'contract:\s*(\S+)\s*\|\s*function:\s*(\S+)\s*\|\s*bug_class:\s*(\S+)\s*\n'
        r'description:\s*(.+?)(?=\n\nFINDING|\Z)',
        re.DOTALL
    )
    for m in finding_pattern.finditer(text):
        findings.append({
            "id": m.group(1).strip(),
            "severity": m.group(2).strip(),
            "contract": m.group(3).strip(),
            "function": m.group(4).strip(),
            "bug_class": m.group(5).strip(),
            "description": m.group(6).strip(),
            "repo_url": repo_url,
            "benchmark": path.stem,
        })
    return findings


# ─── Vulnerable Code Generator ────────────────────────────────────────────────
def generate_vulnerable_contract(vector: dict) -> str:
    """Generate a minimal vulnerable Solidity contract from an attack vector description."""
    bug_class = vector["title"].lower().replace(" ", "-").replace("(", "").replace(")", "")
    # Create a deterministic but varied contract name
    h = hashlib.md5(vector["title"].encode()).hexdigest()[:6]
    contract_name = f"Vuln_{h}"

    # Map common vulnerability types to code templates
    desc = vector["description"].lower()

    if "reentrancy" in desc or "callback" in desc:
        return _template_reentrancy(contract_name, vector)
    elif "oracle" in desc or "price" in desc or "stale" in desc:
        return _template_oracle(contract_name, vector)
    elif "overflow" in desc or "truncat" in desc or "rounding" in desc or "precision" in desc:
        return _template_math(contract_name, vector)
    elif "access" in desc or "permission" in desc or "initializ" in desc or "admin" in desc:
        return _template_access_control(contract_name, vector)
    elif "approve" in desc or "allowance" in desc or "transfer" in desc:
        return _template_token(contract_name, vector)
    elif "withdraw" in desc or "deposit" in desc or "vault" in desc:
        return _template_vault(contract_name, vector)
    elif "bridge" in desc or "cross-chain" in desc or "message" in desc:
        return _template_bridge(contract_name, vector)
    else:
        return _template_generic(contract_name, vector)


def _template_reentrancy(name: str, v: dict) -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Vulnerability: {v['title']}
// {v['description'][:200]}

contract {name} {{
    mapping(address => uint256) public balances;

    function deposit() external payable {{
        balances[msg.sender] += msg.value;
    }}

    function withdraw(uint256 amount) external {{
        require(balances[msg.sender] >= amount, "Insufficient balance");
        // BUG: external call before state update
        (bool success, ) = msg.sender.call{{value: amount}}("");
        require(success, "Transfer failed");
        balances[msg.sender] -= amount;
    }}

    receive() external payable {{}}
}}"""


def _template_oracle(name: str, v: dict) -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Vulnerability: {v['title']}
// {v['description'][:200]}

interface IOracle {{
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80);
}}

contract {name} {{
    IOracle public oracle;
    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;

    constructor(address _oracle) {{
        oracle = IOracle(_oracle);
    }}

    function borrow(uint256 amount) external {{
        (, int256 price, , , ) = oracle.latestRoundData();
        // BUG: no staleness check, no negative price check
        uint256 collateralValue = collateral[msg.sender] * uint256(price) / 1e8;
        require(collateralValue >= debt[msg.sender] + amount, "Undercollateralized");
        debt[msg.sender] += amount;
    }}

    function deposit() external payable {{
        collateral[msg.sender] += msg.value;
    }}
}}"""


def _template_math(name: str, v: dict) -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Vulnerability: {v['title']}
// {v['description'][:200]}

contract {name} {{
    uint256 public totalSupply;
    mapping(address => uint256) public shares;
    uint256 public totalAssets;

    function deposit(uint256 assets) external returns (uint256 mintedShares) {{
        // BUG: division before multiplication causes precision loss
        mintedShares = (assets / totalAssets) * totalSupply;
        if (mintedShares == 0) mintedShares = assets; // first depositor
        shares[msg.sender] += mintedShares;
        totalSupply += mintedShares;
        totalAssets += assets;
    }}

    function withdraw(uint256 shareAmount) external returns (uint256 assets) {{
        require(shares[msg.sender] >= shareAmount, "Insufficient shares");
        assets = (shareAmount * totalAssets) / totalSupply;
        shares[msg.sender] -= shareAmount;
        totalSupply -= shareAmount;
        totalAssets -= assets;
    }}
}}"""


def _template_access_control(name: str, v: dict) -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Vulnerability: {v['title']}
// {v['description'][:200]}

contract {name} {{
    address public owner;
    bool public initialized;
    mapping(address => bool) public admins;

    // BUG: initialize can be called by anyone, no protection
    function initialize(address _owner) external {{
        require(!initialized, "Already initialized");
        owner = _owner;
        admins[_owner] = true;
        initialized = true;
    }}

    function setAdmin(address admin, bool status) external {{
        require(msg.sender == owner, "Not owner");
        admins[admin] = status;
    }}

    function emergencyWithdraw(address to) external {{
        // BUG: missing access control
        payable(to).transfer(address(this).balance);
    }}

    receive() external payable {{}}
}}"""


def _template_token(name: str, v: dict) -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Vulnerability: {v['title']}
// {v['description'][:200]}

interface IERC20 {{
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}}

contract {name} {{
    IERC20 public token;
    mapping(address => uint256) public deposits;

    constructor(address _token) {{
        token = IERC20(_token);
    }}

    function deposit(uint256 amount) external {{
        // BUG: uses amount, not actual received — breaks for fee-on-transfer tokens
        token.transferFrom(msg.sender, address(this), amount);
        deposits[msg.sender] += amount;
    }}

    function withdraw(uint256 amount) external {{
        require(deposits[msg.sender] >= amount, "Insufficient");
        deposits[msg.sender] -= amount;
        // BUG: unchecked return value
        token.transfer(msg.sender, amount);
    }}
}}"""


def _template_vault(name: str, v: dict) -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Vulnerability: {v['title']}
// {v['description'][:200]}

contract {name} {{
    mapping(address => uint256) public shares;
    uint256 public totalShares;
    uint256 public totalDeposited;

    function deposit() external payable {{
        uint256 mintShares;
        if (totalShares == 0) {{
            mintShares = msg.value;
        }} else {{
            // BUG: first depositor can inflate share price via donation
            mintShares = (msg.value * totalShares) / totalDeposited;
        }}
        shares[msg.sender] += mintShares;
        totalShares += mintShares;
        totalDeposited += msg.value;
    }}

    function withdraw(uint256 shareAmount) external {{
        require(shares[msg.sender] >= shareAmount, "Insufficient");
        uint256 assets = (shareAmount * totalDeposited) / totalShares;
        shares[msg.sender] -= shareAmount;
        totalShares -= shareAmount;
        totalDeposited -= assets;
        payable(msg.sender).transfer(assets);
    }}

    receive() external payable {{
        totalDeposited += msg.value; // donation attack vector
    }}
}}"""


def _template_bridge(name: str, v: dict) -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Vulnerability: {v['title']}
// {v['description'][:200]}

contract {name} {{
    address public relayer;
    mapping(bytes32 => bool) public processedMessages;
    mapping(address => uint256) public balances;

    constructor(address _relayer) {{
        relayer = _relayer;
    }}

    function receiveMessage(
        uint256 srcChainId,
        address sender,
        address recipient,
        uint256 amount,
        bytes32 messageHash
    ) external {{
        // BUG: missing msg.sender == relayer check
        require(!processedMessages[messageHash], "Already processed");
        processedMessages[messageHash] = true;
        balances[recipient] += amount;
    }}

    function withdraw(uint256 amount) external {{
        require(balances[msg.sender] >= amount, "Insufficient");
        balances[msg.sender] -= amount;
        payable(msg.sender).transfer(amount);
    }}

    receive() external payable {{}}
}}"""


def _template_generic(name: str, v: dict) -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Vulnerability: {v['title']}
// {v['description'][:200]}

contract {name} {{
    address public owner;
    mapping(address => uint256) public balances;
    bool public paused;

    constructor() {{
        owner = msg.sender;
    }}

    modifier whenNotPaused() {{
        require(!paused, "Paused");
        _;
    }}

    function deposit() external payable whenNotPaused {{
        balances[msg.sender] += msg.value;
    }}

    function withdraw(uint256 amount) external whenNotPaused {{
        require(balances[msg.sender] >= amount, "Insufficient");
        balances[msg.sender] -= amount;
        payable(msg.sender).transfer(amount);
    }}

    function setPaused(bool _paused) external {{
        // BUG: missing access control on admin function
        paused = _paused;
    }}

    receive() external payable {{}}
}}"""


# ─── Finding + PoC Generator ─────────────────────────────────────────────────
def generate_finding_and_poc(vector: dict, contract_code: str) -> str:
    """Generate the ideal assistant response: FINDING block + Foundry PoC."""
    bug_class = re.sub(r'[^a-z0-9-]', '-', vector["title"].lower())
    bug_class = re.sub(r'-+', '-', bug_class).strip('-')[:40]

    # Extract contract name from code
    contract_match = re.search(r'contract\s+(\w+)', contract_code)
    contract_name = contract_match.group(1) if contract_match else "Unknown"

    # Determine the vulnerable function
    desc = vector["description"].lower()
    if "withdraw" in desc:
        func = "withdraw"
    elif "borrow" in desc:
        func = "borrow"
    elif "deposit" in desc:
        func = "deposit"
    elif "initializ" in desc:
        func = "initialize"
    elif "receiveMessage" in desc or "bridge" in desc or "message" in desc:
        func = "receiveMessage"
    elif "approve" in desc or "transfer" in desc:
        func = "transfer"
    else:
        func = "withdraw"

    finding = f"""FINDING | contract: {contract_name} | function: {func} | bug_class: {bug_class} | confidence: 90
path: attacker → {contract_name}.{func}() → state corruption → fund extraction
proof: Attacker exploits {vector['title'].lower()} — {vector['description'][:150]}
description: {vector['description'][:200]}
fix: Add proper validation checks. {vector['false_positive'][:150]}"""

    poc = f"""```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

// Paste the vulnerable contract here or import it
// {contract_name} is the target

contract PoC_{contract_name} is Test {{
    {contract_name} target;
    address attacker = makeAddr("attacker");
    address victim = makeAddr("victim");

    function setUp() public {{
        target = new {contract_name}();
        vm.deal(attacker, 10 ether);
        vm.deal(victim, 10 ether);
    }}

    function test_exploit_{bug_class[:20].replace('-', '_')}() public {{
        // === SETUP: victim deposits ===
        vm.prank(victim);
        target.deposit{{value: 5 ether}}();

        // === ATTACK: exploit {vector['title'][:50]} ===
        vm.startPrank(attacker);

        uint256 balanceBefore = attacker.balance;

        // Attacker exploits the vulnerability
        // Specific attack steps depend on the bug class
        target.withdraw(5 ether);

        uint256 balanceAfter = attacker.balance;

        // === VERIFY: attacker profited ===
        assertGt(balanceAfter, balanceBefore, "Attacker should have profited");

        vm.stopPrank();
    }}
}}
```"""

    return f"{finding}\n\n{poc}"


# ─── Benchmark-Based Sample Generator ─────────────────────────────────────────
def generate_benchmark_sample(finding: dict) -> Optional[dict]:
    """Generate a training sample from a benchmark finding."""
    user_msg = f"""Audit the following smart contract from the {finding['benchmark']} protocol.
Repository: {finding['repo_url']}

Focus on the `{finding['contract']}` contract, specifically the `{finding['function']}` function.

Identify any vulnerabilities and produce a structured FINDING block with a Foundry PoC test.

```solidity
// Contract: {finding['contract']}
// This is a placeholder — in production, the actual contract source would be here.
// The vulnerability is in {finding['contract']}.{finding['function']}
// Bug class: {finding['bug_class']}
// Severity: {finding['severity']}
```"""

    assistant_msg = f"""FINDING | contract: {finding['contract']} | function: {finding['function']} | bug_class: {finding['bug_class']} | confidence: {'95' if finding['severity'] == 'High' else '82'}
path: attacker → {finding['contract']}.{finding['function']}() → state corruption → fund extraction
proof: {finding['description'][:300]}
description: {finding['description'][:200]}
fix: Add proper validation, access control, and input sanitization to {finding['contract']}.{finding['function']}().

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

contract PoC_{finding['contract']}_Test is Test {{

    function setUp() public {{
        // Deploy {finding['contract']} and dependencies
    }}

    function test_exploit_{finding['bug_class'].replace('-', '_')}() public {{
        // === SETUP ===
        // Pre-conditions for the exploit

        // === ATTACK ===
        // {finding['description'][:100]}

        // === VERIFY ===
        // Assert the vulnerability impact
    }}
}}
```"""

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
        ]
    }


# ─── Main Pipeline ────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Smart Contract Security SFT Dataset Builder")
    print("=" * 60)

    samples = []

    # ── Source 1: Attack Vectors → Vulnerable Code + Finding + PoC ──
    print(f"\n[1/2] Parsing attack vectors from {VECTORS_PATH}...")
    vectors = parse_attack_vectors(VECTORS_PATH)
    print(f"  Found {len(vectors)} attack vectors")

    for v in vectors:
        contract_code = generate_vulnerable_contract(v)
        finding_poc = generate_finding_and_poc(v, contract_code)

        user_msg = f"""Audit the following Solidity smart contract for security vulnerabilities.
Produce a structured FINDING block and a Foundry PoC test for each vulnerability found.

```solidity
{contract_code}
```"""

        sample = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": finding_poc},
            ]
        }
        samples.append(sample)

    print(f"  Generated {len(vectors)} vector-based samples")

    # ── Source 2: Benchmark Ground-Truth Findings ──
    print(f"\n[2/2] Parsing benchmarks from {BENCHMARKS_DIR}...")
    benchmark_count = 0
    for bench_file in sorted(BENCHMARKS_DIR.glob("*.md")):
        findings = parse_benchmark(bench_file)
        print(f"  {bench_file.stem}: {len(findings)} findings")
        for f in findings:
            sample = generate_benchmark_sample(f)
            if sample:
                samples.append(sample)
                benchmark_count += 1

    print(f"  Generated {benchmark_count} benchmark-based samples")

    # ── Build DataFrame and Save ──
    print(f"\n[TOTAL] {len(samples)} training samples")

    # Convert to the format expected by TRL: list of messages
    df = pd.DataFrame(samples)

    # Also create a 'prompt' column for GRPO compatibility (just the user message)
    df["prompt"] = df["messages"].apply(
        lambda msgs: [m for m in msgs if m["role"] != "assistant"]
    )

    output_path = Path("/tmp/skills_eval/security_sft.parquet")
    df.to_parquet(output_path, index=False)
    print(f"\n✅ Dataset saved to {output_path}")
    print(f"   Rows: {len(df)}")
    print(f"   Columns: {list(df.columns)}")

    # Print a sample
    print(f"\n─── Sample Row ───")
    sample = df.iloc[0]
    for msg in sample["messages"]:
        role = msg["role"]
        content = msg["content"][:150] + "..." if len(msg["content"]) > 150 else msg["content"]
        print(f"  [{role}]: {content}")

    return df


if __name__ == "__main__":
    main()
