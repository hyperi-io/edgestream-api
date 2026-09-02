"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/update.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from edgestream.models.system.user import User
from edgestream.core.config import Logger
from edgestream.schemas.system.update import UpdatesAvailable
from edgestream.services.apt_helpers import (
    get_apt_available_packages,
    RootHelperPrivilegeError,
    apt_update_packagelist,
    RootHelperExecutionError,
    RootHelperNotFound,
    upgrade_packages
)
from edgestream.services.auth.auth import get_current_user

router = APIRouter()

def ensure_admin(current_user: User):
    """
    Gaurdrails for privileged operations. 
    Verifies the is_superuser boolean from our refactored User model.
    """
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Administrative privileges are required to manage system packages."
        )

@router.get("", status_code=status.HTTP_200_OK, response_model=UpdatesAvailable)
def fetch_upgradable_packages(
    current_user: User = Depends(get_current_user),
) -> UpdatesAvailable:
    """
    Retrieve the list of packages currently marked as upgradable in the local cache.
    Note: This does not require root privileges.
    """
    ensure_admin(current_user)
    try:
        packages = get_apt_available_packages()
        return UpdatesAvailable(packages=packages)
    except Exception as error:
        Logger.logger.error(f"Failed to fetch upgradable packages: {error}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, 
            detail="Unable to list upgradable packages at this time."
        )

@router.get("/refresh", status_code=status.HTTP_200_OK, response_model=UpdatesAvailable)
def refresh_package_cache(
    current_user: User = Depends(get_current_user),
) -> UpdatesAvailable:
    """
    Triggers 'apt-get update' (requires root escalation) and returns the new package list.
    """
    ensure_admin(current_user)
    try:
        apt_update_packagelist() 
        packages = get_apt_available_packages()
        return UpdatesAvailable(packages=packages)

    except RootHelperPrivilegeError as e:
        Logger.logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Permission Denied: The privileged helper is blocked by system security policy "
                "(e.g., NoNewPrivileges=true). Check service security overrides."
            ),
        )
    except RootHelperNotFound as e:
        Logger.logger.error(f"System Update Error (Helper Missing): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal configuration error: Privileged update helper not found."
        )
    except RootHelperExecutionError as e:
        Logger.logger.error(f"APT execution failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Package cache refresh failed. Consult system logs for APT error details.",
        )
    except Exception as error:
        Logger.logger.error(f"Unexpected error in refresh_package_cache: {error}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="An unexpected error occurred while refreshing the package cache."
        )

@router.put("", status_code=status.HTTP_200_OK, response_model=UpdatesAvailable)
def run_package_updates(
    packages_in: List[str],
    current_user: User = Depends(get_current_user),
) -> UpdatesAvailable:
    """
    Upgrade a specific list of packages (requires root escalation).
    """
    ensure_admin(current_user)
    if not packages_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No packages provided for upgrade."
        )

    try:
        upgrade_packages(packages_in)
        packages = get_apt_available_packages()
        return UpdatesAvailable(packages=packages)

    except ValueError as ve:
        Logger.logger.error(f"Validation error during upgrade: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid package selection: {str(ve)}"
        )
    except (RootHelperPrivilegeError, RootHelperNotFound, RootHelperExecutionError) as e:
        Logger.logger.error(f"Escalation error during upgrade: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="System upgrade failed. The update helper encountered an error."
        )
    except Exception as error:
        Logger.logger.error(f"Unexpected failure during update_packages: {error}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="System upgrade failed due to an unexpected internal error."
        )
