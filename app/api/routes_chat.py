from fastapi import APIRouter, Depends, HTTPException
from app.services.chat_service import ChatService
from app.api.dependencies import get_current_user, get_chat_service

router = APIRouter()

@router.post("/")
async def chat(
    message: str,
    thread_id: str,
    current_user=Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    if hasattr(chat_service, "process_message_with_metadata"):
        response = await chat_service.process_message_with_metadata(
            user_id=current_user.id,
            thread_id=thread_id,
            message=message,
        )
        if isinstance(response, dict) and "response" in response:
            return response

    response_text = await chat_service.process_message(
        user_id=current_user.id,
        thread_id=thread_id,
        message=message,
    )
    return {"response": response_text}
