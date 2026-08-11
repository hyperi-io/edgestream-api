import os
import asyncio
import urllib.parse
from typing import List, AsyncIterator, Optional, Set, Dict

import jwt
from jwt.exceptions import PyJWTError
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status, HTTPException
from sqlalchemy.orm import Session
import aiofiles

from edgestream.core.config import settings, Logger
from edgestream import crud
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.services.auth.auth import get_current_user

router = APIRouter()

# Strip non-printable characters to prevent terminal injection/UI garbling
NOPRINT_TRANS_TABLE = {i: None for i in range(0, 128) if not chr(i).isprintable() and i not in (9, 10, 13)}

class ConnectionManager:
    """Manages active WebSocket connections for log streaming."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, websocket: WebSocket, message: str):
        try:
            await websocket.send_text(message)
        except Exception:
            await self.disconnect(websocket)

manager = ConnectionManager()

def make_printable(s: str) -> str:
    """Sanitize strings for safe UI rendering."""
    return s.translate(NOPRINT_TRANS_TABLE)

async def read_last_lines(filename: str, last_lines: int) -> List[str]:
    """Asynchronously reads the tail of a file for the initial backlog."""
    if last_lines <= 0:
        return []
    try:
        async with aiofiles.open(filename, mode="r", encoding="utf-8", errors="replace") as f:
            contents = await f.read()
        lines = contents.splitlines()[-last_lines:]
        return [make_printable(line) for line in lines]
    except Exception as e:
        Logger.logger.error(f"Read error on {filename}: {e}")
        return ["[edgestream] error reading log file"]

async def tail_follow(filename: str) -> AsyncIterator[str]:
    """Continuous async generator that mimics 'tail -f'."""
    try:
        async with aiofiles.open(filename, mode="r", encoding="utf-8", errors="replace") as f:
            await f.seek(0, os.SEEK_END)
            while True:
                line = await f.readline()
                if line:
                    yield make_printable(line.rstrip("\n"))
                else:
                    await asyncio.sleep(0.2) # Polling interval
    except Exception as e:
        Logger.logger.error(f"Follow error on {filename}: {e}")
        yield "[edgestream] connection to log stream interrupted"

async def _authenticate_ws(websocket: WebSocket, token: Optional[str]) -> Optional[Dict]:
    """Strict JWT validation for WebSockets."""
    if not token:
        try:
            # Attempt to receive token from the first message frame
            token = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None

    try:
        return jwt.decode(
            token,
            key=settings.JWT_SECRET,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )
    except PyJWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

@router.websocket("/ws")
async def websocket_endpoint(
        websocket: WebSocket,
        db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time log tailing.
    Supports path resolution, whitelist checking, and JWT auth.
    """
    qp = websocket.query_params
    logfile_raw = qp.get("logfile", "")

    requested_path = os.path.realpath(urllib.parse.unquote(logfile_raw))

    try:
        lines = max(0, min(int(qp.get("lines", "20")), 500))
    except (ValueError, TypeError):
        lines = 20

    try:
        valid_logs: Set[str] = {
            os.path.realpath(log.filename) for log in crud.log_viewer.get_all(db=db)
        }
    except Exception as e:
        Logger.logger.error(f"Failed to fetch log whitelist: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    if requested_path not in valid_logs:
        Logger.logger.warning(f"Unauthorized log access attempt: {requested_path}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Access Denied")
        return

    if not os.path.exists(requested_path) or not os.access(requested_path, os.R_OK):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unreadable Log")
        return

    await websocket.accept()
    claims = await _authenticate_ws(websocket, qp.get("token"))
    if not claims:
        return

    manager.active_connections.append(websocket)
    try:
        if lines > 0:
            backlog = await read_last_lines(requested_path, lines)
            await manager.send_message(websocket, "\n".join(backlog))

        async for line in tail_follow(requested_path):
            await manager.send_message(websocket, line)

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        Logger.logger.error(f"WS Streaming Error on {requested_path}: {e}")
        await manager.disconnect(websocket)

@router.get("", response_model=List[str])
def fetch_available_logs(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[str]:
    """Returns the list of whitelisted log file paths available for viewing."""
    try:
        # Standardized CRUD call
        logs = crud.log_viewer.get_all(db=db)
        return [log.filename for log in logs]
    except Exception as e:
        Logger.logger.error(f"Log list fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error retrieving available logs.")
