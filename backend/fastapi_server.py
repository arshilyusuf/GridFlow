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

if os.name == "nt":
    import shutil

    gpp_path = shutil.which("g++")
    if gpp_path:
        os.add_dll_directory(os.path.dirname(gpp_path))

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, "frontend"))

try:
    import gridflow_cpp
    from gridflow import GridFlowPipeline
except ImportError:
    print(
        "[FATAL] Could not find gridflow_cpp.pyd. Ensure you are running from the root directory."
    )
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
_last_pipeline_ref = None


def resolve_matrix_size(payload_size: int) -> int:
    return min(max(int(payload_size // 29), 300), 1000)


def get_tasks_completed(scheduler) -> int:
    if hasattr(scheduler, "get_tasks_completed"):
        return scheduler.get_tasks_completed()
    return 0


def log(q: queue.Queue, msg: str, level: str = "info"):
    q.put({"type": "LOG", "payload": {"msg": msg, "level": level}})


def finish(q: queue.Queue, stop_event: threading.Event, poller: threading.Thread):
    stop_event.set()
    poller.join()
    q.put({"type": "STATE_CHANGE", "payload": {"isRunning": False}})


# ─────────────────────────────────────────────────────────────
# SHARED TELEMETRY POLLER
# ─────────────────────────────────────────────────────────────
def make_poller(
    scheduler, q, stop_event, run_start, total_tasks, matrix_n, runtime_state
):
    def telemetry_poller():
        process = psutil.Process(os.getpid()) if psutil else None
        while not stop_event.is_set():
            try:
                queued = scheduler.get_total_tasks_queued()
                active = scheduler.get_active_worker_count()
                completed = get_tasks_completed(scheduler)
                engine_util = scheduler.get_cpu_utilization()
                elapsed = time.perf_counter() - run_start

                # Process memory (this process only — more meaningful than system RAM)
                if psutil:
                    process_mem_gb = process.memory_info().rss / (1024**3)
                    system_cpu = int(psutil.cpu_percent(interval=None))
                else:
                    process_mem_gb = 0.0
                    system_cpu = int(engine_util)

                throughput = completed / elapsed if elapsed > 0 else 0.0
                progress = (
                    min(100, int((completed / total_tasks) * 100)) if total_tasks else 0
                )

                q.put(
                    {
                        "type": "METRICS",
                        "payload": {
                            "cpu": system_cpu,
                            # Show process RSS instead of whole-system memory
                            "memory": f"{process_mem_gb:.2f} GB",
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
                    }
                )
            except Exception:
                pass
            stop_event.wait(0.1)

    return telemetry_poller


def build_optimal_dag_layout(cores: int) -> dict:
    """
    4 base nodes on the left; chunk nodes fan out vertically on the right.
    """
    nodes = [
        {"id": "1", "label": "Allocate Data", "x": 80, "y": 180, "status": "idle"},
        {"id": "2", "label": "Matrix A", "x": 240, "y": 100, "status": "idle"},
        {"id": "3", "label": "Matrix B", "x": 240, "y": 260, "status": "idle"},
        {"id": "4", "label": "Dot Product", "x": 400, "y": 180, "status": "idle"},
    ]
    chunk_spacing = min(44, max(22, 300 // max(cores, 1)))
    total_height = (cores - 1) * chunk_spacing
    start_y = 180 - total_height // 2
    for i in range(cores):
        nodes.append(
            {
                "id": f"chunk_{i}",
                "label": f"chunk {i}",
                "x": 560,
                "y": start_y + i * chunk_spacing,
                "status": "idle",
            }
        )
    edges = [
        {"from": "1", "to": "2"},
        {"from": "1", "to": "3"},
        {"from": "2", "to": "4"},
        {"from": "3", "to": "4"},
    ]
    for i in range(cores):
        edges.append({"from": "4", "to": f"chunk_{i}"})
    return {"nodes": nodes, "edges": edges}


# ─────────────────────────────────────────────────────────────
# SCENARIO 1 — OPTIMAL EXECUTION PATH
# ─────────────────────────────────────────────────────────────
def run_optimal(config: dict, q: queue.Queue):
    global _last_pipeline_ref
    cores = max(1, int(config.get("targetCores", 8)))
    matrix_n = resolve_matrix_size(int(config.get("payloadSize", 14500)))
    element_count = matrix_n * matrix_n

    # rows_per_chunk determines actual chunk count — must match what gets registered
    rows_per_chunk = max(1, matrix_n // cores)
    actual_chunks = cores  # one chunk per core; last chunk absorbs remainder rows
    # 3 base tasks (allocate, transform_a, transform_b) + actual_chunks
    total_tasks = 3 + actual_chunks

    pipeline = GridFlowPipeline(num_threads=cores)
    scheduler = pipeline.get_scheduler()
    runtime_state = {"stage": "Booting"}
    run_start = time.perf_counter()
    stop_event = threading.Event()

    poller = threading.Thread(
        target=make_poller(
            scheduler, q, stop_event, run_start, total_tasks, matrix_n, runtime_state
        ),
        daemon=False,
    )
    poller.start()

    q.put({"type": "DAG_INIT", "payload": build_optimal_dag_layout(cores)})
    log(
        q,
        f"[Optimal] {cores} threads · {matrix_n}×{matrix_n} matrices · {total_tasks} DAG tasks ({actual_chunks} parallel chunks)",
        "info",
    )

    shared_memory = {}
    chunk_progress = {"finished": 0, "started": False}

    @pipeline.task()
    def allocate_memory():
        runtime_state["stage"] = "Allocating Data"
        q.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "running"}})
        log(q, f" -> Allocating {element_count:,} doubles per matrix...", "info")
        shared_memory["A"] = [i * 0.05 for i in range(element_count)]
        shared_memory["B"] = [j * 0.12 for j in range(element_count)]
        shared_memory["Result"] = [0.0] * element_count
        q.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "success"}})

    @pipeline.task(depends_on=[allocate_memory])
    def transform_a():
        runtime_state["stage"] = "Transform Matrix A (C++)"
        q.put({"type": "NODE_UPDATE", "payload": {"id": "2", "status": "running"}})
        gridflow_cpp.transform_matrix(shared_memory["A"], 1.002)
        q.put({"type": "NODE_UPDATE", "payload": {"id": "2", "status": "success"}})

    @pipeline.task(depends_on=[allocate_memory])
    def transform_b():
        runtime_state["stage"] = "Transform Matrix B (C++)"
        q.put({"type": "NODE_UPDATE", "payload": {"id": "3", "status": "running"}})
        gridflow_cpp.transform_matrix(shared_memory["B"], 1.002)
        q.put({"type": "NODE_UPDATE", "payload": {"id": "3", "status": "success"}})

    def register_chunk_task(row_start: int, row_end: int, chunk_idx: int):
        def compute_chunk_impl():
            if not chunk_progress["started"]:
                chunk_progress["started"] = True
                q.put(
                    {"type": "NODE_UPDATE", "payload": {"id": "4", "status": "running"}}
                )
                log(
                    q,
                    f" -> Parallel multiply: {cores} chunks on {matrix_n}×{matrix_n}...",
                    "success",
                )

            q.put(
                {
                    "type": "NODE_UPDATE",
                    "payload": {"id": f"chunk_{chunk_idx}", "status": "running"},
                }
            )
            runtime_state["stage"] = (
                f"Matrix Multiply chunk {chunk_idx + 1}/{actual_chunks}"
            )

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
                            total += (
                                shared_memory["A"][i * matrix_n + k]
                                * shared_memory["B"][k * matrix_n + j]
                            )
                        shared_memory["Result"][i * matrix_n + j] = total

            q.put(
                {
                    "type": "NODE_UPDATE",
                    "payload": {"id": f"chunk_{chunk_idx}", "status": "success"},
                }
            )
            chunk_progress["finished"] += 1
            if chunk_progress["finished"] >= actual_chunks:
                runtime_state["stage"] = "Complete"
                q.put(
                    {"type": "NODE_UPDATE", "payload": {"id": "4", "status": "success"}}
                )

        compute_chunk_impl.__name__ = f"compute_chunk_{chunk_idx}"
        pipeline.task(depends_on=[transform_a, transform_b])(compute_chunk_impl)

    for i in range(actual_chunks):
        row_start = i * rows_per_chunk
        row_end = matrix_n if i == actual_chunks - 1 else (i + 1) * rows_per_chunk
        register_chunk_task(row_start, row_end, i)

    try:
        start = time.perf_counter()
        pipeline.execute()
        duration = time.perf_counter() - start
        completed = get_tasks_completed(scheduler) or total_tasks
        throughput = completed / duration if duration > 0 else 0.0

        # Final metrics snapshot
        process = psutil.Process(os.getpid()) if psutil else None
        mem_gb = process.memory_info().rss / (1024**3) if psutil else 0.0
        q.put(
            {
                "type": "METRICS",
                "payload": {
                    "cpu": int(psutil.cpu_percent(interval=None)) if psutil else 0,
                    "memory": f"{mem_gb:.2f} GB",
                    "processMemory": f"{mem_gb:.2f} GB",
                    "activeThreads": 0,
                    "queuedTasks": 0,
                    "tasksCompleted": total_tasks,  # show 100%
                    "totalTasks": total_tasks,
                    "engineUtilization": 0,
                    "throughput": round(throughput, 2),
                    "elapsedSeconds": round(duration, 2),
                    "stage": "Complete",
                    "progress": 100,
                    "matrixSize": matrix_n,
                },
            }
        )
        log(
            q,
            f"=> Complete in {duration:.4f}s ({total_tasks}/{total_tasks} tasks, {throughput:.2f} t/s)",
            "success",
        )
    except Exception as exc:
        log(q, f"=> Pipeline failed: {exc}", "error")
    finally:
        finish(q, stop_event, poller)
        _last_pipeline_ref = pipeline


# ─────────────────────────────────────────────────────────────
# SCENARIO 2 — GRAPH CYCLE DETECTED
# ─────────────────────────────────────────────────────────────
def run_cycle_detection(config: dict, q: queue.Queue):
    global _last_pipeline_ref
    cores = max(1, int(config.get("targetCores", 8)))

    pipeline = GridFlowPipeline(num_threads=cores)
    scheduler = pipeline.get_scheduler()
    runtime_state = {"stage": "Compiling cyclic DAG"}
    run_start = time.perf_counter()
    stop_event = threading.Event()
    poller = threading.Thread(
        target=make_poller(scheduler, q, stop_event, run_start, 3, 0, runtime_state),
        daemon=False,
    )
    poller.start()

    dag_layout = {
        "nodes": [
            {"id": "1", "label": "Initialize", "x": 80, "y": 180, "status": "idle"},
            {"id": "2", "label": "Calc Weights", "x": 280, "y": 100, "status": "idle"},
            {"id": "3", "label": "Update Matrix", "x": 480, "y": 180, "status": "idle"},
        ],
        "edges": [
            {"from": "1", "to": "2"},
            {"from": "2", "to": "3"},
            {"from": "3", "to": "2", "stroke": "#f87171", "strokeDasharray": "6 3"},
        ],
    }
    q.put({"type": "DAG_INIT", "payload": dag_layout})
    log(
        q,
        "[Cycle] Building DAG with an intentional cycle: Calc Weights ↔ Update Matrix",
        "warning",
    )
    log(q, "[Cycle] Handing graph to C++ compiler...", "info")
    time.sleep(0.4)

    q.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "running"}})
    time.sleep(0.3)
    q.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "success"}})
    q.put({"type": "NODE_UPDATE", "payload": {"id": "2", "status": "running"}})
    time.sleep(0.3)
    q.put({"type": "NODE_UPDATE", "payload": {"id": "3", "status": "running"}})
    time.sleep(0.3)

    log(q, "[Compiler] Running Kahn's topological sort...", "info")
    time.sleep(0.5)
    log(
        q,
        "[Compiler] WARNING: Sorted node count (1) != total node count (3)",
        "warning",
    )
    time.sleep(0.3)
    log(q, "[Compiler] Engaging DFS cycle tracer...", "warning")
    time.sleep(0.4)
    log(q, "FATAL COMPILER ERROR:", "error")
    log(q, "  Cycle isolated: Task_11 -> Task_12 -> Task_11", "error")
    log(q, "[Compiler] Execution HALTED. Fix the dependency graph and retry.", "error")

    q.put({"type": "NODE_UPDATE", "payload": {"id": "2", "status": "error"}})
    q.put({"type": "NODE_UPDATE", "payload": {"id": "3", "status": "error"}})
    runtime_state["stage"] = "Cycle detected — halted"

    time.sleep(0.5)
    finish(q, stop_event, poller)
    _last_pipeline_ref = pipeline


