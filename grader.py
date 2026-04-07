"""
Lead-Ops · Programmatic Graders & Rewards
=========================================
100% Python-based deterministic scoring.
"""

from __future__ import annotations

import json
import re
from typing import Any
from sqlalchemy.orm import Session as DBSession

from models import TaskID, Reward, RewardComponent
from db_models import LeadORM, InteractionLogORM

def load_ground_truth() -> list[dict]:
    import os
    from pathlib import Path
    data_path = Path(__file__).resolve().parent / "data" / "solutions.json"
    if not data_path.exists():
        return []
    with open(data_path) as f:
        return json.load(f)

GROUND_TRUTH = {entry["company"].lower(): entry for entry in load_ground_truth()}

def _fuzzy_match_string(a: str | None, b: str | None) -> bool:
    """Ignore case, punctuation, and leading/trailing whitespace."""
    if a is None or b is None:
        return False
    clean_a = re.sub(r'[^a-z0-9]', '', a.lower().strip())
    clean_b = re.sub(r'[^a-z0-9]', '', b.lower().strip())
    return clean_a == clean_b

def _fuzzy_match_url(url_a: str | None, url_b: str | None) -> bool:
    """Ignore https://, www., and trailing slashes."""
    if url_a is None or url_b is None:
        return False
    def clean_url(u: str) -> str:
        u = u.lower().strip()
        u = re.sub(r'^https?://', '', u)
        u = re.sub(r'^www\.', '', u)
        u = re.sub(r'linkedin\.com/in/', '', u)
        u = u.rstrip('/')
        return u
    return clean_url(url_a) == clean_url(url_b)


