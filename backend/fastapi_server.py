# File: backend/fastapi_server.py
import asyncio
import json
import sys
import os
import time
import queue
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

try:
    import psutil
except ImportError:
    psutil = None

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
    import gridflow_cpp
    from gridflow import GridFlowPipeline
except ImportError:
    print("[FATAL] Could not find gridflow_cpp.pyd. Ensure you are running from the root directory.")
    sys.exit(1)

app = FastAPI(title="GridFlow API Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))

manager = ConnectionManager()

# Retain last pipeline until the next run to avoid a Windows/pybind teardown crash.
_last_pipeline_ref = None

def resolve_matrix_size(payload_size: int) -> int:
    # UI "payload" maps to matrix dimension (e.g. 14500 -> 500, 50000 -> 1000).
    return min(max(int(payload_size // 29), 300), 1000)

def get_tasks_completed(scheduler) -> int:
    if hasattr(scheduler, "get_tasks_completed"):
        return scheduler.get_tasks_completed()
    return 0

def run_native_cpp_engine(config: dict, message_queue: queue.Queue):
    global _last_pipeline_ref
    cores = max(1, int(config.get("targetCores", 8)))
    matrix_n = resolve_matrix_size(int(config.get("payloadSize", 14500)))
    element_count = matrix_n * matrix_n
    total_tasks = 3 + cores  # allocate + 2 transforms + parallel row chunks

    pipeline = GridFlowPipeline(num_threads=cores)
    scheduler = pipeline.get_scheduler()
    runtime_state = {"stage": "Booting", "progress": 0}
    run_start = time.perf_counter()
    stop_telemetry = threading.Event()

    def telemetry_poller():
        process = psutil.Process(os.getpid()) if psutil else None
        while not stop_telemetry.is_set():
            try:
                queued = scheduler.get_total_tasks_queued()
                active = scheduler.get_active_worker_count()
                completed = get_tasks_completed(scheduler)
                engine_util = scheduler.get_cpu_utilization()
                elapsed = time.perf_counter() - run_start

                if psutil:
                    system_cpu = int(psutil.cpu_percent(interval=None))
                    system_mem_gb = psutil.virtual_memory().used / (1024 ** 3)
                    process_mem_gb = process.memory_info().rss / (1024 ** 3)
                else:
                    system_cpu = int(engine_util)
                    system_mem_gb = (element_count * 8 * 3) / (1024 ** 3)
                    process_mem_gb = system_mem_gb

                throughput = completed / elapsed if elapsed > 0 else 0.0
                progress = min(100, int((completed / total_tasks) * 100))

                message_queue.put({
                    "type": "METRICS",
                    "payload": {
                        "cpu": system_cpu,
                        "memory": f"{system_mem_gb:.1f} GB",
                        "processMemory": f"{process_mem_gb:.2f} GB",
                        "activeThreads": active,
                        "queuedTasks": queued,
                        "tasksCompleted": completed,
                        "totalTasks": total_tasks,
                        "engineUtilization": int(engine_util),
                        "throughput": round(throughput, 2),
                        "elapsedSeconds": round(elapsed, 2),
                        "stage": runtime_state["stage"],
                        "progress": progress,
                        "matrixSize": matrix_n,
                    },
                })
            except Exception:
                pass
            stop_telemetry.wait(0.1)

    poller_thread = threading.Thread(target=telemetry_poller, daemon=False)
    poller_thread.start()

    def finish_run():
        stop_telemetry.set()
        poller_thread.join()
        message_queue.put({"type": "STATE_CHANGE", "payload": {"isRunning": False}})

    dag_layout = {
        "nodes": [
            {"id": "1", "label": "Allocate Data", "x": 50, "y": 150, "status": "idle"},
            {"id": "2", "label": "Matrix A", "x": 250, "y": 80, "status": "idle"},
            {"id": "3", "label": "Matrix B", "x": 250, "y": 220, "status": "idle"},
            {"id": "4", "label": "Dot Product", "x": 450, "y": 150, "status": "idle"},
        ],
        "edges": [
            {"from": "1", "to": "2"},
            {"from": "1", "to": "3"},
            {"from": "2", "to": "4"},
            {"from": "3", "to": "4"},
        ],
    }
    message_queue.put({"type": "DAG_INIT", "payload": dag_layout})
    message_queue.put({
        "type": "LOG",
        "payload": {
            "msg": (
                f"[Master] {cores} worker threads, {matrix_n}x{matrix_n} matrices, "
                f"{total_tasks} DAG tasks ({cores} parallel compute chunks)..."
            ),
            "level": "info",
        },
    })

    shared_memory = {}
    chunk_progress = {"finished": 0, "started": False}

    @pipeline.task()
    def allocate_memory():
        runtime_state["stage"] = "Allocating Data"
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "running"}})
        message_queue.put({
            "type": "LOG",
            "payload": {"msg": f" -> Allocating {element_count:,} doubles per matrix...", "level": "info"},
        })
        shared_memory["A"] = [i * 0.05 for i in range(element_count)]
        shared_memory["B"] = [j * 0.12 for j in range(element_count)]
        shared_memory["Result"] = [0.0] * element_count
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "success"}})

    @pipeline.task(depends_on=[allocate_memory])
    def transform_a():
        runtime_state["stage"] = "Transform Matrix A (C++)"
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "2", "status": "running"}})
        gridflow_cpp.transform_matrix(shared_memory["A"], 1.002)
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "2", "status": "success"}})

    @pipeline.task(depends_on=[allocate_memory])
    def transform_b():
        runtime_state["stage"] = "Transform Matrix B (C++)"
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "3", "status": "running"}})
        gridflow_cpp.transform_matrix(shared_memory["B"], 1.002)
        message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "3", "status": "success"}})

    rows_per_chunk = max(1, matrix_n // cores)

    def register_chunk_task(row_start: int, row_end: int, chunk_idx: int):
        def compute_chunk_impl():
            if not chunk_progress["started"]:
                chunk_progress["started"] = True
                message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "4", "status": "running"}})
                message_queue.put({
                    "type": "LOG",
                    "payload": {
                        "msg": f" -> Parallel multiply: {cores} chunks on {matrix_n}x{matrix_n} matrices...",
                        "level": "success",
                    },
                })

            runtime_state["stage"] = f"Matrix Multiply chunk {chunk_idx + 1}/{cores}"

            if hasattr(gridflow_cpp, "dot_product_rows"):
                gridflow_cpp.dot_product_rows(
                    shared_memory["A"],
                    shared_memory["B"],
                    shared_memory["Result"],
                    matrix_n,
                    row_start,
                    row_end,
                )
            else:
                for i in range(row_start, row_end):
                    for j in range(matrix_n):
                        total = 0.0
                        for k in range(matrix_n):
                            total += shared_memory["A"][i * matrix_n + k] * shared_memory["B"][k * matrix_n + j]
                        shared_memory["Result"][i * matrix_n + j] = total

            chunk_progress["finished"] += 1
            if chunk_progress["finished"] >= cores:
                runtime_state["stage"] = "Complete"
                message_queue.put({"type": "NODE_UPDATE", "payload": {"id": "4", "status": "success"}})

        compute_chunk_impl.__name__ = f"compute_chunk_{chunk_idx}"
        pipeline.task(depends_on=[transform_a, transform_b])(compute_chunk_impl)

    for chunk_idx in range(cores):
        row_start = chunk_idx * rows_per_chunk
        row_end = matrix_n if chunk_idx == cores - 1 else (chunk_idx + 1) * rows_per_chunk
        register_chunk_task(row_start, row_end, chunk_idx)

    try:
        start_time = time.perf_counter()
        pipeline.execute()
        duration = time.perf_counter() - start_time
        completed = get_tasks_completed(scheduler) or total_tasks
        throughput = completed / duration if duration > 0 else 0.0
        message_queue.put({
            "type": "METRICS",
            "payload": {
                "cpu": int(psutil.cpu_percent(interval=None)) if psutil else 0,
                "memory": f"{psutil.virtual_memory().used / (1024 ** 3):.1f} GB" if psutil else "0.0 GB",
                "processMemory": f"{psutil.Process(os.getpid()).memory_info().rss / (1024 ** 3):.2f} GB" if psutil else "0.0 GB",
                "activeThreads": 0,
                "queuedTasks": 0,
                "tasksCompleted": completed,
                "totalTasks": total_tasks,
                "engineUtilization": 0,
                "throughput": round(throughput, 2),
                "elapsedSeconds": round(duration, 2),
                "stage": "Complete",
                "progress": 100,
                "matrixSize": matrix_n,
            },
        })
        message_queue.put({
            "type": "LOG",
            "payload": {
                "msg": (
                    f"=> Execution complete in {duration:.4f}s "
                    f"({completed}/{total_tasks} tasks, {throughput:.2f} tasks/s, "
                    f"{matrix_n}x{matrix_n} matrices)."
                ),
                "level": "success",
            },
        })
    except Exception as exc:
        runtime_state["stage"] = "Failed"
        message_queue.put({
            "type": "LOG",
            "payload": {"msg": f"=> Pipeline failed: {exc}", "level": "error"},
        })
    finally:
        finish_run()
        _last_pipeline_ref = pipeline