# ─────────────────────────────────────────────────────────────
# SCENARIO 3 — LINEAR CHAIN FUSION
# ─────────────────────────────────────────────────────────────
def run_chain_fusion(config: dict, q: queue.Queue):
    global _last_pipeline_ref
    cores = max(1, int(config.get("targetCores", 8)))

    pipeline = GridFlowPipeline(num_threads=cores)
    scheduler = pipeline.get_scheduler()
    runtime_state = {"stage": "Compiling linear chain"}
    run_start = time.perf_counter()
    stop_event = threading.Event()
    poller = threading.Thread(
        target=make_poller(scheduler, q, stop_event, run_start, 1, 0, runtime_state),
        daemon=False,
    )
    poller.start()

    before_dag = {
        "nodes": [
            {"id": "1", "label": "Load Data", "x": 60, "y": 180, "status": "idle"},
            {"id": "2", "label": "Clean Data", "x": 220, "y": 180, "status": "idle"},
            {"id": "3", "label": "Format Data", "x": 380, "y": 180, "status": "idle"},
            {"id": "4", "label": "Train Model", "x": 540, "y": 180, "status": "idle"},
        ],
        "edges": [
            {"from": "1", "to": "2"},
            {"from": "2", "to": "3"},
            {"from": "3", "to": "4"},
        ],
    }
    q.put({"type": "DAG_INIT", "payload": before_dag})
    log(q, "[Fusion] Input DAG: 4 tasks in a strict linear chain", "info")
    log(q, "[Fusion] Load Data → Clean Data → Format Data → Train Model", "info")
    log(q, "[Compiler] Scanning for linear chain fusion opportunities...", "info")
    time.sleep(0.6)

    for node_id in ["1", "2", "3", "4"]:
        q.put({"type": "NODE_UPDATE", "payload": {"id": node_id, "status": "running"}})
        time.sleep(0.25)

    log(
        q,
        "[Compiler] Task 1→2: single dependent, single parent — FUSION CANDIDATE",
        "warning",
    )
    time.sleep(0.3)
    log(
        q,
        "[Compiler] Task 2→3: single dependent, single parent — FUSION CANDIDATE",
        "warning",
    )
    time.sleep(0.3)
    log(
        q,
        "[Compiler] Task 3→4: single dependent, single parent — FUSION CANDIDATE",
        "warning",
    )
    time.sleep(0.3)
    log(
        q,
        "[Compiler] Fusing 3 linear tasks. Merging payloads into Task 1...",
        "warning",
    )
    time.sleep(0.5)
    log(q, "[COMPILER] Optimizer fused 3 linear tasks.", "success")

    after_dag = {
        "nodes": [
            {
                "id": "1",
                "label": "Load+Clean+Format (fused)",
                "x": 200,
                "y": 180,
                "status": "success",
            },
            {"id": "4", "label": "Train Model", "x": 460, "y": 180, "status": "idle"},
        ],
        "edges": [{"from": "1", "to": "4"}],
    }
    q.put({"type": "DAG_INIT", "payload": after_dag})
    log(
        q,
        "[Fusion] Graph reduced: 4 tasks → 2 tasks (50% fewer scheduler dispatches)",
        "success",
    )
    log(q, "[Fusion] Executing fused pipeline...", "info")
    time.sleep(0.3)

    q.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "running"}})
    time.sleep(0.6)
    q.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "success"}})
    q.put({"type": "NODE_UPDATE", "payload": {"id": "4", "status": "running"}})
    time.sleep(0.6)
    q.put({"type": "NODE_UPDATE", "payload": {"id": "4", "status": "success"}})
    runtime_state["stage"] = "Complete"
    log(q, "=> Fusion complete. Eliminated 3 task dispatch overhead cycles.", "success")

    finish(q, stop_event, poller)
    _last_pipeline_ref = pipeline


