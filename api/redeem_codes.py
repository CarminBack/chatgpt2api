from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from api.support import require_admin, require_identity
from services.redeem_code_service import RedeemCodeError, redeem_code_service


class RedeemCodeCreateRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=500)
    image_quota: int = Field(default=1, ge=1)
    expires_at: str | None = None
    prefix: str = "RC"


class RedeemCodeVerifyRequest(BaseModel):
    code: str = ""


class RedeemCodeRedeemRequest(BaseModel):
    code: str = ""


class RedeemCodeUpdateRequest(BaseModel):
    enabled: bool | None = None


def _profile_payload(item: dict[str, object]) -> dict[str, object]:
    image_quota = max(0, int(item.get("image_quota") or 0))
    image_used = max(0, int(item.get("image_used") or 0))
    image_remaining = max(0, image_quota - image_used) if image_quota > 0 else None
    return {
        "role": item.get("role"),
        "subject_id": item.get("id"),
        "name": item.get("name"),
        "image_quota": image_quota,
        "image_used": image_used,
        "image_remaining": image_remaining,
    }


def _handle_redeem_error(exc: RedeemCodeError) -> None:
    raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/redeem-codes")
    async def list_redeem_codes(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"items": redeem_code_service.list_codes()}

    @router.post("/api/redeem-codes")
    async def create_redeem_codes(body: RedeemCodeCreateRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            items = redeem_code_service.create_codes(
                count=body.count,
                image_quota=body.image_quota,
                expires_at=body.expires_at,
                prefix=body.prefix,
            )
        except RedeemCodeError as exc:
            _handle_redeem_error(exc)
        return {"items": items, "all_items": redeem_code_service.list_codes()}

    @router.post("/api/redeem-codes/verify")
    async def verify_redeem_code(body: RedeemCodeVerifyRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            return redeem_code_service.verify_code(body.code)
        except RedeemCodeError as exc:
            _handle_redeem_error(exc)

    @router.post("/api/redeem-codes/redeem")
    async def redeem_code(body: RedeemCodeRedeemRequest, authorization: str | None = Header(default=None)):
        identity = require_identity(authorization)
        try:
            result = redeem_code_service.redeem(body.code, identity)
        except RedeemCodeError as exc:
            _handle_redeem_error(exc)
        return {
            "ok": True,
            "item": result["item"],
            "image_quota_added": result["image_quota_added"],
            "profile": _profile_payload(result["profile"]),
        }

    @router.post("/api/redeem-codes/{code_id}")
    async def update_redeem_code(code_id: str, body: RedeemCodeUpdateRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        if body.enabled is None:
            raise HTTPException(status_code=400, detail={"error": "还没有检测到改动，请修改后再保存"})
        item = redeem_code_service.set_enabled(code_id, body.enabled)
        if item is None:
            raise HTTPException(status_code=404, detail={"error": "兑换码不存在，可能已经被删除"})
        return {"item": item, "items": redeem_code_service.list_codes()}

    return router
