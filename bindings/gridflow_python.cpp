// File: bindings/gridflow_python.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "../core/scheduler.h"
#include "../compiler/dag_compiler.h"
#include "gil_safe_task.h"
#include "../core/math_kernels.h"
namespace py = pybind11;

PYBIND11_MODULE(gridflow_cpp, m) {
    m.doc() = "GridFlow High-Performance C++ Execution Engine";
m.def("transform_matrix", &transform_matrix);
m.def("dot_product", &dot_product);
m.def("dot_product_rows", &dot_product_rows);
    // Expose the Task object to Python
    py::class_<Task>(m, "Task");

    // Expose our specialized PythonTask
    py::class_<PythonTask, Task>(m, "PythonTask")
        .def(py::init<int, py::function>())
        .def("add_dependent", [](PythonTask& self, PythonTask& dependent) {
            self.dependents.push_back(&dependent);
            dependent.pending_dependencies.fetch_add(1, std::memory_order_relaxed);
        });

    // Expose the Compiler
    py::class_<DAGCompiler>(m, "DAGCompiler")
        .def_static("compile", [](std::vector<PythonTask*>& tasks) {
            std::vector<Task*> base_tasks(tasks.begin(), tasks.end());
            return DAGCompiler::compile(base_tasks);
        });

    // Expose the Engine/Scheduler
    py::class_<Scheduler>(m, "Scheduler")
        .def(py::init<int>()) 
        .def("push_task", [](Scheduler& self, Task* task, int thread_id) {
            self.get_deque(thread_id)->push(task);
        })
        .def("run_workers", [](Scheduler& self, int num_threads, int total_tasks) {
            py::gil_scoped_release release;

            self.reset_for_run(total_tasks);
            std::vector<std::thread> workers;
            for (int i = 0; i < num_threads; ++i) {
                workers.emplace_back([&self, i, num_threads]() {
                    self.worker_loop(i, num_threads);
                });
            }

            while (self.get_tasks_completed() < total_tasks) {
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }

            self.stop();
            for (auto& w : workers) {
                if (w.joinable()) w.join();
            }
        })
        .def("get_active_threads", &Scheduler::get_active_threads)
        .def("get_total_task_count", &Scheduler::get_total_task_count)
        .def("get_cpu_utilization", &Scheduler::get_cpu_utilization)
        .def("get_total_tasks_queued", &Scheduler::get_total_tasks_queued)
        .def("get_active_worker_count", &Scheduler::get_active_worker_count)
        .def("get_tasks_completed", &Scheduler::get_tasks_completed);
}