# GridFlow

A high-performance parallel task scheduler written in C++, exposed to Python via pybind11, with a real-time Next.js monitoring dashboard.

The core engine implements a **lock-free work-stealing scheduler** — the same architecture used in production runtimes like Intel TBB and Java's ForkJoinPool. Tasks are defined in Python using a decorator API, compiled into a DAG by a C++ compiler stage, then executed across N threads with zero locks on the hot path.

---

## Architecture

```
Python @pipeline.task() decorator
        │
        ▼
  GridFlowPipeline (frontend/gridflow.py)
  · Builds PythonTask graph via pybind11
  · Wires dependency edges in C++
        │
        ▼
  DAG Compiler (compiler/dag_compiler.h)
  · Kahn's algorithm — topological sort
  · DFS cycle detector — catches illegal graphs before any thread fires
  · Linear chain fusion — merges A→B→C into one task to cut dispatch overhead
  · Critical path priority — assigns priorities in reverse topological order
        │
        ▼
  Scheduler (core/scheduler.h)
  · One Chase-Lev work-stealing deque per thread
  · Lock-free push/pop/steal with seq_cst fencing
  · HFT-style spin-wait before yielding (keeps cores hot)
  · Dependency counter: fetch_sub(1) on each dependent — fires when it hits 0
  · GIL released for pure C++ tasks, re-acquired only for Python callbacks
        │
        ▼
  Math Kernels (core/math_kernels.h)
  · transform_matrix — element-wise scalar multiply
  · dot_product_rows — row-chunked matrix multiply (parallelised across threads)
        │
        ▼
  FastAPI WebSocket gateway (backend/fastapi_server.py)
  · Streams live telemetry: CPU, memory, task progress, thread count
  · Four demo scenarios routed by scenario name
        │
        ▼
  Next.js dashboard (gridflow-ui/)
  · Live DAG visualizer — nodes animate through idle → running → done/error
  · Terminal log stream
  · Real-time metrics panel
```

---

## Project Structure

```
gridflow/
├── core/
│   ├── task.h                  # Task struct: id, payload, dependents, atomic counter
│   ├── scheduler.h             # Work-stealing scheduler — full implementation
│   ├── scheduler.cpp           # Stub (implementation is header-only)
│   ├── chase_lev_deque.h       # Lock-free deque interface
│   ├── chase_lev_deque.cpp     # push / pop / steal implementations
│   ├── math_kernels.h          # transform_matrix, dot_product_rows
│   └── memory_pool.h           # Thread-local slab allocator (O(1), no OS locks)
│
├── compiler/
│   ├── dag_compiler.h          # Orchestrates compile pipeline
│   ├── cycle_detector.h        # DFS cycle tracer with path output
│   ├── optimizer.h             # Linear chain fusion
│   └── graph_exporter.h        # Exports compiled DAG to Graphviz .dot format
│
├── bindings/
│   ├── gridflow_python.cpp     # pybind11 module — exposes Scheduler, DAGCompiler, PythonTask
│   └── gil_safe_task.h         # PythonTask: GIL acquire/release wrapper around Python callbacks
│
├── frontend/
│   └── gridflow.py             # Python API: @pipeline.task() decorator, GridFlowPipeline class
│
├── backend/
│   ├── fastapi_server.py       # WebSocket server, scenario router, telemetry poller
│   └── requirements.txt
│
├── network/
│   ├── tcp_master.cpp          # C++ cluster dispatcher: serializes tasks, routes to workers
│   ├── tcp_worker.cpp          # C++ worker node: receives binary payloads, runs on local engine
│   ├── serializer.h            # Fixed-layout TaskPayload struct, serialize/deserialize
│   └── registry.h              # NodeRegistry: register, health-check, mark_dead
│
├── tests/
│   ├── test_scheduler.cpp      # Stress test: 100k tasks across 8 threads, checks for races
│   ├── test_compiler.cpp       # Compiler tests: linear fusion + cycle traceback
│   └── test_memory.cpp         # Allocator benchmark: slab vs OS malloc across 8 threads
│
├── examples/
│   └── matrix_ops.py           # Standalone matrix multiply example using the Python API
│
├── gridflow-ui/                # Next.js dashboard
│   ├── app/page.tsx            # Main dashboard page
│   ├── components/
│   │   ├── dashbaord/
│   │   │   ├── dag-visualizer.tsx
│   │   │   └── terminal.tsx
│   │   └── ui/core.tsx
│   ├── hooks/use-engine-socket.ts
│   └── types/gridflow.ts
│
├── build_engine.py             # Compiles gridflow_cpp.pyd via MinGW g++
├── test_pipeline.py            # Quick end-to-end smoke test
└── network_master.py           # Python TCP dispatcher (mirrors tcp_master.cpp)
```