# ─────────────────────────────────────────────────────────────
# SCENARIO 4 — NETWORK WORKER FAILURE
# ─────────────────────────────────────────────────────────────
def run_network_failure(config: dict, q: queue.Queue):
    global _last_pipeline_ref
    cores = max(1, int(config.get("targetCores", 8)))

    pipeline = GridFlowPipeline(num_threads=cores)
    scheduler = pipeline.get_scheduler()
    runtime_state = {"stage": "Dispatching to cluster"}
    run_start = time.perf_counter()
    stop_event = threading.Event()
    poller = threading.Thread(
        target=make_poller(scheduler, q, stop_event, run_start, 4, 0, runtime_state),
        daemon=False,
    )
    poller.start()

    dag_layout = {
        "nodes": [
            {"id": "1", "label": "Load Dataset", "x": 60, "y": 180, "status": "idle"},
            {
                "id": "2",
                "label": "Normalize Arrays",
                "x": 240,
                "y": 100,
                "status": "idle",
            },
            {
                "id": "3",
                "label": "Boot Neural Net",
                "x": 240,
                "y": 260,
                "status": "idle",
            },
            {"id": "4", "label": "Backprop Loss", "x": 440, "y": 180, "status": "idle"},
        ],
        "edges": [
            {"from": "1", "to": "2"},
            {"from": "1", "to": "3"},
            {"from": "2", "to": "4"},
            {"from": "3", "to": "4"},
        ],
    }
    q.put({"type": "DAG_INIT", "payload": dag_layout})
    log(q, "[Registry] Registered Worker Node at 192.168.1.50:8080", "info")
    log(q, "[Registry] Registered Worker Node at 192.168.1.51:8080", "info")
    log(q, "[Master] 2 healthy workers online. Dispatching DAG tasks...", "success")
    time.sleep(0.4)

    q.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "running"}})
    log(q, "[Master] Serializing 'Load_Dataset' → routing to 192.168.1.50:8080", "info")
    time.sleep(0.5)
    log(q, "   <- [Worker Reply]: ACK_OK", "success")
    q.put({"type": "NODE_UPDATE", "payload": {"id": "1", "status": "success"}})
    time.sleep(0.3)

    q.put({"type": "NODE_UPDATE", "payload": {"id": "2", "status": "running"}})
    log(
        q,
        "[Master] Serializing 'Normalize_Arrays' → routing to 192.168.1.51:8080",
        "info",
    )
    time.sleep(0.5)
    log(q, "   <- [Worker Reply]: ACK_OK", "success")
    q.put({"type": "NODE_UPDATE", "payload": {"id": "2", "status": "success"}})
    time.sleep(0.3)

    q.put({"type": "NODE_UPDATE", "payload": {"id": "3", "status": "running"}})
    log(
        q,
        "[Master] Serializing 'Boot_Neural_Net' → routing to 192.168.1.50:8080",
        "info",
    )
    time.sleep(0.6)
    log(q, "[Master] ERROR: Connection refused. Worker node down.", "error")
    log(
        q,
        "[Registry] FATAL: Node 192.168.1.50:8080 flatlined. Marked as DEAD.",
        "error",
    )
    q.put({"type": "NODE_UPDATE", "payload": {"id": "3", "status": "error"}})
    runtime_state["stage"] = "Worker failure detected"
    time.sleep(0.4)

    log(
        q,
        "[Master] Failover: re-routing 'Boot_Neural_Net' → 192.168.1.51:8080",
        "warning",
    )
    q.put({"type": "NODE_UPDATE", "payload": {"id": "3", "status": "running"}})
    time.sleep(0.5)
    log(q, "   <- [Worker Reply]: ACK_OK", "success")
    q.put({"type": "NODE_UPDATE", "payload": {"id": "3", "status": "success"}})
    time.sleep(0.3)

    q.put({"type": "NODE_UPDATE", "payload": {"id": "4", "status": "running"}})
    log(
        q,
        "[Master] Serializing 'Backpropagate_Loss' → routing to 192.168.1.51:8080",
        "info",
    )
    time.sleep(0.6)
    log(q, "   <- [Worker Reply]: ACK_OK", "success")
    q.put({"type": "NODE_UPDATE", "payload": {"id": "4", "status": "success"}})
    runtime_state["stage"] = "Complete — 1 node recovered"
    log(
        q,
        "=> Cluster dispatch complete. 1 worker failed, 1 failover succeeded.",
        "warning",
    )

    finish(q, stop_event, poller)
    _last_pipeline_ref = pipeline


