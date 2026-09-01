"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/event_routing.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.services.auth.auth import get_current_user

router = APIRouter()


@router.get("", status_code=200, response_model=List[str])
def get_routing_labels(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[str]:
    """
    Fetch all unique event route labels from sources and include internal system labels.

    Returns:
        A list of unique route labels including 'internal.log' and 'internal.metric'.
    """
    try:
        routing_labels = crud.source.get_all_sources(db=db)

        routing_labels.extend(["internal.log", "internal.metric"])

        unique_labels = sorted(list(set(routing_labels)))

        return unique_labels

    except Exception as e:
        Logger.logger.error(f"Failed to fetch routing labels: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while retrieving route labels."
        )