class Grader:
    """Deterministic grading engine."""
    
    # ── Step Penalties / Rewards ──────────────────────────────────────────────
    
    STEP_PENALTY = -0.02
    PARTIAL_PROGRESS_REWARD = 0.1
    DESTRUCTIVE_PENALTY = -0.5

    @classmethod
    def evaluate_step_updates(cls, old_fields: dict, new_fields: dict, company_name: str) -> list[RewardComponent]:
        """
        Calculates partial progress or destructive penalties mid-episode.
        Used by environment.py inside step().
        """
        components = []
        gt = GROUND_TRUTH.get(company_name.lower().strip())
        
        for field, old_val in old_fields.items():
            new_val = new_fields.get(field)
            if old_val == new_val:
                continue
                
            # Destructive Action: Nullifying previously populated vital data
            if old_val is not None and old_val != "" and (new_val is None or new_val == ""):
                components.append(RewardComponent(
                    name="destructive_penalty",
                    value=cls.DESTRUCTIVE_PENALTY,
                    weight=1.0,
                    reason=f"Agent deleted valuable data from field '{field}'."
                ))
            
            # Partial Progress: Successfully inserting valid data towards ground truth
            elif gt:
                if field in gt:
                    gt_val = gt[field]
                    if field == "website" or "url" in field or "linkedin" in field:
                        if _fuzzy_match_url(new_val, str(gt_val)):
                            components.append(RewardComponent(
                                name="partial_progress",
                                value=cls.PARTIAL_PROGRESS_REWARD,
                                weight=1.0,
                                reason=f"Correctly enriched {field}."
                            ))
                    elif isinstance(new_val, str):
                        if _fuzzy_match_string(new_val, str(gt_val)):
                            components.append(RewardComponent(
                                name="partial_progress",
                                value=cls.PARTIAL_PROGRESS_REWARD,
                                weight=1.0,
                                reason=f"Correctly enriched {field}."
                            ))
                    elif isinstance(new_val, (int, float)) and isinstance(gt_val, (int, float)):
                        if abs(new_val - gt_val) / max(gt_val, 1) <= 0.1:
                            components.append(RewardComponent(
                                name="partial_progress",
                                value=cls.PARTIAL_PROGRESS_REWARD,
                                weight=1.0,
                                reason=f"Correctly enriched {field}."
                            ))
                            
        return components

    # ── Final Graders ─────────────────────────────────────────────────────────

    @classmethod
    def grade_task(
        cls, 
        task_id: TaskID, 
        db: DBSession, 
        lead: LeadORM, 
        step_count: int,
        step_rewards: float = 0.0 # Accumulated partial progress / destructive penalties
    ) -> Reward:
        if task_id == TaskID.ENRICH_LEAD:
            return cls._grade_task_1(lead, step_count, step_rewards)
        elif task_id == TaskID.MEDDIC_QUALIFY:
            return cls._grade_task_2(db, lead, step_count, step_rewards)
        elif task_id == TaskID.STRATEGIC_ROUTE:
            return cls._grade_task_3(db, lead, step_count, step_rewards)
        
        return Reward(task_id=task_id, total=0.0, message="Unknown task", done=True)

    @staticmethod
    def _apply_modifiers(base_score: float, step_count: int, step_rewards: float) -> tuple[float, list[RewardComponent]]:
        comps = []
        
        # Step Penalty
        penalty = step_count * Grader.STEP_PENALTY
        comps.append(RewardComponent(
            name="efficiency_penalty", value=penalty, weight=1.0,
            reason=f"{step_count} steps taken."
        ))
        
        # Step Rewards (accumulated from state transitions)
        if step_rewards != 0.0:
            comps.append(RewardComponent(
                name="step_modifiers", value=step_rewards, weight=1.0,
                reason="Accumulated partial progress and destructive penalties."
            ))
            
        final = max(0.0, min(1.0, base_score + penalty + step_rewards))
        return final, comps

    @classmethod
    def _grade_task_1(cls, lead: LeadORM, step_count: int, step_rewards: float) -> Reward:
        """
        Task 1 Grader (Easy): Grade based on linkedin_url and job_title match.
        """
        components = []
        company_key = lead.company_name.lower().strip()
        gt = GROUND_TRUTH.get(company_key)
        
        if not gt:
            return Reward(task_id=TaskID.ENRICH_LEAD, total=0.0, 
                          message="No ground truth available for company.", done=True)

        # 50% for contact_linkedin, 50% for contact_title
        linkedin_score = 0.5 if _fuzzy_match_url(lead.contact_linkedin, gt.get("contact_linkedin")) else 0.0
        title_score = 0.5 if _fuzzy_match_string(lead.contact_title, gt.get("contact_title")) else 0.0
        
        base_score = linkedin_score + title_score
        
        components.append(RewardComponent(name="linkedin_match", value=linkedin_score, weight=0.5, reason="Fuzzy matched linkedin profile."))
        components.append(RewardComponent(name="title_match", value=title_score, weight=0.5, reason="Fuzzy matched job title."))

        final_total, mods = cls._apply_modifiers(base_score, step_count, step_rewards)
        components.extend(mods)

        return Reward(
            task_id=TaskID.ENRICH_LEAD, total=final_total, components=components,
            message="Task 1 (Easy) Grader completed.", done=True
        )

    @classmethod
    def _grade_task_2(cls, db: DBSession, lead: LeadORM, step_count: int, step_rewards: float) -> Reward:
        """
        Task 2 Grader (Medium): Economic_Buyer (60%) and Pain (40%).
        """
        components = []
        # Find hidden true signals
        logs = db.query(InteractionLogORM).filter_by(lead_id=lead.id).all()
        true_eb = 0.0
        true_pain = 0.0
        for log in logs:
            if log.meddic_signal == "economic_buyer" and log.signal_strength:
                true_eb = max(true_eb, log.signal_strength)
            if log.meddic_signal == "identify_pain" and log.signal_strength:
                true_pain = max(true_pain, log.signal_strength)

        # Agent signals
        agent_eb = lead.meddic_economic_buyer or 0.0
        agent_pain = lead.meddic_identify_pain or 0.0

        eb_accuracy = max(0.0, 1.0 - abs(agent_eb - true_eb))
        pain_accuracy = max(0.0, 1.0 - abs(agent_pain - true_pain))

        base_score = (eb_accuracy * 0.6) + (pain_accuracy * 0.4)
        
        components.append(RewardComponent(name="eb_accuracy", value=eb_accuracy * 0.6, weight=0.6, reason="Economic Buyer evaluation vs logs."))
        components.append(RewardComponent(name="pain_accuracy", value=pain_accuracy * 0.4, weight=0.4, reason="Identify Pain evaluation vs logs."))

        final_total, mods = cls._apply_modifiers(base_score, step_count, step_rewards)
        components.extend(mods)

        return Reward(
            task_id=TaskID.MEDDIC_QUALIFY, total=final_total, components=components,
            message="Task 2 (Medium) Grader completed.", done=True
        )

    @classmethod
    def _grade_task_3(cls, db: DBSession, lead: LeadORM, step_count: int, step_rewards: float) -> Reward:
        """
        Task 3 Grader (Hard): Enrichment + MEDDIC + Routing. Success = 0.8+
        """
        company_key = lead.company_name.lower().strip()
        gt = GROUND_TRUTH.get(company_key)

        # 1. Enrichment (30%)
        enrichment_score = 0.0
        if gt:
            target_rev = gt.get("annual_revenue")
            if target_rev and lead.annual_revenue:
                if abs(lead.annual_revenue - target_rev) / max(target_rev, 1) <= 0.1:
                    enrichment_score = 1.0

        # 2. MEDDIC completeness safely (30%)
        # Just check if all pillars are scored somewhat
        meddic_fields = [
            lead.meddic_metrics, lead.meddic_economic_buyer, lead.meddic_decision_criteria,
            lead.meddic_decision_process, lead.meddic_identify_pain, lead.meddic_champion
        ]
        meddic_score = sum(1 for f in meddic_fields if f is not None) / 6.0

        # 3. Routing Accuracy (40%)
        routing_score = 0.0
        if gt:
            if lead.assigned_ae == gt.get("correct_ae"):
                routing_score = 1.0
            elif lead.territory == gt.get("correct_territory"):
                routing_score = 0.5  # Partial

        base_score = (enrichment_score * 0.3) + (meddic_score * 0.3) + (routing_score * 0.4)

        components = [
            RewardComponent(name="enrich_accuracy", value=enrichment_score*0.3, weight=0.3),
            RewardComponent(name="meddic_completeness", value=meddic_score*0.3, weight=0.3),
            RewardComponent(name="routing_accuracy", value=routing_score*0.4, weight=0.4),
        ]

        final_total, mods = cls._apply_modifiers(base_score, step_count, step_rewards)
        components.extend(mods)

        # Append Success Tag
        msg = "Task 3 (Hard) Grader completed."
        if final_total >= 0.8:
            msg += " [SUCCESS]"

        return Reward(
            task_id=TaskID.STRATEGIC_ROUTE, total=final_total, components=components,
            message=msg, done=True
        )
