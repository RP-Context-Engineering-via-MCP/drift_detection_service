"""
Behavior and Conflict data models.

These represent the local projections of behaviors and conflicts
stored in the drift service's own database (read model).
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class BehaviorRecord:
    """
    Local projection of a behavior stored in behavior_snapshots table.
    Populated from behavior.* events — never read from Behavior Service DB.
    """
    
    user_id: str
    behavior_id: str
    target: str
    intent: str  # PREFERENCE | CONSTRAINT | HABIT | SKILL | COMMUNICATION
    context: str  # backend | frontend | general | IDE | ...
    polarity: str  # POSITIVE | NEGATIVE
    credibility: float  # 0.0 – 1.0
    reinforcement_count: int
    state: str  # ACTIVE | SUPERSEDED
    created_at: int  # unix timestamp
    last_seen_at: int  # unix timestamp
    snapshot_updated_at: int  # when this row was last touched by an event
    
    def __post_init__(self):
        """Validate field values after initialization."""
        # Validate credibility
        if not 0.0 <= self.credibility <= 1.0:
            raise ValueError(f"Credibility must be between 0.0 and 1.0, got {self.credibility}")
        
        # Validate reinforcement count
        if self.reinforcement_count < 0:
            raise ValueError(f"Reinforcement count cannot be negative, got {self.reinforcement_count}")
        
        # Validate state
        if self.state not in ["ACTIVE", "SUPERSEDED"]:
            raise ValueError(f"State must be ACTIVE or SUPERSEDED, got {self.state}")
        
        # Validate polarity
        if self.polarity not in ["POSITIVE", "NEGATIVE"]:
            raise ValueError(f"Polarity must be POSITIVE or NEGATIVE, got {self.polarity}")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BehaviorRecord":
        """
        Create BehaviorRecord from dictionary (e.g., database row).
        
        Args:
            data: Dictionary containing behavior data
            
        Returns:
            BehaviorRecord instance
        """
        return cls(
            user_id=data["user_id"],
            behavior_id=data["behavior_id"],
            target=data["target"],
            intent=data["intent"],
            context=data["context"],
            polarity=data["polarity"],
            credibility=float(data["credibility"]),
            reinforcement_count=int(data["reinforcement_count"]),
            state=data["state"],
            created_at=int(data["created_at"]),
            last_seen_at=int(data["last_seen_at"]),
            snapshot_updated_at=int(data["snapshot_updated_at"]),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert BehaviorRecord to dictionary for database insertion.
        
        Returns:
            Dictionary representation
        """
        return {
            "user_id": self.user_id,
            "behavior_id": self.behavior_id,
            "target": self.target,
            "intent": self.intent,
            "context": self.context,
            "polarity": self.polarity,
            "credibility": self.credibility,
            "reinforcement_count": self.reinforcement_count,
            "state": self.state,
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
            "snapshot_updated_at": self.snapshot_updated_at,
        }
    
    @property
    def is_active(self) -> bool:
        """Check if behavior is currently active."""
        return self.state == "ACTIVE"
    
    @property
    def is_superseded(self) -> bool:
        """Check if behavior has been superseded."""
        return self.state == "SUPERSEDED"
    
    @property
    def created_datetime(self) -> datetime:
        """Get created_at as datetime object."""
        return datetime.fromtimestamp(self.created_at)
    
    @property
    def last_seen_datetime(self) -> datetime:
        """Get last_seen_at as datetime object."""
        return datetime.fromtimestamp(self.last_seen_at)
    
    def __repr__(self) -> str:
        return (
            f"BehaviorRecord(user_id={self.user_id!r}, behavior_id={self.behavior_id!r}, "
            f"target={self.target!r}, intent={self.intent}, polarity={self.polarity}, "
            f"reinforcement={self.reinforcement_count}, state={self.state})"
        )


@dataclass
class ConflictRecord:
    """
    Local projection of a resolved conflict stored in conflict_snapshots table.
    Populated from behavior.conflict.resolved events.
    """
    
    user_id: str
    conflict_id: str
    behavior_id_1: str
    behavior_id_2: str
    conflict_type: str  # RESOLVABLE | USER_DECISION_NEEDED
    resolution_status: str  # AUTO_RESOLVED | PENDING | USER_RESOLVED
    old_polarity: Optional[str]  # For preference reversals
    new_polarity: Optional[str]
    old_target: Optional[str]  # For target migrations
    new_target: Optional[str]
    created_at: int  # unix timestamp
    
    def __post_init__(self):
        """Validate field values after initialization."""
        # Validate conflict type
        valid_types = ["RESOLVABLE", "USER_DECISION_NEEDED"]
        if self.conflict_type not in valid_types:
            raise ValueError(f"Conflict type must be one of {valid_types}, got {self.conflict_type}")
        
        # Validate resolution status
        valid_statuses = ["AUTO_RESOLVED", "PENDING", "USER_RESOLVED"]
        if self.resolution_status not in valid_statuses:
            raise ValueError(f"Resolution status must be one of {valid_statuses}, got {self.resolution_status}")
        
        # Validate polarities if present
        if self.old_polarity and self.old_polarity not in ["POSITIVE", "NEGATIVE"]:
            raise ValueError(f"Old polarity must be POSITIVE or NEGATIVE, got {self.old_polarity}")
        if self.new_polarity and self.new_polarity not in ["POSITIVE", "NEGATIVE"]:
            raise ValueError(f"New polarity must be POSITIVE or NEGATIVE, got {self.new_polarity}")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConflictRecord":
        """
        Create ConflictRecord from dictionary (e.g., database row).
        
        Args:
            data: Dictionary containing conflict data
            
        Returns:
            ConflictRecord instance
        """
        return cls(
            user_id=data["user_id"],
            conflict_id=data["conflict_id"],
            behavior_id_1=data["behavior_id_1"],
            behavior_id_2=data["behavior_id_2"],
            conflict_type=data["conflict_type"],
            resolution_status=data["resolution_status"],
            old_polarity=data.get("old_polarity"),
            new_polarity=data.get("new_polarity"),
            old_target=data.get("old_target"),
            new_target=data.get("new_target"),
            created_at=int(data["created_at"]),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ConflictRecord to dictionary for database insertion.
        
        Returns:
            Dictionary representation
        """
        return {
            "user_id": self.user_id,
            "conflict_id": self.conflict_id,
            "behavior_id_1": self.behavior_id_1,
            "behavior_id_2": self.behavior_id_2,
            "conflict_type": self.conflict_type,
            "resolution_status": self.resolution_status,
            "old_polarity": self.old_polarity,
            "new_polarity": self.new_polarity,
            "old_target": self.old_target,
            "new_target": self.new_target,
            "created_at": self.created_at,
        }
    
    @property
    def is_polarity_reversal(self) -> bool:
        """Check if this conflict represents a polarity reversal."""
        return (
            self.old_polarity is not None 
            and self.new_polarity is not None 
            and self.old_polarity != self.new_polarity
        )
    
    @property
    def is_target_migration(self) -> bool:
        """Check if this conflict represents a target migration."""
        return (
            self.old_target is not None 
            and self.new_target is not None 
            and self.old_target != self.new_target
        )
    
    @property
    def created_datetime(self) -> datetime:
        """Get created_at as datetime object."""
        return datetime.fromtimestamp(self.created_at)
    
    def __repr__(self) -> str:
        return (
            f"ConflictRecord(user_id={self.user_id!r}, conflict_id={self.conflict_id!r}, "
            f"type={self.conflict_type}, status={self.resolution_status}, "
            f"polarity_reversal={self.is_polarity_reversal})"
        )