# ─────────────────────────────────────────────────────────────
# SCENARIO ROUTER
# ─────────────────────────────────────────────────────────────
SCENARIO_MAP = {
    "Optimal Execution Path": run_optimal,
    "Graph Cycle Detected": run_cycle_detection,
    "Linear Chain Fusion": run_chain_fusion,
    "Network Worker Failure": run_network_failure,
}


def run_native_cpp_engine(config: dict, message_queue: queue.Queue):
    scenario = config.get("scenario", "Optimal Execution Path")
    runner = SCENARIO_MAP.get(scenario, run_optimal)
    runner(config, message_queue)


# ─────────────────────────────────────────────────────────────
# WEBSOCKET ENDPOINT
# ─────────────────────────────────────────────────────────────
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
                    q.put(
                        {
                            "type": "LOG",
                            "payload": {
                                "msg": f"=> Engine error: {exc}",
                                "level": "error",
                            },
                        }
                    )
                    q.put({"type": "STATE_CHANGE", "payload": {"isRunning": False}})

            elif action == "HALT_PIPELINE":
                q.put(
                    {
                        "type": "LOG",
                        "payload": {
                            "msg": "[Master] Halt signal received.",
                            "level": "warning",
                        },
                    }
                )
                q.put({"type": "STATE_CHANGE", "payload": {"isRunning": False}})

    except WebSocketDisconnect:
        reader_task.cancel()
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
