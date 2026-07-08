from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from api.support import require_admin
from services.vwh_temp_mail_service import VwhTempMailClient


class VwhTempMailRequest(BaseModel):
    api_base: str


class VwhTempMailInboxRequest(VwhTempMailRequest):
    email: str


class VwhTempMailMessageRequest(VwhTempMailRequest):
    message_id: str


def _client(api_base: str) -> VwhTempMailClient:
    try:
        return VwhTempMailClient(api_base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


def _handle_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail={"error": str(exc)})


def create_router() -> APIRouter:
    router = APIRouter()

    @router.post("/api/temp-mail/vwh/health")
    async def check_health(body: VwhTempMailRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            return {"result": await run_in_threadpool(_client(body.api_base).health)}
        except Exception as exc:
            raise _handle_error(exc) from exc

    @router.post("/api/temp-mail/vwh/domains")
    async def list_domains(body: VwhTempMailRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            return {"items": await run_in_threadpool(_client(body.api_base).domains)}
        except Exception as exc:
            raise _handle_error(exc) from exc

    @router.post("/api/temp-mail/vwh/messages")
    async def list_messages(body: VwhTempMailInboxRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            messages = await run_in_threadpool(_client(body.api_base).list_messages, body.email)
            return {"items": [message.raw for message in messages]}
        except Exception as exc:
            raise _handle_error(exc) from exc

    @router.post("/api/temp-mail/vwh/message")
    async def get_message(body: VwhTempMailMessageRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            return {"item": await run_in_threadpool(_client(body.api_base).get_message, body.message_id)}
        except Exception as exc:
            raise _handle_error(exc) from exc

    return router
