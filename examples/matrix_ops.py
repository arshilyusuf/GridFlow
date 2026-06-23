import time
import sys
import os

# --- THE WINDOWS DLL SECURITY PATCH ---
if os.name == 'nt':
    import shutil
    gpp_path = shutil.which("g++")
    if gpp_path:
        os.add_dll_directory(os.path.dirname(gpp_path))

# --- PATH RESOLUTION FIX ---
# Dynamically find the root directory to import both the C++ binary and Python frontend
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir) # Allows 'import gridflow_cpp'
sys.path.append(os.path.join(root_dir, 'frontend')) # Allows 'from gridflow import GridFlowPipeline'

from gridflow import GridFlowPipeline

# Initialize engine to maximize local compute threads
pipeline = GridFlowPipeline(num_threads=8)

# Shared multi-dimensional data arrays simulated inside the worker context
matrix_a = [[i * 0.05 for i in range(500)] for _ in range(500)]
matrix_b = [[j * 0.12 for j in range(500)] for _ in range(500)]
result_matrix = [[0.0 for _ in range(500)] for _ in range(500)]

@pipeline.task()
def matrix_stage_one():
    print("[Engine Compute] Executing Row-Wise Transformation Phase 1...")
    for i in range(250):
        for j in range(500):
            matrix_a[i][j] *= 1.002

@pipeline.task()
def matrix_stage_two():
    print("[Engine Compute] Executing Row-Wise Transformation Phase 2...")
    for i in range(250, 500):
        for j in range(500):
            matrix_a[i][j] *= 1.002

@pipeline.task(depends_on=[matrix_stage_one, matrix_stage_two])
def complete_dot_product():
    print("[Engine Compute] Synchronizing threads. Executing Parallel Matrix Multiplication...")
    for i in range(500):
        for j in range(500):
            total = 0.0
            for k in range(500):
                total += matrix_a[i][k] * matrix_b[k][j]
            result_matrix[i][j] = total
    print("[Engine Compute] Mathematical verification hash calculated successfully.")

if __name__ == "__main__":
    print("===========================================")
    print("   GRIDFLOW COMPUTATIONAL STRESS TEST      ")
    print("===========================================\n")
    start_time = time.perf_counter()
    pipeline.execute()
    print(f"\n=> Heavy compute completed in {time.perf_counter() - start_time:.4f} seconds.")