# -*- coding: utf-8 -*-
"""灏忎笐绀惧尯 API 璺敱锛氳处鍙枫€佹帓琛屾涓庤瘎璁恒€?
璇诲彇锛堟鍗曘€佽瘎璁猴級涓嶉渶瑕佺櫥褰曪紱鍐欏叆锛堜笂浼犲皬涓戝€笺€佸彂琛ㄨ瘎璁猴級闇€瑕佸厛鐧诲綍銆?"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from typing import Optional

from app.api.deps import get_auth_store, get_leaderboard_store, require_user
from app.schemas import auth as auth_schemas
from app.schemas import leaderboard as schemas
from app.services.auth import AuthError

router = APIRouter(prefix="/api/community", tags=["灏忎笐绀惧尯"])


def get_leaderboard():
    """鑾峰彇鎺掕姒滃疄渚嬶紙杩涚▼绾у崟渚嬶紝鐩綍鍙 JOKER_PROFILE_DIR 瑕嗙洊锛夈€?""
    return get_leaderboard_store()


# ------------------------------------------------------------ 璐﹀彿

@router.post("/auth/register", response_model=auth_schemas.AuthResponse)
async def register(body: auth_schemas.RegisterInput):
    """娉ㄥ唽骞剁洿鎺ョ櫥褰曘€傚瘑鐮佷负 6 浣嶆暟瀛楋紝闇€閫夋嫨澶村儚绫诲瀷銆?""
    try:
        return get_auth_store().register(body.username, body.password, body.avatar_type)
    except AuthError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post("/auth/login", response_model=auth_schemas.AuthResponse)
async def login(body: auth_schemas.Credentials):
    """鐧诲綍锛岃繑鍥炰細璇?token銆?""
    username = body.username
    password = body.password
    try:
        return get_auth_store().login(username, password)
    except AuthError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(default=None)):
    """閫€鍑虹櫥褰曪細浣滃簾褰撳墠 token銆?""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    get_auth_store().logout(token)
    return {"ok": True}


@router.get("/auth/me")
async def me(authorization: Optional[str] = Header(default=None)):
    """杩斿洖褰撳墠鐧诲綍鐢ㄦ埛锛涙湭鐧诲綍杩斿洖 {username: null}銆?""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    current = get_auth_store().verify(token)
    return {"username": current}


# ------------------------------------------------------------ 姒滃崟锛堣鍙栵級

@router.get("/avatars")
async def avatar_options():
    """杩斿洖鍙€夌殑澶村儚鍒楄〃銆?""
    from app.services.auth import AVATAR_TYPES
    return {"avatars": list(AVATAR_TYPES)}


@router.get("/leaderboard")
async def get_ranking(
    limit: int = Query(default=50, ge=1, le=200, description="杩斿洖鏉＄洰鏁伴噺"),
    offset: int = Query(default=0, ge=0, description="鍋忕Щ閲?)
):
    """鑾峰彇鎺掕姒滐紙鎸夊垎鏁伴檷搴忥級銆?""
    service = get_leaderboard()
    entries = service.get_leaderboard(limit, offset)
    
    # 鑾峰彇姣忎釜鏉＄洰鐨勭敤鎴峰ご鍍忕被鍨?    auth_store = get_auth_store()
    usernames = [e["user_name"] for e in entries]
    avatars = auth_store.get_avatars(usernames)
    for entry in entries:
        entry["avatar_type"] = avatars.get(entry["user_name"], "娈夐亾鍨?)
    
    return {"entries": entries}


@router.get("/entries/{entry_id}")
async def get_entry_detail(entry_id: int):
    """鑾峰彇鏌愭潯鎺掕姒滆褰曠殑璇︽儏銆?""
    service = get_leaderboard()
    entry = service.get_entry(entry_id)
    if not entry:
        raise HTTPException(404, "鎺掕姒滄潯鐩笉瀛樺湪")
    
    # 娣诲姞澶村儚淇℃伅
    auth_store = get_auth_store()
    user_info = auth_store.get_user_info(entry["user_name"])
    if user_info:
        entry["avatar_type"] = user_info["avatar_type"]
    else:
        entry["avatar_type"] = "娈夐亾鍨?
    
    return entry


@router.get("/entries/{entry_id}/comments")
async def get_entry_comments(entry_id: int):
    """鑾峰彇鏌愭潯璁板綍鐨勬墍鏈夎瘎璁恒€?""
    service = get_leaderboard()
    comments = service.get_comments(entry_id)
    return {"comments": comments}


# ------------------------------------------------------------ 姒滃崟锛堝啓鍏ワ紝闇€鐧诲綍锛?
@router.post("/submit")
async def submit_score(body: schemas.ScoreSubmitInput, username: str = Depends(require_user)):
    """涓婁紶灏忎笐鍊煎埌鎺掕姒溿€傛樀绉板彇鑷櫥褰曡处鍙枫€?""
    service = get_leaderboard()
    entry_id = service.submit_entry(username, body.score, body.joker_type)
    return {"entry_id": entry_id, "username": username}


@router.post("/comments")
async def add_comment(body: schemas.CommentInput, username: str = Depends(require_user)):
    """鍙戣〃璇勮銆傛樀绉板彇鑷櫥褰曡处鍙枫€?""
    service = get_leaderboard()
    try:
        comment_id = service.add_comment(body.entry_id, username, body.content)
        return {"comment_id": comment_id, "username": username}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: int, username: str = Depends(require_user)):
    """鍒犻櫎璇勮锛堜粎浣滆€呮湰浜哄彲鍒狅級銆?""
    service = get_leaderboard()
    comment = service.get_comment(comment_id)
    if not comment:
        raise HTTPException(404, "璇勮涓嶅瓨鍦?)
    if comment["user_name"] != username:
        raise HTTPException(403, "鍙兘鍒犻櫎鑷繁鐨勮瘎璁?)
    service.delete_comment(comment_id)
    return {"deleted": True}
