"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/networking_static_route.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List

import bleach
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.network.static_route import (
    StaticRouteCreate,
    StaticRouteUpsert,
    StaticRoute,
    StaticRouteDelete
)
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.utils.validators import (
    clean_var,
    validate_network,
    normalize_network,
    validate_ip
)

router = APIRouter()


@router.post("", status_code=201)
def create_static_route(
        *,
        route_in: StaticRouteCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Define a new static IPv4/IPv6 route.
    """
    if not validate_network(route_in.to):
        suggestion = normalize_network(route_in.to)
        msg = "Invalid destination network (CIDR)."
        if suggestion:
            msg += f" Host bits are set; did you mean '{suggestion}'?"
        raise HTTPException(status_code=400, detail=msg)

    if not validate_ip(route_in.via):
        raise HTTPException(status_code=400, detail="Invalid gateway IP address (via).")

    try:
        route_in.to = clean_var(route_in.to)
        route_in.via = bleach.clean(route_in.via or "")
        route_in.device = bleach.clean(route_in.device or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Input sanitization failed: {str(e)}")

    try:
        crud.static_route.create(db=db, obj_in=route_in)
        return schedule_task(db, background_tasks, f"Add static route to {route_in.to}", True)
    except Exception as e:
        Logger.logger.error(f"Failed to create static route: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error configuring static route.")


@router.put("", status_code=201)
def upsert_static_route_entry(
        *,
        route_in: StaticRouteUpsert,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Update an existing route (identified by the current triplet) or create it.
    """
    for net_field, val in [("current", route_in.current_to), ("new", route_in.new_to)]:
        if not validate_network(val):
            suggestion = normalize_network(val)
            msg = f"Invalid {net_field} destination network."
            if suggestion:
                msg += f" Host bits are set; did you mean '{suggestion}'?"
            raise HTTPException(status_code=400, detail=msg)

    if not validate_ip(route_in.current_via) or not validate_ip(route_in.new_via):
        raise HTTPException(status_code=400, detail="Invalid gateway IP address.")

    try:
        current_to = clean_var(route_in.current_to)
        new_to = clean_var(route_in.new_to)

        c_via = bleach.clean(route_in.current_via or "")
        c_dev = bleach.clean(route_in.current_device or "")
        n_via = bleach.clean(route_in.new_via or "")
        n_dev = bleach.clean(route_in.new_device or "")

        crud.static_route.upsert_by_triplet(
            db=db,
            current_to=current_to, current_via=c_via, current_device=c_dev,
            new_to=new_to, new_via=n_via, new_device=n_dev,
        )

        task_msg = f"Update static route {current_to} → {new_to} via {n_via}"
        return schedule_task(db, background_tasks, task_msg, True)

    except Exception as e:
        Logger.logger.error(f"Static route upsert failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error updating static route.")


@router.get("", status_code=200, response_model=List[StaticRoute])
def get_static_routes(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[StaticRoute]:
    """
    Retrieve all configured static routes.
    """
    try:
        return crud.static_route.export(db=db)
    except Exception as e:
        Logger.logger.error(f"Failed to fetch static routes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error retrieving route list.")


@router.delete("", status_code=200)
def delete_static_route(
        *,
        body: StaticRouteDelete,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Remove a static route based on its unique Destination/Gateway/Device triplet.
    """
    try:
        deleted = crud.static_route.delete(
            db=db,
            to=body.to,
            via=body.via,
            device=body.device
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Static Route not found.")

        return schedule_task(
            db, background_tasks,
            f"Delete static route {body.to} via {body.via}",
            True
        )
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Static route deletion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error deleting static route.")
