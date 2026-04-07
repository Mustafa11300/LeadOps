"""
Lead-Ops · SQLAlchemy ORM Models
=================================
SQLAlchemy 2.0 mapped classes for the Lead-Ops database.

Tables:
    - leads:            CRM lead records with enrichment fields
    - accounts:         Parent company accounts with territory assignment
    - interaction_logs: Email/call/note threads between reps and prospects
    - enrichment_cache: Cached results from external enrichment APIs
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    Session,
)


# ───────────────────────────────────────────────────────────────────────────────
# Base
# ───────────────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ───────────────────────────────────────────────────────────────────────────────
# Accounts (parent company)
# ───────────────────────────────────────────────────────────────────────────────

class AccountORM(Base):
    """
    Parent company account.

    An Account represents the canonical company record and
    holds territory assignment + segmentation info.
    """

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    annual_revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Territory & Segmentation
    segment: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="enterprise | mid_market | smb",
    )
    territory: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="West | East | Central | EMEA",
    )
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    assigned_ae: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
        comment="Account Executive assigned to this account",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )

    # Relationships
    leads: Mapped[list["LeadORM"]] = relationship(
        "LeadORM", back_populates="account", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, company='{self.company_name}', segment='{self.segment}')>"


# ───────────────────────────────────────────────────────────────────────────────
# Leads
# ───────────────────────────────────────────────────────────────────────────────

class LeadORM(Base):
    """
    CRM lead record.

    Contains raw and enriched data about a sales prospect.
    Linked to a parent Account and can have many InteractionLogs.
    """

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)

    # Foreign key to account
    account_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=True,
    )

    # Company Info (may be dirty / incomplete)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    annual_revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Contact Info
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_linkedin: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Enrichment
    tech_stack_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON array of technologies, e.g. [\"Python\", \"AWS\"]",
    )
    lead_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    enrichment_data_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Raw enrichment payload as JSON",
    )

    # MEDDIC Scores (stored as individual columns for query efficiency)
    meddic_metrics: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    meddic_economic_buyer: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    meddic_decision_criteria: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    meddic_decision_process: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    meddic_identify_pain: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    meddic_champion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Routing
    assigned_ae: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    territory: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    routing_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="new",
        comment="new | enriched | qualified | routed | disqualified",
    )
    is_dirty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="Whether this lead has unclean/incomplete data",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )

    # Relationships
    account: Mapped[Optional["AccountORM"]] = relationship(
        "AccountORM", back_populates="leads",
    )
    interaction_logs: Mapped[list["InteractionLogORM"]] = relationship(
        "InteractionLogORM", back_populates="lead", cascade="all, delete-orphan",
    )
    enrichment_cache: Mapped[list["EnrichmentCacheORM"]] = relationship(
        "EnrichmentCacheORM", back_populates="lead", cascade="all, delete-orphan",
    )

    # ── Helpers ───────────────────────────────────────────────────────────

    @property
    def tech_stack(self) -> list[str]:
        """Parse tech_stack_json into a list."""
        if self.tech_stack_json:
            try:
                return json.loads(self.tech_stack_json)
            except json.JSONDecodeError:
                return []
        return []

    @tech_stack.setter
    def tech_stack(self, value: list[str]) -> None:
        self.tech_stack_json = json.dumps(value)

    @property
    def enrichment_data(self) -> dict[str, Any] | None:
        """Parse enrichment_data_json into a dict."""
        if self.enrichment_data_json:
            try:
                return json.loads(self.enrichment_data_json)
            except json.JSONDecodeError:
                return None
        return None

    @enrichment_data.setter
    def enrichment_data(self, value: dict[str, Any]) -> None:
        self.enrichment_data_json = json.dumps(value)

    @property
    def meddic_composite_score(self) -> float | None:
        """Composite MEDDIC score if any pillars are scored."""
        scores = [
            self.meddic_metrics,
            self.meddic_economic_buyer,
            self.meddic_decision_criteria,
            self.meddic_decision_process,
            self.meddic_identify_pain,
            self.meddic_champion,
        ]
        valid = [s for s in scores if s is not None]
        if not valid:
            return None
        return sum(valid) / len(valid)

    def update_fields(self, updates: dict[str, Any]) -> None:
        """Apply a dict of field updates (used by UpdateAction handler)."""
        for key, value in updates.items():
            if key == "tech_stack" and isinstance(value, list):
                self.tech_stack = value
            elif key == "enrichment_data" and isinstance(value, dict):
                self.enrichment_data = value
            elif hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()

    def update_territory(self, territory: str, assigned_ae: str, reason: str) -> None:
        """Update territory assignment with audit trail."""
        self.territory = territory
        self.assigned_ae = assigned_ae
        self.routing_reason = reason
        self.status = "routed"
        self.updated_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<Lead(id={self.id}, company='{self.company_name}', status='{self.status}')>"


# ───────────────────────────────────────────────────────────────────────────────
# Interaction Logs
# ───────────────────────────────────────────────────────────────────────────────

class InteractionLogORM(Base):
    """
    Email, call, or note record between a sales rep and a prospect.

    These logs are the primary data source for MEDDIC qualification —
    the agent must scan them to identify pain points, champions, etc.
    """

    __tablename__ = "interaction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leads.id"), nullable=False,
    )

    log_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="email | call | note",
    )
    direction: Mapped[str] = mapped_column(
        String(20), nullable=False, default="inbound",
        comment="inbound | outbound",
    )
    from_addr: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    to_addr: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # MEDDIC signal metadata (ground truth for grading)
    meddic_signal: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Which MEDDIC pillar this log contains a signal for",
    )
    signal_strength: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="How strong the signal is (0.0–1.0)",
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False,
    )

    # Relationships
    lead: Mapped["LeadORM"] = relationship(
        "LeadORM", back_populates="interaction_logs",
    )

    def __repr__(self) -> str:
        return f"<InteractionLog(id={self.id}, lead_id={self.lead_id}, type='{self.log_type}')>"


# ───────────────────────────────────────────────────────────────────────────────
# Enrichment Cache
# ───────────────────────────────────────────────────────────────────────────────

class EnrichmentCacheORM(Base):
    """
    Cached enrichment results from external APIs.

    Avoids redundant API calls during agent episodes.
    """

    __tablename__ = "enrichment_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leads.id"), nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="tavily | linkedin | crunchbase",
    )
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False,
    )

    # Relationships
    lead: Mapped["LeadORM"] = relationship(
        "LeadORM", back_populates="enrichment_cache",
    )

    @property
    def payload(self) -> dict[str, Any]:
        try:
            return json.loads(self.payload_json)
        except json.JSONDecodeError:
            return {}

    @payload.setter
    def payload(self, value: dict[str, Any]) -> None:
        self.payload_json = json.dumps(value)

    def __repr__(self) -> str:
        return f"<EnrichmentCache(id={self.id}, lead_id={self.lead_id}, source='{self.source}')>"


# ───────────────────────────────────────────────────────────────────────────────
# Engine factory
# ───────────────────────────────────────────────────────────────────────────────

def create_db_engine(db_url: str = "sqlite:///master.db", echo: bool = False):
    """Create a SQLAlchemy engine with WAL mode for SQLite."""
    engine = create_engine(db_url, echo=echo)

    # Enable WAL mode for better concurrent read performance
    if "sqlite" in db_url:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_all_tables(engine) -> None:
    """Create all tables defined in the ORM."""
    Base.metadata.create_all(engine)
