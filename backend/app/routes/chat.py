import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import ai


logger = logging.getLogger("crewloop.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])


class Turn(BaseModel):
    role: str = Field(..., pattern="^(user|model|assistant)$")
    text: str


class Attachment(BaseModel):
    mime_type: str
    data: str  # base64-encoded bytes
    name: str | None = None


class ChatRequest(BaseModel):
    turns: list[Turn] = Field(..., min_length=1)
    attachments: list[Attachment] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
async def chat_with_loop(payload: ChatRequest) -> ChatResponse:
    turns = [{"role": "user" if t.role != "model" else "model", "text": t.text} for t in payload.turns]
    attachments = [a.model_dump() for a in payload.attachments]
    try:
        reply = await ai.generate_chat_reply(turns, attachments=attachments or None)
    except Exception:
        logger.exception("chat reply failed")
        raise HTTPException(status_code=502, detail="Loop couldn't reach Gemini")
    if not reply:
        raise HTTPException(status_code=502, detail="Loop returned no reply")
    return ChatResponse(reply=reply)
