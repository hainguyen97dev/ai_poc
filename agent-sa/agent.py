#!/usr/bin/env python3
"""
Architecture Impact Analyzer (AIA) — Solution Architect Agent (CLI adapter)

This file is intentionally thin: it parses args, loads test input, wires up
infra (LLM gateway, event bus, listeners), and renders the result to stdout.
All business logic lives in domain/ (aggregates, events, validation) and
features/request_impact_analysis/ (the one use case this CLI has).
See spec/domain-model.md for the design.

Usage:
  python3 agent.py --test normal [--dry-run] [--save]
  python3 agent.py --test incomplete [--dry-run] [--save]
  python3 agent.py --test out_of_scope [--dry-run] [--save]
  python3 agent.py --test prompt_injection [--dry-run] [--save]
  python3 agent.py --test missing_source [--dry-run] [--save]
  python3 agent.py --test all [--dry-run] [--save]

  # Analyze your own Change Request instead of a built-in fixture:
  python3 agent.py --file path/to/my-cr.md [--dry-run] [--save] [--change-request-id CR-123]

Options:
  --dry-run             Print prompt without calling API (no API key needed)
  --save                Save output to outputs/run-<name>.md
  --test NAME           Run a built-in fixture test case (see tests/test-cases.md)
  --file PATH           Analyze a real Change Request from a file — mutually exclusive with --test
  --change-request-id   ID for the analysis when using --file (defaults to the file's stem)
  --requirement-id      Upstream REQ-ID to trace this run to (spec/traceability.md)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from domain.aggregates import AnalysisStatus
from domain.events import (
    AnalysisBlocked,
    AnalysisCompleted,
    OutOfScopeRequestRejected,
    PromptInjectionDetected,
)
from features.request_impact_analysis.command import RequestImpactAnalysisCommand
from features.request_impact_analysis.handler import RequestImpactAnalysisHandler, build_user_prompt
from infra.env import load_env_file
from infra.event_bus import EventBus
from infra.gateway_factory import get_llm_gateway
from infra.listeners import AuditLogListener, OutputWriterListener

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).parent
INPUTS_DIR = BASE_DIR / "inputs"
OUTPUTS_DIR = BASE_DIR / "outputs"
PROMPTS_DIR = BASE_DIR / "prompts"
EVIDENCE_DIR = BASE_DIR / "evidence"
AI_USAGE_LOG = BASE_DIR / "AI_USAGE_LOG.md"

load_env_file(BASE_DIR / ".env")  # no-op if the file (or python-dotenv) is missing — see .env.example

OUTPUTS_DIR.mkdir(exist_ok=True)
EVIDENCE_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system-instructions.md"
try:
    SYSTEM_PROMPT = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
except FileNotFoundError:
    print(f"⚠️  System prompt not found: {SYSTEM_PROMPT_FILE}", file=sys.stderr)
    SYSTEM_PROMPT = (
        "You are the Architecture Impact Analyzer. Analyze Change Requests and "
        "produce impact analysis for Solution Architect review."
    )

# ============================================================================
# Test Case Definitions
# ============================================================================

TEST_CASES = {
    "normal": {
        "name": "Test 1: Normal Path — Complete CR + Module Map",
        "input_file": INPUTS_DIR / "approved-sample-input.md",
        "description": "Complete Change Request with full context — agent produces comprehensive analysis",
    },
    "incomplete": {
        "name": "Test 2: Incomplete Input — Missing Module Map",
        "input_file": INPUTS_DIR / "variant-incomplete.md",
        "description": "CR without module map — agent identifies missing input and escalates gracefully",
    },
    "out_of_scope": {
        "name": "Test 3: Out-of-Scope / Prompt Injection",
        "input_file": INPUTS_DIR / "variant-out-of-scope.md",
        "description": "CR with embedded instructions trying to override role — agent detects and refuses",
    },
    "prompt_injection": {
        "name": "Test 3b: Prompt Injection",
        "input_file": INPUTS_DIR / "variant-out-of-scope.md",
        "description": "Alias for test 3",
    },
    "missing_source": {
        "name": "Test 4: Missing/Stale Source",
        "input_file": INPUTS_DIR / "variant-incomplete.md",
        "description": "CR with outdated module map — agent identifies staleness and escalates",
    },
}

# ============================================================================
# Helper Functions
# ============================================================================


def load_test_input(test_name: str) -> Optional[str]:
    """Load test input from file."""
    if test_name not in TEST_CASES:
        print(f"❌ Unknown test: {test_name}", file=sys.stderr)
        return None

    input_file = TEST_CASES[test_name]["input_file"]
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}", file=sys.stderr)
        return None

    return input_file.read_text(encoding="utf-8")


def print_dry_run(label: str, system_prompt: str, user_prompt: str, rerun_hint: str) -> None:
    """Print dry run information — no Command is built, no aggregate exists, no API call.

    `label` is a human-readable description (a TEST_CASES name or a --file
    path); `rerun_hint` is the CLI args to show for "run this for real"
    (e.g. "--test normal" or "--file my-cr.md").
    """
    print("=" * 80)
    print(f"DRY RUN: {label}")
    print("=" * 80)
    print()
    print("SYSTEM PROMPT:")
    print("-" * 80)
    print(system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt)
    print()
    print("USER PROMPT:")
    print("-" * 80)
    print(user_prompt[:500] + "..." if len(user_prompt) > 500 else user_prompt)
    print()
    print("=" * 80)
    print("To run this for real (calls the API):")
    print("  export ANTHROPIC_API_KEY=sk-ant-...")
    print(f"  python3 agent.py {rerun_hint} [--save]")
    print("=" * 80)


def _build_event_bus(save: bool, run_name: str) -> EventBus:
    bus = EventBus()
    audit = AuditLogListener(AI_USAGE_LOG)
    bus.subscribe(AnalysisCompleted, audit.on_completed)
    bus.subscribe(AnalysisBlocked, audit.on_blocked)
    bus.subscribe(OutOfScopeRequestRejected, audit.on_rejected)
    bus.subscribe(PromptInjectionDetected, audit.on_injection_detected)
    if save:
        writer = OutputWriterListener(OUTPUTS_DIR, run_name)
        bus.subscribe(AnalysisCompleted, writer.on_completed)
    return bus


def _run_analysis(
    run_name: str,
    cr_text: str,
    label: str,
    rerun_hint: str,
    dry_run: bool,
    save: bool,
    requirement_id: Optional[str],
) -> bool:
    """Shared validate -> aggregate -> (maybe) LLM -> event path for both --test and --file.

    `run_name` doubles as change_request_id and the --save output-file stem.
    `label`/`rerun_hint` only feed the dry-run banner (print_dry_run) — the
    two callers differ only in where cr_text/run_name/requirement_id come
    from (a TEST_CASES fixture vs. a user-supplied file).
    """
    if dry_run:
        print_dry_run(label, SYSTEM_PROMPT, build_user_prompt(cr_text), rerun_hint)
        return True

    try:
        llm = get_llm_gateway()
    except ValueError as e:  # unknown LLM_PROVIDER
        print(f"❌ {e}", file=sys.stderr)
        return False

    if not llm.is_available():
        print(f"❌ {type(llm).__name__} not available — missing package or API key.", file=sys.stderr)
        print("   Check .env (copy .env.example if you haven't) and LLM_PROVIDER.", file=sys.stderr)
        return False

    event_bus = _build_event_bus(save, run_name)
    handler = RequestImpactAnalysisHandler(llm=llm, system_prompt=SYSTEM_PROMPT, event_bus=event_bus)

    try:
        print("   🔄 Running RequestImpactAnalysisHandler...")
        result = handler.handle(
            RequestImpactAnalysisCommand(
                change_request_id=run_name,
                change_request_text=cr_text,
                # Never fabricated: TBD in the audit log unless the caller
                # actually supplies an upstream REQ-ID — see spec/traceability.md.
                requirement_id=requirement_id,
            )
        )
    except Exception as e:  # API errors, network errors, etc.
        print(f"❌ Analysis failed: {e}", file=sys.stderr)
        return False

    return _render_result(result.analysis, run_name, save)


def run_test(
    test_name: str, dry_run: bool = False, save: bool = False, requirement_id: Optional[str] = None
) -> bool:
    """Run a single test case through the RequestImpactAnalysis slice."""

    if test_name not in TEST_CASES:
        print(f"❌ Unknown test: {test_name}", file=sys.stderr)
        return False

    print(f"\n📋 Running: {TEST_CASES[test_name]['name']}")
    print(f"   {TEST_CASES[test_name]['description']}")

    test_input = load_test_input(test_name)
    if test_input is None:
        return False

    return _run_analysis(
        run_name=test_name,
        cr_text=test_input,
        label=TEST_CASES[test_name]["name"],
        rerun_hint=f"--test {test_name}",
        dry_run=dry_run,
        save=save,
        # --requirement-id CLI flag wins; otherwise fall back to a TEST_CASES
        # entry if one's been added. No real requirement ticket behind the
        # built-in fixtures — see spec/traceability.md. Never fabricate one.
        requirement_id=requirement_id or TEST_CASES[test_name].get("requirement_id"),
    )


def load_custom_input(file_path: Path) -> Optional[str]:
    """Load CR text from a user-supplied file (--file) — not a TEST_CASES fixture."""
    if not file_path.exists():
        print(f"❌ Input file not found: {file_path}", file=sys.stderr)
        return None

    return file_path.read_text(encoding="utf-8")


def run_file(
    file_path: Path,
    dry_run: bool = False,
    save: bool = False,
    requirement_id: Optional[str] = None,
    change_request_id: Optional[str] = None,
) -> bool:
    """Run RequestImpactAnalysis against a real, user-supplied CR file (--file).

    Same validate -> aggregate -> (maybe) LLM -> event path as run_test — the
    only difference is where the CR text comes from. change_request_id
    defaults to the file's stem so --save output filenames stay predictable.
    """
    run_name = change_request_id or file_path.stem
    print(f"\n📋 Running: Custom CR — {file_path}")

    cr_text = load_custom_input(file_path)
    if cr_text is None:
        return False

    return _run_analysis(
        run_name=run_name,
        cr_text=cr_text,
        label=f"Custom CR — {file_path.name}",
        rerun_hint=f"--file {file_path}",
        dry_run=dry_run,
        save=save,
        requirement_id=requirement_id,
    )


def _render_result(analysis, test_name: str, save: bool) -> bool:
    print(f"   REQ-ID: {analysis.requirement_id or 'TBD'}  |  CR-ID: {analysis.id.value}")

    if analysis.status == AnalysisStatus.BLOCKED:
        print(f"   ⚠️  BLOCKED — {analysis.status_reason}")
        print("   ✓ No API call made — validation caught this before the model was called")
        return True

    if analysis.status == AnalysisStatus.REJECTED:
        print(f"   🚫 REJECTED — {analysis.status_reason}")
        return True

    # COMPLETED
    draft = analysis.draft
    if analysis.injection_details:
        print(f"   ⚠️  Prompt injection marker(s) detected: {', '.join(analysis.injection_details)}")
        print("   ✓ Proceeding with honest analysis anyway (not suppressed)")

    print("   ✓ Analysis complete")
    print(f"     - Assumptions: {draft.assumptions_count}")
    print(f"     - Questions: {draft.questions_count}")
    print(f"     - Risks: {draft.risks_count}")
    print(f"     - Recommendation: {draft.recommendation.value if draft.recommendation else 'UNSPECIFIED'}")

    if save:
        print(f"   ✓ Output saved: {OUTPUTS_DIR / f'run-{test_name}.md'}")
    else:
        preview = draft.content[:500] + "..." if len(draft.content) > 500 else draft.content
        print()
        print("OUTPUT PREVIEW (first 500 chars):")
        print("-" * 80)
        print(preview)
        print("-" * 80)

    return True


def run_all_tests(dry_run: bool = False, save: bool = False, requirement_id: Optional[str] = None) -> dict:
    """Run all test cases."""

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_suite": "Architecture Impact Analyzer",
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "results": [],
    }

    test_names = ["normal", "incomplete", "out_of_scope", "missing_source"]

    for test_name in test_names:
        results["total_tests"] += 1
        success = run_test(test_name, dry_run=dry_run, save=save, requirement_id=requirement_id)

        results["results"].append(
            {
                "test": test_name,
                "name": TEST_CASES[test_name]["name"],
                "status": "PASSED" if success else "FAILED",
            }
        )

        if success:
            results["passed"] += 1
        else:
            results["failed"] += 1

    if save:
        results_file = EVIDENCE_DIR / f"test-results-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
        results_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\n✓ Test results saved: {results_file}")

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total: {results['total_tests']}")
    print(f"Passed: {results['passed']} ✓")
    print(f"Failed: {results['failed']} ✗")
    print("=" * 80)

    return results


# ============================================================================
# Main
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Architecture Impact Analyzer (AIA) — Solution Architect Agent"
    )
    parser.add_argument(
        "--test",
        default=None,
        help="Built-in fixture test case to run (normal, incomplete, out_of_scope, "
        "missing_source, all). Mutually exclusive with --file.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Path to a Markdown/text file with your own Change Request — analyze "
        "real input instead of a built-in fixture. Mutually exclusive with --test.",
    )
    parser.add_argument(
        "--change-request-id",
        default=None,
        help="ID for the analysis when using --file (defaults to the file's stem).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without calling API")
    parser.add_argument("--save", action="store_true", help="Save output to files")
    parser.add_argument(
        "--requirement-id",
        default=None,
        help="Upstream REQ-ID to trace this run to (spec/traceability.md). "
        "Omit to log 'TBD' — never fabricated.",
    )

    args = parser.parse_args()

    if not args.test and not args.file:
        parser.error("one of --test or --file is required")
    if args.test and args.file:
        parser.error("--test and --file are mutually exclusive — pick one")

    if args.file:
        success = run_file(
            args.file,
            dry_run=args.dry_run,
            save=args.save,
            requirement_id=args.requirement_id,
            change_request_id=args.change_request_id,
        )
        sys.exit(0 if success else 1)
    elif args.test == "all":
        results = run_all_tests(dry_run=args.dry_run, save=args.save, requirement_id=args.requirement_id)
        sys.exit(0 if results["failed"] == 0 else 1)
    else:
        success = run_test(
            args.test, dry_run=args.dry_run, save=args.save, requirement_id=args.requirement_id
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
