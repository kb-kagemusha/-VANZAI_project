"""Search only; venue addresses from POI lookup are not persisted as Google content."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from src.api.jwt_auth import get_current_active_user
from src.models.master import User
from src.services.google_places import configured, search_places
from src.services.order_request_service import OrderRequestError
from collections import defaultdict, deque
from threading import Lock
from time import monotonic

router = APIRouter(prefix="/api/places", tags=["Places"])
_searches = defaultdict(deque)
_search_lock = Lock()


def throttle(user_id):
    # Per API process/user. Explicit click only; no charged requests while typing.
    with _search_lock:
        moment = monotonic()
        for key in list(_searches):
            if not _searches[key] or _searches[key][-1] <= moment - 60:
                del _searches[key]
        recent = _searches[user_id]
        while recent and recent[0] <= moment - 60:
            recent.popleft()
        if len(recent) >= 10:
            raise HTTPException(429, "検索が続いています。1分ほど待ってから再検索してください")
        recent.append(moment)


def ensure(user):
    if user.role not in ("admin", "ops"):
        raise HTTPException(403, "所在地検索の権限がありません")


@router.get("/status")
def status(response: Response, current_user: User = Depends(get_current_active_user)):
    ensure(current_user)
    response.headers["Cache-Control"] = "no-store"
    return {"configured": configured()}


@router.get("/search")
def search(response: Response, query: str = Query(min_length=2, max_length=200), current_user: User = Depends(get_current_active_user)):
    ensure(current_user)
    response.headers["Cache-Control"] = "no-store"
    if not query.strip():
        raise HTTPException(400, "会場名を入力してください")
    throttle(current_user.id)
    try:
        return {"items": search_places(query.strip())}
    except OrderRequestError as exc:
        raise HTTPException(exc.status_code, exc.detail) from None
