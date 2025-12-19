#!/usr/bin/env python3
"""
build_artifacts_master.py
==========================

Master orchestrator for artifact generation pipeline.
Runs Parts A, B, C and validates all outputs for website readiness.

This script does NOT implement any analytics logic.
It ONLY orchestrates, validates, and certifies readiness.

Usage:
  python scripts/build_artifacts_master.py
  python scripts/build_artifacts_master.py --self-test

Environment:
  MASTER_TEST_MODE=1 - Enable test mode (forwards ARTIFACT_SCAN_LIMIT to parts)
  ARTIFACT_SCAN_LIMIT=N - Limit entries scanned (test mode only)

Exit codes:
  0 - PASS (all artifacts ready)
  1 - FAIL (validation failed)
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
ARTIFACTS_DIR = Path("public/data/artifacts")

# SSOT: Expected artifact files
EXPECTED_ARTIFACTS = [
    # Part A
    "coverage_v7.json",
    "scale_v7.json",
    "preview_row_v7.json",
    # Part B
    "sentiment_vs_forward_return_v7.json",
    "regimes_activity_vs_silence_v7.json",
    # Part C
    "hybrid_decisions_v7.json",
    "confidence_disagreement_v7.json",
    "lifecycle_summary_v7.json",
]

# Part scripts to run
PART_SCRIPTS = [
    ("A", "build_artifacts_part_a.py"),
    ("B", "build_artifacts_part_b.py"),
    ("C", "build_artifacts_part_c.py"),
]


# ============================================================================
# Validation state
# ============================================================================

class ValidationState:
    """Track validation progress and results."""
    
    def __init__(self):
        self.checks_passed: List[str] = []
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.artifacts_verified: List[str] = []
    
    def add_pass(self, check: str):
        """Record a passed check."""
        self.checks_passed.append(check)
        print(f"[OK] {check}")
    
    def add_warn(self, message: str):
        """Record a warning."""
        self.warnings.append(message)
        print(f"[WARN] {message}")
    
    def add_error(self, message: str):
        """Record an error."""
        self.errors.append(message)
        print(f"[ERROR] {message}")
    
    def is_passing(self) -> bool:
        """Check if validation is passing (no errors)."""
        return len(self.errors) == 0
    
    def print_summary(self):
        """Print final summary."""
        print()
        print("=" * 60)
        if self.is_passing():
            print("[PASS] Artifacts ready for website ingestion")
        else:
            print("[FAIL] Artifacts validation failed")
        print("=" * 60)
        print(f"Checks passed: {len(self.checks_passed)}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"Errors: {len(self.errors)}")
        print(f"Artifacts verified: {len(self.artifacts_verified)}")


# ============================================================================
# Step 2: Run parts A, B, C
# ============================================================================

def run_part(part_name: str, script_name: str, state: ValidationState) -> bool:
    """
    Run one part script via subprocess.
    Returns True if successful, False otherwise.
    """
    script_path = SCRIPT_DIR / script_name
    
    if not script_path.exists():
        state.add_error(f"Part {part_name} script not found: {script_path}")
        return False
    
    print(f"[RUN] Part {part_name}: {script_name}")
    
    try:
        # Use same Python interpreter
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        
        # Print stdout/stderr
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        
        if result.returncode != 0:
            state.add_error(f"Part {part_name} failed with exit code {result.returncode}")
            return False
        
        state.add_pass(f"Part {part_name} completed")
        return True
    
    except Exception as e:
        state.add_error(f"Part {part_name} exception: {e}")
        return False


# ============================================================================
# Step 3: File existence validation
# ============================================================================

def validate_file_existence(state: ValidationState) -> bool:
    """
    Check that all expected artifacts exist and are valid JSON.
    Returns True if all files valid, False otherwise.
    """
    all_valid = True
    
    for artifact_name in EXPECTED_ARTIFACTS:
        artifact_path = ARTIFACTS_DIR / artifact_name
        
        # Check exists
        if not artifact_path.exists():
            state.add_error(f"Missing artifact: {artifact_name}")
            all_valid = False
            continue
        
        # Check non-empty
        if artifact_path.stat().st_size == 0:
            state.add_error(f"Empty artifact: {artifact_name}")
            all_valid = False
            continue
        
        # Check valid JSON
        try:
            with open(artifact_path, "r", encoding="utf-8") as f:
                json.load(f)
            state.artifacts_verified.append(artifact_name)
        except json.JSONDecodeError as e:
            state.add_error(f"Invalid JSON in {artifact_name}: {e}")
            all_valid = False
            continue
    
    if all_valid:
        state.add_pass("All artifacts present and valid JSON")
    
    return all_valid


# ============================================================================
# Step 4: Schema sanity checks
# ============================================================================

def validate_coverage_schema(data: Dict[str, Any], state: ValidationState) -> bool:
    """Validate coverage_v7.json schema."""
    try:
        # Must have counts with v7_seen
        counts = data.get("counts", {})
        v7_seen = counts.get("v7_seen")
        if not isinstance(v7_seen, int) or v7_seen <= 0:
            state.add_error("coverage_v7: counts.v7_seen must be int > 0")
            return False
        
        # Must have groups (non-empty list)
        groups = data.get("groups", [])
        if not isinstance(groups, list) or len(groups) == 0:
            state.add_error("coverage_v7: groups must be non-empty list")
            return False
        
        return True
    except Exception as e:
        state.add_error(f"coverage_v7 schema validation failed: {e}")
        return False


def validate_scale_schema(data: Dict[str, Any], state: ValidationState) -> bool:
    """Validate scale_v7.json schema."""
    try:
        # Must have days_running >= 1
        days_running = data.get("days_running")
        if not isinstance(days_running, int) or days_running < 1:
            state.add_error("scale_v7: days_running must be int >= 1")
            return False
        
        # Must have v7_usable_total > 0
        v7_usable_total = data.get("v7_usable_total")
        if not isinstance(v7_usable_total, int) or v7_usable_total <= 0:
            state.add_error("scale_v7: v7_usable_total must be int > 0")
            return False
        
        # Must have avg_usable_per_day > 0
        avg_usable = data.get("avg_usable_per_day")
        if not isinstance(avg_usable, (int, float)) or avg_usable <= 0:
            state.add_error("scale_v7: avg_usable_per_day must be number > 0")
            return False
        
        return True
    except Exception as e:
        state.add_error(f"scale_v7 schema validation failed: {e}")
        return False


def validate_preview_schema(data: Dict[str, Any], state: ValidationState) -> bool:
    """Validate preview_row_v7.json schema."""
    try:
        # Must have a "row" object
        row = data.get("row")
        if not isinstance(row, dict):
            state.add_error("preview_row_v7: must have 'row' object")
            return False
        
        # Check for key fields in row (with prefixes as Part A generates)
        required_fields = [
            "symbol",
            "next_1h_return_bucket",
        ]
        
        # Check at least these core fields exist
        for field in required_fields:
            if field not in row:
                state.add_error(f"preview_row_v7: row missing field '{field}'")
                return False
        
        return True
    except Exception as e:
        state.add_error(f"preview_row_v7 schema validation failed: {e}")
        return False


def validate_behavior_artifact(
    name: str,
    data: Dict[str, Any],
    state: ValidationState,
) -> bool:
    """Validate behavior artifact (B1/B2) for NaN/inf."""
    try:
        json_str = json.dumps(data)
        
        # Check for NaN/inf (case-insensitive, as JSON values)
        if ": NaN" in json_str or ": Infinity" in json_str or ": -Infinity" in json_str:
            state.add_error(f"{name}: contains NaN or Infinity values")
            return False
        
        return True
    except Exception as e:
        state.add_error(f"{name} validation failed: {e}")
        return False


def validate_hybrid_decisions_schema(data: Dict[str, Any], state: ValidationState) -> bool:
    """Validate hybrid_decisions_v7.json schema."""
    try:
        # Check decision_sources percentages sum to ~1.0
        decision_sources = data.get("decision_sources", {})
        
        primary_lex_pct = decision_sources.get("primary_lexicon", {}).get("percentage", 0)
        primary_ai_pct = decision_sources.get("primary_ai", {}).get("percentage", 0)
        referee_pct = decision_sources.get("referee_override", {}).get("percentage", 0)
        full_agree_pct = decision_sources.get("full_agreement", {}).get("percentage", 0)
        
        total_pct = primary_lex_pct + primary_ai_pct + referee_pct + full_agree_pct
        
        # Allow for rounding: within 0.01
        if abs(total_pct - 1.0) > 0.01 and total_pct != 0.0:
            state.add_error(
                f"hybrid_decisions_v7: percentages sum to {total_pct}, expected ~1.0"
            )
            return False
        
        return True
    except Exception as e:
        state.add_error(f"hybrid_decisions_v7 schema validation failed: {e}")
        return False


def validate_lifecycle_schema(data: Dict[str, Any], state: ValidationState) -> bool:
    """Validate lifecycle_summary_v7.json schema."""
    try:
        # Must have at least 1 symbol
        symbols = data.get("symbols", [])
        if not isinstance(symbols, list) or len(symbols) == 0:
            state.add_error("lifecycle_summary_v7: must have at least 1 symbol")
            return False
        
        return True
    except Exception as e:
        state.add_error(f"lifecycle_summary_v7 schema validation failed: {e}")
        return False


def validate_schemas(state: ValidationState) -> bool:
    """
    Validate schema of all artifacts.
    Returns True if all schemas valid, False otherwise.
    """
    all_valid = True
    
    # Coverage
    try:
        with open(ARTIFACTS_DIR / "coverage_v7.json", "r") as f:
            data = json.load(f)
        if not validate_coverage_schema(data, state):
            all_valid = False
    except Exception as e:
        state.add_error(f"Failed to validate coverage_v7: {e}")
        all_valid = False
    
    # Scale
    try:
        with open(ARTIFACTS_DIR / "scale_v7.json", "r") as f:
            data = json.load(f)
        if not validate_scale_schema(data, state):
            all_valid = False
    except Exception as e:
        state.add_error(f"Failed to validate scale_v7: {e}")
        all_valid = False
    
    # Preview
    try:
        with open(ARTIFACTS_DIR / "preview_row_v7.json", "r") as f:
            data = json.load(f)
        if not validate_preview_schema(data, state):
            all_valid = False
    except Exception as e:
        state.add_error(f"Failed to validate preview_row_v7: {e}")
        all_valid = False
    
    # Sentiment vs forward return (B1)
    try:
        with open(ARTIFACTS_DIR / "sentiment_vs_forward_return_v7.json", "r") as f:
            data = json.load(f)
        if not validate_behavior_artifact("sentiment_vs_forward_return_v7", data, state):
            all_valid = False
    except Exception as e:
        state.add_error(f"Failed to validate sentiment_vs_forward_return_v7: {e}")
        all_valid = False
    
    # Regimes (B2)
    try:
        with open(ARTIFACTS_DIR / "regimes_activity_vs_silence_v7.json", "r") as f:
            data = json.load(f)
        if not validate_behavior_artifact("regimes_activity_vs_silence_v7", data, state):
            all_valid = False
    except Exception as e:
        state.add_error(f"Failed to validate regimes_activity_vs_silence_v7: {e}")
        all_valid = False
    
    # Hybrid decisions (C1)
    try:
        with open(ARTIFACTS_DIR / "hybrid_decisions_v7.json", "r") as f:
            data = json.load(f)
        if not validate_hybrid_decisions_schema(data, state):
            all_valid = False
    except Exception as e:
        state.add_error(f"Failed to validate hybrid_decisions_v7: {e}")
        all_valid = False
    
    # Confidence/disagreement (C2)
    try:
        with open(ARTIFACTS_DIR / "confidence_disagreement_v7.json", "r") as f:
            data = json.load(f)
        if not validate_behavior_artifact("confidence_disagreement_v7", data, state):
            all_valid = False
    except Exception as e:
        state.add_error(f"Failed to validate confidence_disagreement_v7: {e}")
        all_valid = False
    
    # Lifecycle (C3)
    try:
        with open(ARTIFACTS_DIR / "lifecycle_summary_v7.json", "r") as f:
            data = json.load(f)
        if not validate_lifecycle_schema(data, state):
            all_valid = False
    except Exception as e:
        state.add_error(f"Failed to validate lifecycle_summary_v7: {e}")
        all_valid = False
    
    if all_valid:
        state.add_pass("Schema checks passed")
    
    return all_valid


# ============================================================================
# Step 5: Cross-artifact consistency checks
# ============================================================================

def validate_consistency(state: ValidationState) -> bool:
    """
    Validate consistency across artifacts.
    Returns True if consistent, False otherwise.
    """
    try:
        # Load scale_v7 for reference usable count
        with open(ARTIFACTS_DIR / "scale_v7.json", "r") as f:
            scale_data = json.load(f)
        
        reference_usable = scale_data.get("v7_usable_total", 0)
        
        # Load coverage_v7
        with open(ARTIFACTS_DIR / "coverage_v7.json", "r") as f:
            coverage_data = json.load(f)
        
        coverage_usable = coverage_data.get("counts", {}).get("v7_usable", 0)
        
        # Compare within 1%
        if reference_usable > 0:
            diff_pct = abs(coverage_usable - reference_usable) / reference_usable
            
            if diff_pct > 0.01:
                state.add_error(
                    f"Consistency check failed: scale v7_usable={reference_usable}, "
                    f"coverage v7_usable={coverage_usable}, diff={diff_pct*100:.1f}%"
                )
                return False
            elif diff_pct > 0.001:
                state.add_warn(
                    f"Minor inconsistency: scale v7_usable={reference_usable}, "
                    f"coverage v7_usable={coverage_usable}, diff={diff_pct*100:.2f}%"
                )
        
        state.add_pass("Consistency checks passed")
        return True
    
    except Exception as e:
        state.add_error(f"Consistency check failed: {e}")
        return False


# ============================================================================
# Step 6: Write readiness report
# ============================================================================

def write_readiness_report(state: ValidationState) -> None:
    """Write ARTIFACTS_READY.json report."""
    report = {
        "status": "PASS" if state.is_passing() else "FAIL",
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "artifacts_verified": state.artifacts_verified,
        "checks_passed": state.checks_passed,
        "warnings": state.warnings,
        "errors": state.errors,
        "ready_for_website": state.is_passing(),
    }
    
    report_path = ARTIFACTS_DIR / "ARTIFACTS_READY.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=True)
    
    print(f"[OUT] Wrote readiness report: {report_path}")


# ============================================================================
# Main pipeline
# ============================================================================

def run_pipeline(self_test: bool = False) -> int:
    """
    Run the full artifact generation and validation pipeline.
    Returns exit code (0=success, 1=failure).
    """
    print("=" * 60)
    print("Artifact Master Builder")
    print("=" * 60)
    
    # Check test mode
    if self_test or os.getenv("MASTER_TEST_MODE") == "1":
        print("[TEST] Running in test mode")
        scan_limit = os.getenv("ARTIFACT_SCAN_LIMIT")
        if scan_limit:
            print(f"[TEST] ARTIFACT_SCAN_LIMIT={scan_limit}")
    
    state = ValidationState()
    
    # Step 2: Run parts A, B, C
    for part_name, script_name in PART_SCRIPTS:
        if not run_part(part_name, script_name, state):
            state.print_summary()
            write_readiness_report(state)
            return 1
    
    # Step 3: File existence validation
    if not validate_file_existence(state):
        state.print_summary()
        write_readiness_report(state)
        return 1
    
    # Step 4: Schema validation
    if not validate_schemas(state):
        state.print_summary()
        write_readiness_report(state)
        return 1
    
    # Step 5: Consistency validation
    if not validate_consistency(state):
        state.print_summary()
        write_readiness_report(state)
        return 1
    
    # All checks passed
    state.print_summary()
    write_readiness_report(state)
    return 0


# ============================================================================
# Entry point
# ============================================================================

def main():
    # Parse command-line args
    self_test = "--self-test" in sys.argv
    
    exit_code = run_pipeline(self_test=self_test)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
