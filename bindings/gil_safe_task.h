// File: bindings/gil_safe_task.h
#pragma once

#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include "../core/task.h"

namespace py = pybind11;

// Inherit from your core Task, but make it Python-aware
struct PythonTask : public Task {
    py::function py_payload;

    PythonTask(int id, py::function func) : Task(id, [](){}), py_payload(func) {
        
        // Override the base C++ work_payload with a GIL-safe lambda
        this->work_payload = [this]() {
            try {
                // ACQUIRE THE GIL: Only one C++ thread can talk to Python at a time.
                // If a thread is executing native C++ math, it doesn't need this.
                py::gil_scoped_acquire acquire;
                
                // Execute the Python researcher's code
                this->py_payload();
                
            } catch (py::error_already_set& e) {
                // Safely catch Python exceptions and print them in C++
                std::cerr << "[GridFlow C++ Engine] Python Exception in Task " 
                          << this->id << ":\n" << e.what() << std::endl;
            }
        };
    }
};