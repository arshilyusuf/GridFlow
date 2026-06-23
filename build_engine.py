# File: build_engine.py
import os
import sys
import pybind11

def build():
    print("=> Locating Python C++ headers...")
    
    # 1. Get PyBind11 headers
    pybind_include = pybind11.get_include()
    
    # 2. Get native Python headers and libraries
    base_dir = os.path.dirname(sys.executable)
    python_include = os.path.join(base_dir, "include")
    python_libs = os.path.join(base_dir, "libs")
    
    # Extract version (e.g., python313)
    py_version = f"python{sys.version_info.major}{sys.version_info.minor}"

    print(f"=> Found Python {sys.version_info.major}.{sys.version_info.minor} environment.")

    # 3. Construct the MinGW compilation command with static linking flags
    cmd = (
        f'g++ -O3 -Wall -shared -std=c++17 -fPIC '
        f'-static-libgcc -static-libstdc++ -Wl,-Bstatic -lwinpthread -Wl,-Bdynamic '
        f'-I"{pybind_include}" -I"{python_include}" '
        f'bindings/gridflow_python.cpp core/chase_lev_deque.cpp '
        f'-o gridflow_cpp.pyd '
        f'-L"{python_libs}" -l{py_version}'
    )

    print("=> Executing MinGW Compiler:")
    print(cmd)
    
    # 4. Run the compiler
    result = os.system(cmd)
    
    if result == 0:
        print("\n[SUCCESS] Compiled self-contained 'gridflow_cpp.pyd' successfully!")
    else:
        print("\n[FAILED] The compiler threw an error.")

if __name__ == "__main__":
    build()