---

## Prerequisites

- Python 3.10+
- MinGW-w64 with g++ on PATH (Windows) or g++ (Linux/macOS)
- Node.js 18+

```bash
pip install pybind11 fastapi uvicorn psutil
```

---

## Build

Compile the C++ extension module:

```bash
python build_engine.py
```

This produces `gridflow_cpp.pyd` (Windows) or `gridflow_cpp.so` (Linux/macOS) in the project root. The build script locates your Python headers and pybind11 automatically.

If the build fails with a DLL error on Windows, make sure MinGW's `bin/` folder is on your `PATH` so g++ can find `libstdc++` and `libwinpthread`.

---

## Run

**1. Start the FastAPI backend**

```bash
cd backend
uvicorn fastapi_server:app --host 127.0.0.1 --port 8000
```

**2. Start the Next.js frontend**

```bash
cd gridflow-ui
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**3. (Optional) Run the Python smoke test**

```bash
python test_pipeline.py
```

---

## Demo Scenarios

Select a scenario from the dashboard dropdown and click **Deploy Pipeline**.

| Scenario | What it runs | Engine features shown |
|---|---|---|
| **Optimal Execution Path** | Allocates two matrices, transforms them in parallel, splits the dot product across N row-chunks | Work-stealing scheduler, GIL release, parallel C++ math |
| **Graph Cycle Detected** | Builds an illegal cyclic DAG (B→C→B), hands it to the compiler | Kahn's sort, DFS cycle tracer, compiler error halting |
| **Linear Chain Fusion** | Submits A→B→C→D, optimizer fuses into 2 tasks | DAGOptimizer, linear chain detection, dispatch reduction |
| **Network Worker Failure** | Dispatches tasks to two TCP worker nodes; one goes offline mid-run | NodeRegistry, TCP serializer, failover routing |

---

## Tests

```bash
# Scheduler stress test — 100k tasks, 8 threads, checks for races and duplicates
g++ -O2 -std=c++17 -pthread tests/test_scheduler.cpp core/chase_lev_deque.cpp -o test_sched
./test_sched

# Compiler tests — linear chain fusion + cycle traceback
g++ -O2 -std=c++17 tests/test_compiler.cpp core/chase_lev_deque.cpp -o test_compiler
./test_compiler

# Memory allocator benchmark — slab vs OS malloc, 8 threads × 1M allocs
g++ -O3 -std=c++17 -pthread tests/test_memory.cpp -o test_memory -I./core
./test_memory
```

---

## Key Design Decisions

**Why work-stealing?** A single shared queue becomes a bottleneck under contention. Each thread owning its own deque means the common case (pop from own queue) is contention-free. Stealing only happens when a thread runs dry, and the Chase-Lev algorithm makes steal lock-free too.

**Why header-only scheduler?** The scheduler is templated on its usage pattern and tightly coupled to the deque. Keeping it in a header avoids separate compilation complexity and lets the compiler inline the hot `worker_loop` path.

**Why release the GIL?** Python's GIL serialises all Python bytecode. If C++ threads re-entered Python without acquiring the GIL they'd corrupt the interpreter. `gil_safe_task.h` wraps each Python callback in `py::gil_scoped_acquire` — C++ math tasks skip this entirely and run in true parallel.

**Why slab allocation?** `new`/`delete` under contention serialize on the OS heap lock. The thread-local slab allocator pre-allocates chunks of 8192 nodes and serves alloc/dealloc in O(1) with zero inter-thread contention. The benchmark in `test_memory.cpp` shows the speedup on your machine.

---

## Network Layer

`network/` contains a standalone C++ cluster dispatcher that mirrors the Python `network_master.py`. Tasks are serialized into a fixed-layout `TaskPayload` struct (id, name[64], priority) and sent over raw TCP sockets. The worker node deserializes the payload, wraps it in a `Task`, and dispatches it to its local 8-core engine. The `NodeRegistry` tracks liveness and `mark_dead()` removes failed workers from the routing pool.

This layer is separate from the FastAPI server — it demonstrates how the same C++ engine can operate in a distributed setting without Python involved at all.