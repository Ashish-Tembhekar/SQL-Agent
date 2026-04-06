import json
import asyncio
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.config import validate_config
from backend.app.models import ChatRequest, CommitRequest, RollbackRequest, SessionStatus
from backend.app.agent import invoke_agent, clear_agent
from backend.app.tools import execute_sql_query, commit_transaction, rollback_transaction, get_retry_state, reset_retry, set_current_session
from backend.app.schemas import get_transaction_state, clear_transaction_state
from backend.app.callbacks import StreamingCallbackHandler


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()
    print("SQL-Agent backend started successfully!")
    yield
    print("SQL-Agent backend shutting down...")


app = FastAPI(title="SQL-Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        response = invoke_agent(request.session_id, request.message)
        tx_state = get_transaction_state(request.session_id)
        return {
            "response": response,
            "session_id": request.session_id,
            "has_pending_changes": tx_state["is_active"] and len(tx_state["pending_statements"]) > 0,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/commit")
async def commit(request: CommitRequest):
    try:
        set_current_session(request.session_id)
        result = commit_transaction.invoke({})
        return {"response": result, "session_id": request.session_id, "has_pending_changes": False}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/rollback")
async def rollback(request: RollbackRequest):
    try:
        set_current_session(request.session_id)
        result = rollback_transaction.invoke({})
        return {"response": result, "session_id": request.session_id, "has_pending_changes": False}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/session/{session_id}")
async def session_status(session_id: str):
    tx_state = get_transaction_state(session_id)
    return {
        "session_id": session_id,
        "has_pending_changes": tx_state["is_active"] and len(tx_state["pending_statements"]) > 0,
        "pending_count": len(tx_state["pending_statements"]),
    }


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    clear_agent(session_id)
    clear_transaction_state(session_id)
    return {"status": "ok", "session_id": session_id}


@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                message = payload.get("message", "")
                use_ollama = payload.get("use_ollama", False)
            except json.JSONDecodeError:
                message = data
                use_ollama = False

            if not message.strip():
                continue

            callback = StreamingCallbackHandler()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: _invoke_with_callback(session_id, message, use_ollama, callback)
            )

            tx_state = get_transaction_state(session_id)
            has_pending = tx_state["is_active"] and len(tx_state["pending_statements"]) > 0

            pending_preview = None
            if has_pending:
                pending_preview = tx_state["pending_statements"][-1] if tx_state["pending_statements"] else None

            await websocket.send_json({
                "type": "done",
                "content": response,
                "session_id": session_id,
                "has_pending_changes": has_pending,
                "pending_preview": pending_preview,
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "content": str(e),
                "session_id": session_id,
            })
        except Exception:
            pass


def _invoke_with_callback(session_id: str, message: str, use_ollama: bool, callback: StreamingCallbackHandler):
    set_current_session(session_id)
    reset_retry(session_id)
    return invoke_agent(session_id, message, use_ollama, callbacks=[callback])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
