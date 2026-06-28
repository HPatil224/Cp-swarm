import os
import sys
import asyncio
import logging
import uuid
import re
import datetime
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from concurrent.futures import ThreadPoolExecutor

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings
from problems.schema import Problem, SampleIO
from orchestrator import pipeline
from benchmark import parse_problem_file

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_server")

app = FastAPI(title="Swarm Solver Web Dashboard")

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for running the sync pipeline in background
executor = ThreadPoolExecutor(max_workers=5)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket):
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = []
        self.active_connections[run_id].append(websocket)
        logger.info(f"WebSocket connected for run: {run_id}")

    def disconnect(self, run_id: str, websocket: WebSocket):
        if run_id in self.active_connections:
            self.active_connections[run_id].remove(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]
        logger.info(f"WebSocket disconnected for run: {run_id}")

    async def broadcast(self, run_id: str, event: str, data: dict):
        if run_id in self.active_connections:
            payload = {"event": event, "data": data}
            for connection in self.active_connections[run_id]:
                try:
                    await connection.send_json(payload)
                except Exception as e:
                    logger.error(f"Error broadcasting to WS: {e}")

manager = ConnectionManager()

# Pydantic schemas
class CustomProblemRequest(BaseModel):
    title: str
    statement: str
    samples: List[dict]

class SolveRequest(BaseModel):
    file_path: Optional[str] = None
    custom_problem: Optional[CustomProblemRequest] = None

# Ensure static folder exists
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(exist_ok=True)

# Helper to run pipeline and dispatch events
def run_pipeline_sync(problem: Problem, run_id: str, loop: asyncio.AbstractEventLoop):
    def ws_callback(event: str, data: dict):
        asyncio.run_coroutine_threadsafe(
            manager.broadcast(run_id, event, data),
            loop
        )
    
    try:
        pipeline.solve(problem, run_id=run_id, callback=ws_callback)
    except Exception as e:
        logger.error(f"Error in pipeline.solve: {e}")
        asyncio.run_coroutine_threadsafe(
            manager.broadcast(run_id, "failed", {"status": f"crashed: {str(e)}"}),
            loop
        )

# API Endpoints
@app.get("/api/problems")
def get_problems():
    """Discover available problems in samples and benchmarks."""
    problems_list = []
    
    # Check benchmarks and samples dirs
    paths = [
        ("benchmarks", Path("problems/benchmarks")),
        ("samples", Path("problems/samples"))
    ]
    
    for category, directory in paths:
        if directory.exists():
            for filepath in directory.glob("*.txt"):
                try:
                    problem = parse_problem_file(filepath)
                    problems_list.append({
                        "filename": filepath.name,
                        "category": category,
                        "title": problem.title,
                        "filepath": str(filepath.resolve())
                    })
                except Exception as e:
                    logger.error(f"Failed to parse problem file {filepath}: {e}")
                    
    return problems_list

@app.post("/api/solve")
async def start_solve(request: SolveRequest):
    """Triggers the solve loop for a problem in a background thread."""
    run_id = uuid.uuid4().hex[:8]
    problem = None
    
    if request.file_path:
        filepath = Path(request.file_path)
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Problem file not found")
        problem = parse_problem_file(filepath)
    elif request.custom_problem:
        samples = [
            SampleIO(input=s.get("input", "") + "\n", expected_output=s.get("output", ""))
            for s in request.custom_problem.samples
        ]
        problem = Problem(
            title=request.custom_problem.title,
            statement=request.custom_problem.statement,
            samples=samples
        )
    else:
        raise HTTPException(status_code=400, detail="Must provide either file_path or custom_problem")
        
    # Start loop in thread pool
    loop = asyncio.get_running_loop()
    executor.submit(run_pipeline_sync, problem, run_id, loop)
    
    return {"status": "started", "run_id": run_id}

@app.get("/api/runs")
def get_historical_runs():
    """Scan the logs directory for run metadata."""
    runs_dir = settings.paths.logs_dir
    runs_list = []
    
    if runs_dir.exists():
        for run_path in sorted(runs_dir.iterdir(), key=lambda p: p.stat().st_mtime if p.is_dir() else 0, reverse=True):
            if run_path.is_dir():
                transcript_file = run_path / "transcript.md"
                if transcript_file.exists():
                    try:
                        content = transcript_file.read_text(encoding="utf-8")
                        title_match = re.search(r"\*\*Problem\*\*:\s*(.*)", content)
                        status_match = re.search(r"\*\*Final Status\*\*:\s*(.*)", content)
                        
                        title = title_match.group(1).strip() if title_match else "Unknown"
                        status = status_match.group(1).strip() if status_match else "unknown"
                        
                        runs_list.append({
                            "run_id": run_path.name,
                            "title": title,
                            "status": status,
                            "timestamp": datetime.datetime.fromtimestamp(run_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })
                    except Exception as e:
                        logger.error(f"Error reading transcript for {run_path.name}: {e}")
                        
    return runs_list

@app.get("/api/runs/{run_id}")
def get_run_details(run_id: str):
    """Retrieve full transcript and C++ solution for a run."""
    run_dir = settings.paths.logs_dir / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="Run not found")
        
    transcript_file = run_dir / "transcript.md"
    solution_file = run_dir / "solution.cpp"
    
    transcript = transcript_file.read_text(encoding="utf-8") if transcript_file.exists() else ""
    solution = solution_file.read_text(encoding="utf-8") if solution_file.exists() else ""
    
    return {
        "run_id": run_id,
        "transcript": transcript,
        "solution": solution
    }

# WebSockets endpoint
@app.websocket("/ws/solve/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    await manager.connect(run_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(run_id, websocket)

# Mount static files or fall back to index.html
@app.get("/")
def read_root():
    return FileResponse(static_dir / "index.html")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