@app.websocket("/ws/execution")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    q = queue.Queue()

    async def queue_reader():
        loop = asyncio.get_running_loop()
        while True:
            try:
                msg = await loop.run_in_executor(None, q.get)
                try:
                    await manager.send_message(msg, websocket)
                except (WebSocketDisconnect, RuntimeError):
                    break
                except Exception:
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.1)

    reader_task = asyncio.create_task(queue_reader())

    try:
        while True:
            data = await websocket.receive_text()
            req = json.loads(data)
            action = req.get("action")

            if action == "START_PIPELINE":
                if reader_task.done():
                    reader_task = asyncio.create_task(queue_reader())
                config = req.get("config", {})
                loop = asyncio.get_running_loop()
                try:
                    await loop.run_in_executor(None, run_native_cpp_engine, config, q)
                except Exception as exc:
                    q.put({"type": "LOG", "payload": {"msg": f"=> Engine error: {exc}", "level": "error"}})
                    q.put({"type": "STATE_CHANGE", "payload": {"isRunning": False}})

            elif action == "HALT_PIPELINE":
                q.put({"type": "LOG", "payload": {"msg": "[Master] Halt signal received.", "level": "warning"}})
                q.put({"type": "STATE_CHANGE", "payload": {"isRunning": False}})

    except WebSocketDisconnect:
        reader_task.cancel()
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
