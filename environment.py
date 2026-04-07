"""
Lead-Ops · Environment Controller
===================================
Implementation of the LeadOpsEnv and fundamental API methods:
reset(), step(), and state().
"""

from __future__ import annotations

import random
from typing import Any

from sqlalchemy.orm import Session as DBSession

from models import (
    TaskID, LeadObservation, Action, StepResult, Reward, RewardComponent,
    ToolName, get_default_available_actions
)
from db_models import LeadORM
from session_manager import SessionManager
from grader import Grader
from actions import execute_action

class LeadOpsEnv:
    """Core OpenEnv API for Lead-Ops."""
    
    def __init__(self, session_manager: SessionManager):
        self.sm = session_manager

    def reset(self, task_id: TaskID) -> tuple[str, LeadObservation]:
        """
        Creates a new isolated session and selects a target lead.
        """
        session_id = self.sm.create_session()
        db = self.sm.get_db_session(session_id)
        
        # Select target lead based on task type
        # In a real environment we might filter by is_dirty, or specific task logic.
        # For simplicity, pick a random lead that has interactions if meddic_qualify, 
        # or a random lead if enrich_lead.
        lead = db.query(LeadORM).order_by(LeadORM.id).offset(random.randint(0, 49)).first()
        if not lead:
            raise RuntimeError("Database contains no leads!")

        # Store the target lead ID inside session info to persist across steps
        info = self.sm.get_session_info(session_id)
        # Using a monkeypatch hack since SessionInfo dataclass doesn't have target_lead_id
        # Alternatively we can fetch it dynamically or just assume the first lead queried is target.
        # Let's attach it safely if possible
        setattr(info, "target_lead_id", lead.id)
        setattr(info, "task_id", task_id)
        
        obs = self._build_observation(lead, task_id)
        db.close()
        return session_id, obs

    def step(self, session_id: str, action: Action) -> StepResult:
        """
        Executes an action, applying it to the database, and computes reward.
        """
        db = self.sm.get_db_session(session_id)
        info = self.sm.get_session_info(session_id)
        
        target_lead_id = getattr(info, "target_lead_id", 1)
        task_id = getattr(info, "task_id", TaskID.ENRICH_LEAD)
        lead = db.query(LeadORM).filter_by(id=target_lead_id).first()
        
        if not lead:
             db.close()
             raise ValueError(f"Target lead {target_lead_id} missing in session DB.")

        if getattr(info, "step_rewards_accum", None) is None:
            setattr(info, "step_rewards_accum", 0.0)
            
        # Snapshot state before action
        old_fields = {c.name: getattr(lead, c.name) for c in lead.__table__.columns}

        # 1. Execute action
        metadata = execute_action(db, lead, action, task_id)

        # Snapshot state after action and evaluate modifiers
        db.refresh(lead)
        new_fields = {c.name: getattr(lead, c.name) for c in lead.__table__.columns}
        step_comps = Grader.evaluate_step_updates(old_fields, new_fields, lead.company_name)
        
        step_reward_delta = sum(c.value for c in step_comps)
        info.step_rewards_accum += step_reward_delta

        # Increment step count
        step_idx = self.sm.increment_step(session_id)

        # 2. Check if terminal
        is_done = False
        if action.tool_name in [ToolName.ROUTE_TO_AE, ToolName.DISQUALIFY]:
            is_done = True
            
        if step_idx >= 15:
            is_done = True

        if action.tool_name == ToolName.UPDATE_LEAD and task_id == TaskID.ENRICH_LEAD:
            is_done = True
            
        if lead.status == "disqualified":
            is_done = True

        # 3. Compute Reward
        if is_done:
            reward = Grader.grade_task(task_id, db, lead, step_idx, info.step_rewards_accum)
        else:
            # Intermediate step penalty + partial progress updates
            step_comps.insert(0, RewardComponent(
                name="intermediate_step_penalty",
                value=Grader.STEP_PENALTY,
                weight=1.0,
                reason="Standard penalty for taking an action."
            ))
            step_total = max(-1.0, min(1.0, Grader.STEP_PENALTY + step_reward_delta))
            
            reward = Reward(
                task_id=task_id,
                total=step_total,
                components=step_comps,
                message="Intermediate step completed.",
                done=False
            )

        # 4. Refresh observation
        obs = self._build_observation(lead, task_id)
        
        db.close()
        
        if is_done:
            self.sm.destroy_session(session_id)

        return StepResult(
            step_number=step_idx,
            observation=obs,
            action=action,
            reward=reward,
            metadata=metadata
        )

    def state(self, session_id: str) -> dict[str, Any]:
        """Provides full snapshot of the database state."""
        info = self.sm.get_session_info(session_id)
        # Using simple size tracking for now
        db_size_kb = info.db_path.stat().st_size / 1024 if info.db_path.exists() else 0
        return {
            "session_id": session_id,
            "is_active": info.is_active,
            "step_count": info.step_count,
            "age_seconds": info.age_seconds,
            "database_size_kb": db_size_kb
        }

    def _build_observation(self, lead: LeadORM, task_id: TaskID) -> LeadObservation:
        from models import MEDDICScores, RoutingResult
        
        meddic = None
        if task_id in [TaskID.MEDDIC_QUALIFY, TaskID.STRATEGIC_ROUTE]:
            meddic = MEDDICScores(
                metrics=lead.meddic_metrics or 0.0,
                economic_buyer=lead.meddic_economic_buyer or 0.0,
                decision_criteria=lead.meddic_decision_criteria or 0.0,
                decision_process=lead.meddic_decision_process or 0.0,
                identify_pain=lead.meddic_identify_pain or 0.0,
                champion=lead.meddic_champion or 0.0,
            )
            
        routing = None
        if lead.assigned_ae:
            routing = RoutingResult(
                assigned_ae=lead.assigned_ae,
                team="Unknown",
                region=lead.territory,
                routing_reason=lead.routing_reason or "Assigned",
                confidence=1.0
            )
            
        return LeadObservation(
            lead_id=str(lead.id),
            company_name=lead.company_name,
            industry=lead.industry,
            annual_revenue=lead.annual_revenue,
            employee_count=lead.employee_count,
            website=lead.website,
            contact_name=lead.contact_name,
            contact_title=lead.contact_title,
            contact_email=lead.contact_email,
            contact_linkedin=lead.contact_linkedin,
            tech_stack=lead.tech_stack,
            lead_source=lead.lead_source,
            enrichment_data=lead.enrichment_data,
            meddic_scores=meddic,
            routing_result=routing,
            available_actions=get_default_available_actions(task_id)
        )
