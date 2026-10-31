from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import sqlite3
import time

from database import init_db, create_task, get_task, get_all_tasks
from ai_pipeline import start_processing

app = FastAPI(title="Audio Summarizer")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/history", response_class=HTMLResponse)
async def read_history(request: Request):
    tasks = get_all_tasks()
    return templates.TemplateResponse("history.html", {"request": request, "tasks": tasks})

@app.post("/api/upload")
async def upload_audio(file: UploadFile = File(...)):
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".mp3", ".wav", ".m4a"}:
        raise HTTPException(status_code=400, detail="Invalid file type. Only .mp3, .wav, and .m4a are supported.")
    safe_name = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, f"{time.time_ns()}_{safe_name}")
    bytes_written = 0
    try:
        with open(file_path, "wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail="File is too large. Maximum size is 50MB.")
                buffer.write(chunk)
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except OSError as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    try:
        task_id = create_task(filename)
        start_processing(task_id, file_path)
    except (OSError, RuntimeError, sqlite3.Error):
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    return JSONResponse(content={"task_id": task_id, "message": "File uploaded successfully."})

@app.get("/api/status/{task_id}")
async def get_audio_status(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
