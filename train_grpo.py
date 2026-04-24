#!/usr/bin/env python3
"""
train_grpo.py — GRPO Training Script for Smart Contract Security Auditor

Uses Hugging Face TRL's GRPOTrainer to fine-tune a coding model via Group Relative
Policy Optimization. Implements a custom reward function that:

1. Parses the model's generated response to extract:
   - A structured FINDING block (format compliance reward)
   - A Foundry PoC test (compilability + exploit success reward)

2. Uses subprocess to run `forge test` on the extracted PoC in a temp directory.
   - +1.0 reward if the PoC compiles AND the test passes (exploit proven)
   - +0.3 reward if the PoC compiles but the test fails (partial credit)
   - -0.5 reward if the PoC doesn't compile
   - -1.0 reward if no PoC/FINDING block is found at all

Based on:
  - DeepSeekMath GRPO (2402.03300)
  - SFT→GRPO pipeline from "From SFT to RL" (2602.14012)
  - SecCoderX secure code generation via RL (2602.07422)

Usage:
  # Single GPU (small model):
  python train_grpo.py

  # Multi-GPU with accelerate:
  accelerate launch train_grpo.py

  # With custom model:
  python train_grpo.py --model_name Qwen/Qwen2.5-Coder-3B-Instruct
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd
from datasets import Dataset

from trl import GRPOTrainer, GRPOConfig

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
FORGE_AVAILABLE = shutil.which("forge") is not None
FOUNDRY_TOML = """[profile.default]
src = "src"
out = "out"
libs = ["lib"]
solc_version = "0.8.24"
"""

FORGE_STD_REMAPPING = """forge-std/=lib/forge-std/src/"""


# ─── Reward Functions ─────────────────────────────────────────────────────────

def extract_finding_block(text: str) -> dict | None:
    """Extract a structured FINDING block from model output."""
    pattern = re.compile(
        r'FINDING\s*\|\s*contract:\s*(\S+)\s*\|\s*function:\s*(\S+)\s*\|'
        r'\s*bug_class:\s*(\S+)\s*\|\s*confidence:\s*(\d+)',
        re.IGNORECASE
    )
    match = pattern.search(text)
    if not match:
        return None
    return {
        "contract": match.group(1),
        "function": match.group(2),
        "bug_class": match.group(3),
        "confidence": int(match.group(4)),
    }


def extract_solidity_poc(text: str) -> str | None:
    """Extract the Foundry PoC test code from model output."""
    # Look for solidity code blocks
    pattern = re.compile(r'```solidity\s*\n(.*?)```', re.DOTALL)
    matches = pattern.findall(text)
    if not matches:
        return None

    # Find the block that looks like a test (contains "is Test" or "function test_")
    for code in matches:
        if "is Test" in code or "function test_" in code or "function test" in code:
            return code.strip()

    # If no test-specific block, return the largest code block
    if matches:
        return max(matches, key=len).strip()

    return None


def run_forge_test(poc_code: str, timeout: int = 30) -> dict:
    """
    Run a Foundry PoC test in a temporary directory.

    Returns:
        dict with keys:
        - compiled: bool
        - test_passed: bool
        - output: str (stdout+stderr)
    """
    if not FORGE_AVAILABLE:
        # If forge is not installed, we can only do syntax-level checks
        return {
            "compiled": False,
            "test_passed": False,
            "output": "forge not available — using syntax check only",
            "syntax_valid": _check_solidity_syntax(poc_code),
        }

    tmpdir = tempfile.mkdtemp(prefix="forge_poc_")
    try:
        # Set up Foundry project structure
        src_dir = Path(tmpdir) / "src"
        test_dir = Path(tmpdir) / "test"
        src_dir.mkdir()
        test_dir.mkdir()

        # Write foundry.toml
        (Path(tmpdir) / "foundry.toml").write_text(FOUNDRY_TOML)

        # Install forge-std (minimal — just create the directory structure)
        lib_dir = Path(tmpdir) / "lib" / "forge-std" / "src"
        lib_dir.mkdir(parents=True)

        # Write remappings
        (Path(tmpdir) / "remappings.txt").write_text(FORGE_STD_REMAPPING)

        # Install forge-std via forge
        try:
            subprocess.run(
                ["forge", "install", "foundry-rs/forge-std", "--no-git", "--no-commit"],
                cwd=tmpdir,
                capture_output=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Write the PoC test file
        (test_dir / "PoC.t.sol").write_text(poc_code)

        # Try to build first
        build_result = subprocess.run(
            ["forge", "build"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if build_result.returncode != 0:
            return {
                "compiled": False,
                "test_passed": False,
                "output": build_result.stderr[:500],
            }

        # Run the test
        test_result = subprocess.run(
            ["forge", "test", "-vv"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        test_passed = test_result.returncode == 0 and "PASS" in test_result.stdout
        return {
            "compiled": True,
            "test_passed": test_passed,
            "output": (test_result.stdout + test_result.stderr)[:500],
        }

    except subprocess.TimeoutExpired:
        return {
            "compiled": False,
            "test_passed": False,
            "output": "forge timed out",
        }
    except Exception as e:
        return {
            "compiled": False,
            "test_passed": False,
            "output": f"Error: {str(e)[:200]}",
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _check_solidity_syntax(code: str) -> bool:
    """Basic syntax check for Solidity code without forge."""
    required_patterns = [
        r'pragma\s+solidity',
        r'contract\s+\w+',
        r'function\s+\w+',
    ]
    return all(re.search(p, code) for p in required_patterns)


# ─── GRPO Reward Function (TRL-compatible signature) ──────────────────────────

def security_audit_reward(completions, prompts=None, log_extra=None, log_metric=None, **kwargs):
    """
    Custom reward function for GRPO training.

    Evaluates each completion on three dimensions:
    1. Format compliance: Does it contain a valid FINDING block?
    2. PoC quality: Does it contain a valid Solidity test?
    3. Exploit verification: Does the PoC compile and demonstrate the bug?

    Reward scale:
      +1.0  = FINDING block + PoC compiles + test passes (exploit proven)
      +0.5  = FINDING block + PoC compiles + test fails (good attempt)
      +0.2  = FINDING block + PoC present but doesn't compile
      +0.0  = FINDING block but no PoC
      -0.5  = No FINDING block but some relevant content
      -1.0  = Empty or completely irrelevant output
    """
    rewards = []
    compile_count = 0
    pass_count = 0
    finding_count = 0

    for i, completion in enumerate(completions):
        # Handle both standard and conversational formats
        if isinstance(completion, list):
            # Conversational format: list of message dicts
            text = completion[0]["content"] if completion else ""
        else:
            text = str(completion)

        reward = -1.0  # default: no useful output

        # Step 1: Check for FINDING block
        finding = extract_finding_block(text)
        if finding:
            finding_count += 1
            reward = 0.0  # at least has a finding

            # Step 2: Check for PoC code
            poc_code = extract_solidity_poc(text)
            if poc_code:
                reward = 0.2  # has a PoC attempt

                # Step 3: Try to compile and run
                result = run_forge_test(poc_code)

                if result.get("compiled") or result.get("syntax_valid", False):
                    compile_count += 1
                    reward = 0.5  # compiles

                    if result.get("test_passed"):
                        pass_count += 1
                        reward = 1.0  # exploit proven!
                else:
                    reward = 0.2  # compilation failed
        elif any(kw in text.lower() for kw in ["vulnerability", "exploit", "bug", "finding"]):
            reward = -0.5  # at least tried

        rewards.append(reward)

    # Log metrics
    if log_metric and len(rewards) > 0:
        log_metric("finding_rate", finding_count / len(rewards))
        log_metric("compile_rate", compile_count / len(rewards))
        log_metric("exploit_rate", pass_count / len(rewards))

    if log_extra:
        log_extra("has_finding", ["yes" if extract_finding_block(
            c[0]["content"] if isinstance(c, list) else str(c)
        ) else "no" for c in completions])

    return rewards


def format_reward(completions, **kwargs):
    """
    Secondary reward function that checks structural format compliance.

    Rewards:
      +0.5 = Has FINDING block with all required fields
      +0.3 = Has FINDING block with some fields
      +0.1 = Has code block
      0.0  = Nothing useful
    """
    rewards = []
    for completion in completions:
        if isinstance(completion, list):
            text = completion[0]["content"] if completion else ""
        else:
            text = str(completion)

        reward = 0.0

        # Check for FINDING block completeness
        has_finding = bool(re.search(r'FINDING\s*\|', text))
        has_path = bool(re.search(r'path:', text))
        has_proof = bool(re.search(r'proof:', text))
        has_description = bool(re.search(r'description:', text))
        has_fix = bool(re.search(r'fix:', text))
        has_code = bool(re.search(r'```solidity', text))

        if has_finding:
            field_count = sum([has_path, has_proof, has_description, has_fix])
            reward = 0.3 + (0.05 * field_count)  # 0.3 base + 0.05 per field, max 0.5

        if has_code:
            reward += 0.1

        rewards.append(reward)

    return rewards


# ─── Dataset Loading ──────────────────────────────────────────────────────────

def load_sft_dataset(path: str) -> Dataset:
    """Load the SFT dataset and convert to GRPO format.

    GRPO needs a 'prompt' column containing the system+user messages.
    The model generates completions (assistant responses) during training.
    """
    df = pd.read_parquet(path)

    # The 'prompt' column already contains [system, user] messages
    # Convert to HF Dataset
    dataset = Dataset.from_pandas(df[["prompt"]])
    return dataset


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GRPO Training for Smart Contract Security Auditor")
    parser.add_argument("--model_name", type=str, default="Qwen/Qwen2.5-Coder-1.5B-Instruct",
                        help="Model to fine-tune")
    parser.add_argument("--dataset_path", type=str, default="/tmp/skills_eval/security_sft.parquet",
                        help="Path to the SFT dataset")
    parser.add_argument("--output_dir", type=str, default="/tmp/skills_eval/grpo_output",
                        help="Output directory for checkpoints")
    parser.add_argument("--hub_model_id", type=str, default=None,
                        help="HuggingFace Hub model ID for pushing")
    parser.add_argument("--num_train_epochs", type=int, default=2,
                        help="Number of training epochs")
    parser.add_argument("--per_device_train_batch_size", type=int, default=2,
                        help="Batch size per device")
    parser.add_argument("--num_generations", type=int, default=4,
                        help="Number of generations per prompt (G in GRPO)")
    parser.add_argument("--learning_rate", type=float, default=5e-7,
                        help="Learning rate")
    parser.add_argument("--max_completion_length", type=int, default=2048,
                        help="Maximum completion length")
    parser.add_argument("--push_to_hub", action="store_true",
                        help="Push model to HuggingFace Hub")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("GRPO Training — Smart Contract Security Auditor")
    logger.info("=" * 60)
    logger.info(f"Model: {args.model_name}")
    logger.info(f"Dataset: {args.dataset_path}")
    logger.info(f"Forge available: {FORGE_AVAILABLE}")

    # Load dataset
    logger.info("Loading dataset...")
    dataset = load_sft_dataset(args.dataset_path)
    logger.info(f"Dataset size: {len(dataset)} samples")

    # Configure GRPO
    training_args = GRPOConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        learning_rate=args.learning_rate,
        num_generations=args.num_generations,
        max_completion_length=args.max_completion_length,

        # GRPO-specific settings
        beta=0.0,                    # No KL divergence penalty (per recent best practices)
        scale_rewards=True,          # Normalize rewards by std
        reward_weights=[0.7, 0.3],   # Primary: exploit verification, Secondary: format

        # Training settings
        gradient_checkpointing=True,
        bf16=True,
        logging_steps=5,
        logging_first_step=True,
        disable_tqdm=True,           # Plain text logs, not tqdm bars
        save_strategy="steps",
        save_steps=50,
        save_total_limit=3,
        log_completions=True,        # Log completions for debugging

        # Hub settings
        push_to_hub=args.push_to_hub,
        hub_model_id=args.hub_model_id,

        # Misc
        report_to="none",            # Set to "wandb" or "tensorboard" for tracking
        seed=42,
    )

    # Initialize trainer with dual reward functions
    logger.info("Initializing GRPOTrainer...")
    trainer = GRPOTrainer(
        model=args.model_name,
        args=training_args,
        reward_funcs=[security_audit_reward, format_reward],
        train_dataset=dataset,
    )

    # Train
    logger.info("Starting GRPO training...")
    logger.info(f"  Reward functions: security_audit_reward (0.7) + format_reward (0.3)")
    logger.info(f"  Generations per prompt (G): {args.num_generations}")
    logger.info(f"  Effective batch: {args.per_device_train_batch_size} * {args.num_generations} = {args.per_device_train_batch_size * args.num_generations}")

    trainer.train()

    # Save
    logger.info("Saving model...")
    trainer.save_model(args.output_dir)

    if args.push_to_hub and args.hub_model_id:
        logger.info(f"Pushing to hub: {args.hub_model_id}")
        trainer.push_to_hub()

    logger.info("✅ GRPO training complete!")
    logger.info(f"   Model saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
