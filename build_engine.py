# File: build_engine.py
import os
import sys
import shutil
import pybind11

def build():
    print("=> Locating Python C++ headers...")

    pybind_include = pybind11.get_include()
    base_dir = os.path.dirname(sys.executable)
    python_include = os.path.join(base_dir, "include")
    python_libs = os.path.join(base_dir, "libs")
    py_version = f"python{sys.version_info.major}{sys.version_info.minor}"

    print(f"=> Found Python {sys.version_info.major}.{sys.version_info.minor} environment.")

    root = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(root, "gridflow_cpp.pyd")
    staging = os.path.join(root, "gridflow_cpp.build.pyd")

    cmd = (
        f'g++ -O3 -Wall -shared -std=c++17 -fPIC '
        f'-static-libgcc -static-libstdc++ -Wl,-Bstatic -lwinpthread -Wl,-Bdynamic '
        f'-I"{pybind_include}" -I"{python_include}" '
        f'bindings/gridflow_python.cpp core/chase_lev_deque.cpp '
        f'-o "{staging}" '
        f'-L"{python_libs}" -l{py_version}'
    )

    print("=> Executing MinGW Compiler:")
    print(cmd)

    if os.path.exists(staging):
        os.remove(staging)

    result = os.system(cmd)
    if result != 0:
        print("\n[FAILED] The compiler threw an error.")
        return 1

    try:
        if os.path.exists(target):
            os.remove(target)
        os.replace(staging, target)
    except PermissionError:
        print(
            "\n[FAILED] Cannot replace gridflow_cpp.pyd — it is locked by a running Python process.\n"
            "         Stop the FastAPI server (Ctrl+C), then run: python build_engine.py"
        )
        if os.path.exists(staging):
            print(f"         Staged build saved at: {staging}")
        return 1

    print("\n[SUCCESS] Compiled self-contained 'gridflow_cpp.pyd' successfully!")
    return 0

if __name__ == "__main__":
    raise SystemExit(build())
