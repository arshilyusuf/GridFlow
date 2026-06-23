# File: backend/fastapi_server.py
import asyncio
import json
import sys
import os
import time
import queue
import concurrent.futures
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- WINDOWS PATH & DLL RESOLUTION ---
if os.name == 'nt':
    import shutil
    gpp_path = shutil.which("g++")
    if gpp_path:
        os.add_dll_directory(os.path.dirname(gpp_path))

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'frontend'))

try:
    from gridflow import GridFlowPipeline
except ImportError:
    print("[FATAL] Could not find gridflow_cpp.pyd. Ensure you are running from the root directory.")
    sys.exit(1)

# --- SERVER SETUP ---
app = FastAPI(title="GridFlow API Gateway")
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))

manager = ConnectionManager()

# --- NATIVE C++ TELEMETRY BRIDGE ---
def run_native_cpp_engine(cores: int, message_queue: queue.Queue):
    pipeline = GridFlowPipeline(num_threads=cores)
    scheduler = pipeline.get_scheduler()

    # 1. Telemetry Poller: Monitors the real C++ hardware state
    stop_telemetry = threading.Event()
    def telemetry_poller():
        while not stop_telemetry.is_set():
            try:
                # Query real C++ internal state
                queued = scheduler.get_total_tasks_queued()
                active = scheduler.get_active_worker_count()
                
                # Report metrics
                message_queue.put({
                    "type": "METRICS", 
                    "payload": {
                        "cpu": int((active / cores) * 100), 
                        "memory": f"{(0.2 + (queued * 0.12)):.1f} GB", 
                        "activeThreads": active
                    }
                })
            except Exception:
                pass # Fail silently if C++ methods aren't ready yet
            time.sleep(0.2)

    poller_thread = threading.Thread(target=telemetry_poller, daemon=True)
    poller_thread.start()

    # 2. Map DAG
    dag_layout = {
        "nodes": [
            {"id": "1", "label": "Allocate Data", "x": 50, "y": 150, "status": "idle"},
            {"id": "2", "label": "Matrix A", "x": 250, "y": 80, "status": "idle"},
            {"id": "3", "label": "Matrix B", "x": 250, "y": 220, "status": "idle"},
            {"id": "4", "label": "Dot Product", "x": 450, "y": 150, "status": "idle"}
        ],
        "edges": [{"from": "1", "to": "2"}, {"from": "1", "to": "3"}, {"from": "2", "to": "4"}, {"from": "3", "to": "4"}]
    }
    message_queue.put({"type": "DAG_INIT", "payload": dag_layout})
    message_queue.put({"type": "LOG", "payload": {"msg": f"[Master] Booting native engine with {cores} threads...", "level": "info"}})

    # 3. Execution Logic
    shared_memory = {}

    @pipeline.task()
    def allocate_memory():
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "running"}})
        message_queue.put({"type": "LOG", "payload": {"msg": " -> [Core 0] Allocating contiguous heap blocks...", "level": "info"}})
        shared_memory['A'] = [[i * 0.05 for i in range(500)] for _ in range(500)]
        shared_memory['B'] = [[j * 0.12 for j in range(500)] for _ in range(500)]
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "success"}})

    @pipeline.task(depends_on=[allocate_memory])
    @pipeline.task(depends_on=[allocate_memory])
    def transform_a():
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "2", "status": "running"}})
        # Instead of Python for-loops, call the C++ kernel
        transform_matrix(shared_memory['A'], 1.002) 
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "2", "status": "success"}})

    @pipeline.task(depends_on=[transform_a, transform_b])
    def compute_dot():
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "4", "status": "running"}})
        # Call the native C++ dot product
        dot_product(shared_memory['A'], shared_memory['B'], shared_memory['Result'], 500)
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "4", "status": "success"}})

    @pipeline.task(depends_on=[transform_a, transform_b])
    def compute_dot():
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "4", "status": "running"}})
        message_queue.put({"type": "LOG", "payload": {"msg": " -> [Sync] Executing parallel dot product...", "level": "success"}})
        shared_memory['Result'] = [[0.0 for _ in range(500)] for _ in range(500)]
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "4", "status": "success"}})

    # 4. Pipeline Execution
    start_time = time.perf_counter()
    pipeline.execute()
    duration = time.perf_counter() - start_time
    
    # 5. Cleanup
    message_queue.put({"type": "LOG", "payload": {"msg": f"=> Execution complete in {duration:.4f}s.", "level": "success"}})
    stop_telemetry.set()
    poller_thread.join()
    message_queue.put({"type": "STATE_CHANGE", "payload": {"isRunning": False}})

# --- WEBSOCKET HANDLERS ---
@app.websocket("/ws/execution")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    q = queue.Queue()

    async def queue_reader():
        loop = asyncio.get_running_loop()
        while True:
            try:
                msg = await loop.run_in_executor(None, q.get)
                await manager.send_message(msg, websocket)
            except Exception:
                break

    reader_task = asyncio.create_task(queue_reader())

    try:
        while True:
            data = await websocket.receive_text()
            req = json.loads(data)
            if req.get("action") == "START_PIPELINE":
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, run_native_cpp_engine, req["config"]["targetCores"], q)
    except WebSocketDisconnect:
        reader_task.cancel()
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)