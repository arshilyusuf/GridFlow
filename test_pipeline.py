# File: test_pipeline.py
import time
import sys
import os
import shutil

# --- THE WINDOWS DLL SECURITY PATCH ---
# Python 3.8+ ignores the system PATH. We dynamically find your MinGW compiler
# and explicitly whitelist its bin folder so Python can load the C++ runtime DLLs.
if os.name == 'nt':
    gpp_path = shutil.which("g++")
    if gpp_path:
        mingw_bin = os.path.dirname(gpp_path)
        print(f"=> [System] Whitelisting MinGW DLL directory: {mingw_bin}")
        os.add_dll_directory(mingw_bin)
    else:
        print("=> [System] Warning: Could not find g++ on PATH.")

# Add the frontend folder so we can import our API wrapper
sys.path.append('./frontend')
from gridflow import GridFlowPipeline

# Initialize the 8-core C++ engine
pipeline = GridFlowPipeline(num_threads=8)

# --- Define the Machine Learning DAG using Python Decorators ---

@pipeline.task()
def load_data():
    print("[Python Task] Loading 10GB dataset into memory...")
    time.sleep(0.5) # Simulating heavy I/O

@pipeline.task(depends_on=[load_data])
def normalize_data():
    print("[Python Task] Normalizing arrays...")
    time.sleep(0.5) # Simulating CPU work

@pipeline.task(depends_on=[load_data])
def initialize_weights():
    print("[Python Task] Booting neural net architecture...")
    time.sleep(0.5)

@pipeline.task(depends_on=[normalize_data, initialize_weights])
def train_model():
    print("[Python Task] Backpropagating loss (Heavy Math)...")
    time.sleep(1.0)

if __name__ == "__main__":
    print("===========================================")
    print("   GRIDFLOW DISTRIBUTED ML PIPELINE TEST   ")
    print("===========================================\n")
    
    # This triggers Kahn's Algorithm, releases the GIL, and fires up the C++ threads
    pipeline.execute()