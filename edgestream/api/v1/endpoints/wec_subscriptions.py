"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/wec_subscriptions.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from edgestream.wec.models import SubscriptionRow, SubscriptionPayload
from edgestream.wec.service import WecService
from edgestream.core.config import Logger

router = APIRouter()


def get_wec_service() -> WecService:
    """
    Dependency provider for the WEC Service.
    Resolves the standalone SQLite database used by the pywec collector.
    """
    db_url = os.getenv("WEC_DB_URL", "/var/lib/pywec/pywec.db")

    # Ensure standard SQLAlchemy connection string format
    if "://" not in db_url:
        # SQLite absolute path requires 4 slashes: sqlite:////path/to/db
        prefix = "sqlite:////" if db_url.startswith("/") else "sqlite:///"
        db_url = f"{prefix}{db_url.lstrip('/')}"

    return WecService(db_url)


def _raise_wec_not_configured(e: Exception) -> None:
    """
    Normalizes downstream WEC service errors.
    If the DB file is missing or unreadable, we report 503 (Service Unavailable).
    """
    msg = str(getattr(e, "orig", e)).lower()
    Logger.logger.error(f"WEC Service connectivity error: {msg}")

    if "unable to open database file" in msg or "no such table" in msg:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "WEC_NOT_CONFIGURED",
                "message": "The Windows Event Collector service is not initialized or configured.",
            },
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="The WEC service encountered an internal database error."
    )


@router.get("/", response_model=List[SubscriptionRow])
async def list_subscriptions(svc: WecService = Depends(get_wec_service)):
    """Retrieve all active Windows Event Collector subscriptions."""
    try:
        return await svc.list()
    except OperationalError as e:
        _raise_wec_not_configured(e)
    except Exception as e:
        Logger.logger.error(f"WEC list failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching WEC subscriptions."
        )


@router.post("/", response_model=SubscriptionRow, status_code=status.HTTP_201_CREATED)
async def create_subscription(
        payload: SubscriptionPayload,
        svc: WecService = Depends(get_wec_service)
):
    """Register a new Windows Event Subscription (WEC)."""
    try:
        return await svc.create(payload)
    except ValidationError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Subscription validation failed: {ve.errors()}"
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid subscription parameters: {str(e)}"
        )
    except OperationalError as e:
        _raise_wec_not_configured(e)
    except Exception as e:
        Logger.logger.error(f"WEC creation failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during subscription creation."
        )


@router.put("/{sub_id}", response_model=SubscriptionRow)
async def update_subscription(
        sub_id: int,
        payload: SubscriptionPayload,
        svc: WecService = Depends(get_wec_service)
):
    """Modify an existing WEC subscription."""
    try:
        return await svc.update(sub_id, payload)
    except ValidationError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid subscription updates."
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription ID {sub_id} not found."
        )
    except OperationalError as e:
        _raise_wec_not_configured(e)
    except Exception as e:
        Logger.logger.error(f"WEC update failure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error updating subscription.")


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(sub_id: int, svc: WecService = Depends(get_wec_service)):
    """Permanently remove a WEC subscription."""
    try:
        await svc.delete(sub_id)
        return
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription ID {sub_id} not found."
        )
    except OperationalError as e:
        _raise_wec_not_configured(e)
    except Exception as e:
        Logger.logger.error(f"WEC deletion failure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error deleting subscription.")
