from fastapi import APIRouter, HTTPException

from .. import repo


router = APIRouter(prefix="/api", tags=["conversations"])


@router.get("/conversations")
async def list_conversations(limit: int = 100) -> dict:
    return {"items": await repo.list_conversations(limit=limit)}


@router.get("/conversations/{phone}")
async def get_conversation(phone: str) -> dict:
    conv = await repo.get_conversation_by_phone(phone)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    messages = await repo.list_messages(conv["id"])
    calls = await repo.list_calls_for_conversation(conv["id"])
    return {"conversation": conv, "messages": messages, "calls": calls}


@router.get("/calls")
async def list_calls(limit: int = 100) -> dict:
    return {"items": await repo.list_calls(limit=limit)}
