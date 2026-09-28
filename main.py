import shutil
import tempfile
import threading
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

import services

app = FastAPI(title="Certificate Generator API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-app-name.onrender.com",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


FRONTEND = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND / "static"), name="static")

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND / "index.html")

WORK_ROOT = Path(tempfile.gettempdir()) / "certgen"
WORK_ROOT.mkdir(exist_ok=True)


# ---------------------------------------------------------------- state
@dataclass
class Session:
    id: str
    dir: Path
    template: Path
    data: dict[str, list[str]]
    status: Literal["ready", "running", "done", "error"] = "ready"
    done: int = 0
    total: int = 0
    error: Optional[str] = None
    result: Optional[Path] = None
    lock: threading.Lock = field(default_factory=threading.Lock)


SESSIONS: dict[str, Session] = {}  # in-memory: swap for Redis/DB if you run >1 worker


def get_session(sid: str) -> Session:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


# --------------------------------------------------------------- schemas
class SessionInfo(BaseModel):
    session_id: str
    columns: list[str]
    row_count: int
    preview: list[dict[str, str]]


class GenerateRequest(BaseModel):
    # {original_column: new_name}; new_name may equal original (this replaces the ColumnSelector popup)
    columns: dict[str, str]
    merge: bool = False


class Progress(BaseModel):
    status: str
    done: int
    total: int
    percent: int
    error: Optional[str] = None


# ------------------------------------------------------------- endpoints
@app.post("/api/sessions", response_model=SessionInfo)
def create_session(
    data_file: UploadFile = File(...),
    template_file: UploadFile = File(...),
    bijoy_to_unicode: bool = Form(False),
):
    """Step 1: upload data + template. Returns the columns to pick from."""
    d_ext = Path(data_file.filename or "").suffix.lower()
    if d_ext not in services.DATA_EXTENSIONS:
        raise HTTPException(400, f"Data file must be one of {sorted(services.DATA_EXTENSIONS)}")
    if Path(template_file.filename or "").suffix.lower() != ".docx":
        raise HTTPException(400, "Template must be a .docx file")

    sid = uuid.uuid4().hex
    sdir = WORK_ROOT / sid
    sdir.mkdir(parents=True)
    data_path, template_path = sdir / f"input{d_ext}", sdir / "template.docx"

    try:
        for up, dest in ((data_file, data_path), (template_file, template_path)):
            with open(dest, "wb") as f:
                shutil.copyfileobj(up.file, f)
        data = services.get_data(data_path, bijoy_to_unicode)
    except Exception as e:
        shutil.rmtree(sdir, ignore_errors=True)
        raise HTTPException(400, f"Could not read data file: {e}")

    if not data:
        shutil.rmtree(sdir, ignore_errors=True)
        raise HTTPException(400, "No data found in the input file")

    SESSIONS[sid] = Session(id=sid, dir=sdir, template=template_path, data=data)
    rows = min(len(v) for v in data.values())
    preview = [{k: v[i] for k, v in data.items()} for i in range(min(3, rows))]
    return SessionInfo(session_id=sid, columns=list(data), row_count=rows, preview=preview)


def _run_job(s: Session, selected: dict[str, list[str]], merge: bool):
    def on_progress(done: int, total: int):
        s.done, s.total = done, total

    try:
        out_dir = s.dir / "certificates"
        shutil.rmtree(out_dir, ignore_errors=True)
        files = services.generate_certs(s.template, selected, out_dir, on_progress)

        extras = []
        if merge:
            extras.append(services.merge_docs(files, out_dir / "All_Certificates_Merged.docx"))

        zip_path = s.dir / "certificates.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files + extras:
                z.write(f, f.name)
        s.result, s.status = zip_path, "done"
    except Exception as e:
        s.error, s.status = str(e), "error"


@app.post("/api/sessions/{sid}/generate", status_code=202)
def generate(sid: str, req: GenerateRequest, bg: BackgroundTasks):
    """Step 2: choose/rename columns and start generation (runs in background)."""
    s = get_session(sid)
    if s.status == "running":
        raise HTTPException(409, "Generation already running")
    if not req.columns:
        raise HTTPException(400, "Select at least one column")

    missing = [c for c in req.columns if c not in s.data]
    if missing:
        raise HTTPException(400, f"Unknown columns: {missing}")

    new_names = [(new.strip() or old) for old, new in req.columns.items()]
    if len(set(new_names)) != len(new_names):
        raise HTTPException(400, "Renamed columns must be unique")

    selected = {new: s.data[old] for (old, _), new in zip(req.columns.items(), new_names)}
    s.status, s.done, s.total, s.error, s.result = "running", 0, 0, None, None
    bg.add_task(_run_job, s, selected, req.merge)
    return {"status": "running"}


@app.get("/api/sessions/{sid}/progress", response_model=Progress)
def progress(sid: str):
    """Step 3: poll this (e.g. every 500ms) to drive the progress bar."""
    s = get_session(sid)
    pct = int(s.done / s.total * 100) if s.total else 0
    return Progress(status=s.status, done=s.done, total=s.total, percent=pct, error=s.error)


@app.get("/api/sessions/{sid}/download")
def download(sid: str):
    """Step 4: get the zip (all certificates + merged file if requested)."""
    s = get_session(sid)
    if s.status != "done" or not s.result:
        raise HTTPException(409, f"Not ready (status: {s.status})")
    return FileResponse(s.result, media_type="application/zip", filename="certificates.zip")


@app.delete("/api/sessions/{sid}", status_code=204)
def delete_session(sid: str):
    s = SESSIONS.pop(sid, None)
    if s:
        shutil.rmtree(s.dir, ignore_errors=True)