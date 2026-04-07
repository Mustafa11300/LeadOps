"""
Lead-Ops · Action Implementations
===================================
Executes the tools selected by the RL agent and modifies the session database.
"""

from __future__ import annotations

import json
from typing import Any
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from models import Action, SearchAction, UpdateAction, ToolName, TaskID
from db_models import LeadORM, InteractionLogORM, EnrichmentCacheORM
import config

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

settings = config.settings

def execute_action(db: DBSession, lead: LeadORM, action: Action, task_id: TaskID) -> dict[str, Any]:
    """Routes the action to the appropriate implementation."""
    
    if action.action_type == "search":
        return _execute_search(db, lead, action)
    elif action.action_type == "update":
        return _execute_update(db, lead, action)
    
    return {"status": "error", "message": "Unknown action type."}

def _execute_search(db: DBSession, lead: LeadORM, action: SearchAction) -> dict[str, Any]:
    tool = action.tool_name
    
    if tool == ToolName.TAVILY_SEARCH:
        return _search_tavily(db, lead, action.query, action.filters)
    
    elif tool == ToolName.CRM_LOOKUP:
        return _search_crm(db, lead, action.query)
        
    elif tool == ToolName.LINKEDIN_ENRICH:
        return _search_tavily(db, lead, f"{action.query} site:linkedin.com/in/", action.filters)
        
    return {"status": "error", "message": f"Search tool {tool} not implemented."}

def _execute_update(db: DBSession, lead: LeadORM, action: UpdateAction) -> dict[str, Any]:
    tool = action.tool_name
    
    if tool == ToolName.UPDATE_LEAD:
        updates = action.field_updates
        lead.update_fields(updates)
        db.commit()
        return {"status": "success", "message": f"Lead updated with fields: {list(updates.keys())}"}
        
    elif tool == ToolName.SCORE_MEDDIC:
        updates = action.field_updates
        # Ensure we map explicitly to meddic_ prefixed columns
        meddic_updates = {}
        for k, v in updates.items():
            col_name = f"meddic_{k}" if not k.startswith("meddic_") else k
            if hasattr(lead, col_name) and isinstance(v, (int, float)):
                meddic_updates[col_name] = float(v)
        
        lead.update_fields(meddic_updates)
        db.commit()
        return {"status": "success", "message": f"MEDDIC scores updated."}
        
    elif tool == ToolName.ROUTE_TO_AE:
        updates = action.field_updates
        ae = updates.get("assigned_ae", "unknown")
        territory = updates.get("region") or updates.get("territory") or "Unknown"
        lead.update_territory(territory=territory, assigned_ae=ae, reason=action.reason)
        db.commit()
        return {"status": "success", "message": f"Lead routed to {ae} in {territory}."}
        
    elif tool == ToolName.DISQUALIFY:
        lead.status = "disqualified"
        lead.routing_reason = action.reason
        db.commit()
        return {"status": "success", "message": "Lead disqualified."}

    return {"status": "error", "message": f"Update tool {tool} not implemented."}


def _search_tavily(db: DBSession, lead: LeadORM, query: str, filters: dict) -> dict[str, Any]:
    """Executes a real Tavily web search and caches the result."""
    # Check cache first
    cached = db.query(EnrichmentCacheORM).filter_by(lead_id=lead.id, source="tavily", query=query).first()
    if cached:
        return {"cached": True, "result": cached.payload}
        
    if not TavilyClient or not settings.TAVILY_API_KEY or "xxxxxxxx" in settings.TAVILY_API_KEY:
        return {"error": "Tavily API key not configured or package missing."}
        
    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    try:
        response = client.search(
            query=query, 
            search_depth="basic",
            max_results=filters.get("max_results", 3)
        )
        
        # Summarize for the agent
        results = response.get("results", [])
        summary = [{"title": r.get("title"), "content": r.get("content")} for r in results]
        
        # Cache it
        cache_entry = EnrichmentCacheORM(
            lead_id=lead.id,
            source="tavily",
            query=query,
            payload_json=json.dumps(summary)
        )
        db.add(cache_entry)
        db.commit()
        
        return {"cached": False, "result": summary}
        
    except Exception as e:
        return {"error": str(e)}

def _search_crm(db: DBSession, target_lead: LeadORM, query: str) -> dict[str, Any]:
    """Retrieves CRM records and Interaction Logs for the MEDDIC task."""
    # We ignore the specific query and return the target lead's context 
    # to maintain the single-episode focus.
    
    logs = db.query(InteractionLogORM).filter_by(lead_id=target_lead.id).order_by(InteractionLogORM.timestamp.asc()).all()
    
    log_data = []
    for log in logs:
        log_data.append({
            "timestamp": log.timestamp.isoformat(),
            "direction": log.direction,
            "type": log.log_type,
            "subject": log.subject,
            "body": log.body,
        })
        
    return {
        "status": "success",
        "message": f"Found {len(logs)} chronological interaction logs.",
        "interaction_logs": log_data
    }
