#!/usr/bin/env python3
"""
Lead-Ops · Compliance Checker
==============================
Validates the project structure and schemas against the OpenEnv manifest.

Usage::

    python check_compliance.py

Exit codes:
    0  — all checks passed
    1  — one or more checks failed
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import yaml

# ── Constants ─────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
REQUIRED_FILES = [
    "openenv.yaml",
    "models.py",
    "config.py",
    "requirements.txt",
    "README.md",
    ".env.example",
    ".gitignore",
    "server/app.py",
]

REQUIRED_MANIFEST_KEYS = {"spec_version", "name", "version", "tasks"}
REQUIRED_TASK_KEYS = {"id", "description", "reward_range"}
EXPECTED_TASKS = {"enrich_lead", "meddic_qualify", "strategic_route"}

# ── Styling ───────────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

PASS = f"{GREEN}✔ PASS{RESET}"
FAIL = f"{RED}✘ FAIL{RESET}"
WARN = f"{YELLOW}⚠ WARN{RESET}"


def _header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}")


# ── Checks ────────────────────────────────────────────────────────────────────

class ComplianceChecker:
    """Runs a suite of structural and schema checks."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def _record(self, ok: bool, label: str, detail: str = "") -> bool:
        if ok:
            self.passed += 1
            print(f"  {PASS}  {label}")
        else:
            self.failed += 1
            msg = f"  {FAIL}  {label}"
            if detail:
                msg += f"  →  {detail}"
            print(msg)
        return ok

    def _warn(self, label: str, detail: str = "") -> None:
        self.warnings += 1
        msg = f"  {WARN}  {label}"
        if detail:
            msg += f"  →  {detail}"
        print(msg)

    # ── 1. File existence ─────────────────────────────────────────────────

    def check_files_exist(self) -> bool:
        _header("1 · File Structure")
        all_ok = True
        for rel in REQUIRED_FILES:
            path = PROJECT_ROOT / rel
            ok = path.exists()
            self._record(ok, f"{rel}", "" if ok else "file not found")
            all_ok = all_ok and ok
        return all_ok

    # ── 2. openenv.yaml ──────────────────────────────────────────────────

    def check_manifest(self) -> dict | None:
        _header("2 · OpenEnv Manifest (openenv.yaml)")
        manifest_path = PROJECT_ROOT / "openenv.yaml"

        if not manifest_path.exists():
            self._record(False, "openenv.yaml exists", "file missing")
            return None

        try:
            with open(manifest_path) as f:
                manifest = yaml.safe_load(f)
            self._record(True, "Valid YAML syntax")
        except yaml.YAMLError as exc:
            self._record(False, "Valid YAML syntax", str(exc))
            return None

        for key in REQUIRED_MANIFEST_KEYS:
            self._record(
                key in manifest,
                f"Top-level key '{key}'",
                "missing" if key not in manifest else "",
            )

        version = manifest.get("version", "")
        self._record(
            version == "1.0.0",
            f"Version is '1.0.0'",
            f"got '{version}'" if version != "1.0.0" else "",
        )

        tasks = manifest.get("tasks", [])
        self._record(
            isinstance(tasks, list) and len(tasks) == 3,
            f"Exactly 3 tasks defined",
            f"found {len(tasks) if isinstance(tasks, list) else 'non-list'}",
        )

        task_ids = set()
        for task in tasks if isinstance(tasks, list) else []:
            tid = task.get("id", "<missing>")
            task_ids.add(tid)
            for key in REQUIRED_TASK_KEYS:
                self._record(
                    key in task,
                    f"Task '{tid}' has key '{key}'",
                    "missing" if key not in task else "",
                )

        self._record(
            task_ids == EXPECTED_TASKS,
            "Task IDs match expected set",
            f"got {task_ids}" if task_ids != EXPECTED_TASKS else "",
        )

        return manifest

    # ── 3. Pydantic models ───────────────────────────────────────────────

    def check_models(self) -> bool:
        _header("3 · Pydantic V2 Models (models.py)")

        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))

        try:
            models = importlib.import_module("models")
            self._record(True, "models.py imports successfully")
        except Exception as exc:
            self._record(False, "models.py imports successfully", str(exc))
            return False

        # Check expected classes
        expected_classes = [
            "LeadObservation",
            "SearchAction",
            "UpdateAction",
            "Reward",
            "MEDDICScores",
            "StepResult",
            "RoutingResult",
            "RewardComponent",
            "AvailableAction",
        ]
        all_ok = True
        for cls_name in expected_classes:
            cls = getattr(models, cls_name, None)
            ok = cls is not None
            self._record(ok, f"Class '{cls_name}' defined", "" if ok else "not found")
            all_ok = all_ok and ok

        # Check enums
        expected_enums = ["ToolName", "TaskID", "LeadSource", "ActionType"]
        for enum_name in expected_enums:
            enum_cls = getattr(models, enum_name, None)
            ok = enum_cls is not None
            self._record(ok, f"Enum '{enum_name}' defined", "" if ok else "not found")
            all_ok = all_ok and ok

        # Check Action is a union type
        action_type = getattr(models, "Action", None)
        self._record(
            action_type is not None,
            "Action union type defined",
            "" if action_type is not None else "not found",
        )

        # Instantiation — LeadObservation with available_actions
        try:
            available = models.get_default_available_actions(models.TaskID.ENRICH_LEAD)
            obs = models.LeadObservation(
                company_name="Acme Corp",
                available_actions=available,
            )
            self._record(True, "LeadObservation instantiates with available_actions")
            self._record(
                len(obs.available_actions) > 0,
                f"available_actions has {len(obs.available_actions)} tools for enrich_lead",
            )
            self._record(
                hasattr(obs, "completeness"),
                "LeadObservation has 'completeness' property",
            )
        except Exception as exc:
            self._record(False, "LeadObservation instantiates", str(exc))
            all_ok = False

        # Instantiation — SearchAction (CoT)
        try:
            act = models.SearchAction(
                thought="I need to search for company firmographic data to enrich the lead.",
                tool_name="tavily_search",
                query="Acme Corp revenue employees",
            )
            self._record(True, "SearchAction instantiates with CoT")
            self._record(
                act.action_type == "search",
                "SearchAction.action_type == 'search'",
            )
        except Exception as exc:
            self._record(False, "SearchAction instantiates with CoT", str(exc))
            all_ok = False

        # Instantiation — UpdateAction
        try:
            act = models.UpdateAction(
                thought="Setting annual revenue based on web search results from Tavily.",
                tool_name="update_lead",
                field_updates={"annual_revenue": 50_000_000, "industry": "FinTech"},
                reason="Confirmed via Crunchbase and public filings",
            )
            self._record(True, "UpdateAction instantiates with field_updates")
            self._record(
                act.action_type == "update",
                "UpdateAction.action_type == 'update'",
            )
        except Exception as exc:
            self._record(False, "UpdateAction instantiates", str(exc))
            all_ok = False

        # CoT validation rejects short thoughts
        try:
            models.SearchAction(
                thought="ok",
                tool_name="tavily_search",
                query="test",
            )
            self._record(False, "SearchAction rejects too-short CoT", "should have raised")
            all_ok = False
        except Exception:
            self._record(True, "SearchAction rejects too-short CoT thought")

        # Reward
        try:
            reward = models.Reward(
                task_id="enrich_lead",
                total=0.85,
                components=[
                    models.RewardComponent(
                        name="data_completeness", value=0.9, weight=0.5
                    )
                ],
            )
            self._record(True, "Reward instantiates with components")
        except Exception as exc:
            self._record(False, "Reward instantiates", str(exc))
            all_ok = False

        # MEDDIC composite score
        try:
            meddic = models.MEDDICScores(
                metrics=0.8,
                economic_buyer=0.6,
                decision_criteria=0.7,
                decision_process=0.5,
                identify_pain=0.9,
                champion=0.3,
            )
            score = meddic.composite_score
            self._record(
                0.0 <= score <= 1.0,
                f"MEDDICScores.composite_score = {score:.3f}",
            )
        except Exception as exc:
            self._record(False, "MEDDICScores.composite_score", str(exc))
            all_ok = False

        # Token count check — observation under 4k tokens (~16k chars)
        try:
            available = models.get_default_available_actions(models.TaskID.ENRICH_LEAD)
            obs = models.LeadObservation(
                company_name="Acme Corp",
                industry="FinTech",
                annual_revenue=50_000_000,
                employee_count=500,
                website="https://acme.com",
                contact_name="Jane Doe",
                contact_title="VP Sales",
                contact_email="jane@acme.com",
                available_actions=available,
            )
            obs_json = obs.model_dump_json()
            char_count = len(obs_json)
            # Rough estimate: 1 token ≈ 4 chars
            token_estimate = char_count // 4
            ok = token_estimate < 4000
            self._record(
                ok,
                f"Observation ~{token_estimate} tokens (< 4k limit, {char_count} chars)",
                f"too large: ~{token_estimate} tokens" if not ok else "",
            )
        except Exception as exc:
            self._record(False, "Observation token count", str(exc))
            all_ok = False

        return all_ok

    # ── 4. Config ────────────────────────────────────────────────────────

    def check_config_module(self) -> bool:
        _header("4 · Configuration (config.py)")

        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))

        config_path = PROJECT_ROOT / "config.py"
        try:
            source = config_path.read_text()
            compile(source, str(config_path), "exec")
            self._record(True, "config.py is valid Python syntax")
        except SyntaxError as exc:
            self._record(False, "config.py syntax", str(exc))
            return False

        required_vars = ["HF_TOKEN", "API_BASE_URL", "TAVILY_API_KEY"]
        for var in required_vars:
            ok = var in source
            self._record(ok, f"config.py references '{var}'", "" if ok else "missing")

        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            self._record(True, ".env file exists")
            # Check .env has the right variable names
            env_content = env_file.read_text()
            for var in required_vars:
                ok = var in env_content
                self._record(ok, f".env contains '{var}'", "" if ok else "missing")
        else:
            self._warn(
                ".env file not found",
                "Copy .env.example → .env and fill in your secrets",
            )

        return True

    # ── 5. Requirements ──────────────────────────────────────────────────

    def check_requirements(self) -> bool:
        _header("5 · Dependencies (requirements.txt)")
        req_path = PROJECT_ROOT / "requirements.txt"

        if not req_path.exists():
            self._record(False, "requirements.txt exists")
            return False

        content = req_path.read_text()
        expected_packages = [
            "fastapi",
            "uvicorn",
            "pydantic",
            "sqlalchemy",
            "tavily-python",
            "python-dotenv",
            "httpx",
            "pyyaml",
        ]
        all_ok = True
        for pkg in expected_packages:
            ok = pkg in content
            self._record(ok, f"Package '{pkg}' listed", "" if ok else "missing")
            all_ok = all_ok and ok

        lines = [
            l.strip()
            for l in content.splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
        pinned = all("==" in l for l in lines)
        self._record(pinned, "All packages have pinned versions (==)")

        return all_ok

    # ── 6. Available Actions per task ─────────────────────────────────────

    def check_available_actions(self) -> bool:
        _header("6 · Available Actions (anti-hallucination)")

        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))

        try:
            models = importlib.import_module("models")
        except Exception as exc:
            self._record(False, "models import", str(exc))
            return False

        all_ok = True
        for task_id in models.TaskID:
            actions = models.get_default_available_actions(task_id)
            ok = len(actions) > 0
            tool_names = [a.tool_name.value for a in actions]
            self._record(
                ok,
                f"Task '{task_id.value}' → {len(actions)} tools: {tool_names}",
            )
            all_ok = all_ok and ok

            # Verify each action has a type (search or update)
            for a in actions:
                ok = a.action_type in ("search", "update")
                self._record(
                    ok,
                    f"  {a.tool_name.value} → type='{a.action_type.value}'",
                )
                all_ok = all_ok and ok

        return all_ok

    # ── Run all ───────────────────────────────────────────────────────────

    def run(self) -> int:
        print(f"\n{BOLD}🔍  Lead-Ops · Phase 1 Compliance Check{RESET}")
        print(f"   Project root: {PROJECT_ROOT}\n")

        self.check_files_exist()
        self.check_manifest()
        self.check_models()
        self.check_config_module()
        self.check_requirements()
        self.check_available_actions()

        # ── Summary ───────────────────────────────────────────────────────
        _header("Summary")
        total = self.passed + self.failed
        print(f"  {GREEN}{self.passed}{RESET}/{total} checks passed")
        if self.failed:
            print(f"  {RED}{self.failed}{RESET} checks failed")
        if self.warnings:
            print(f"  {YELLOW}{self.warnings}{RESET} warnings")

        if self.failed == 0:
            print(f"\n  {GREEN}{BOLD}✔  ALL CHECKS PASSED — Phase 1 is compliant.{RESET}\n")
        else:
            print(f"\n  {RED}{BOLD}✘  {self.failed} CHECK(S) FAILED — see above.{RESET}\n")

        return 0 if self.failed == 0 else 1


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    checker = ComplianceChecker()
    sys.exit(checker.run())
