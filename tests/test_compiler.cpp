// File: tests/test_compiler.cpp
#include <iostream>
#include <vector>
#include <string>
#include "../core/task.h"
#include "../compiler/dag_compiler.h"
#include "../compiler/graph_exporter.h"

struct NamedTask : public Task {
    std::string name;
    NamedTask(int id, std::string n) : Task(id, [](){}), name(n) {}
};

void run_optimizer_and_export_test() {
    std::cout << "==========================================\n";
    std::cout << " TEST 1: LINEAR OPTIMIZATION & EXPORT\n";
    std::cout << "==========================================\n";

    NamedTask* t0 = new NamedTask(0, "Load Data");
    NamedTask* t1 = new NamedTask(1, "Clean Data (Linear)");
    NamedTask* t2 = new NamedTask(2, "Format Data (Linear)");
    NamedTask* t3 = new NamedTask(3, "Train Model");

    // Create a strict straight line: Load -> Clean -> Format -> Train
    t0->dependents.push_back(t1);
    t1->pending_dependencies.store(1);

    t1->dependents.push_back(t2);
    t2->pending_dependencies.store(1);

    t2->dependents.push_back(t3);
    t3->pending_dependencies.store(1);

    std::vector<Task*> tasks = {t0, t1, t2, t3};

    try {
        std::vector<Task*> execution_order = DAGCompiler::compile(tasks);
        std::cout << "[SUCCESS] Graph compiled.\n";
        
        // Export the optimized graph
        GraphExporter::export_to_dot(execution_order, "pipeline_graph.dot");
        std::cout << "[SUCCESS] Exported optimized visual graph to 'pipeline_graph.dot'.\n\n";

    } catch (const std::exception& e) {
        std::cout << "[FAILED] Unexpected error: " << e.what() << "\n";
    }
}

void run_cycle_traceback_test() {
    std::cout << "==========================================\n";
    std::cout << " TEST 2: CYCLE TRACEBACK ENGINE\n";
    std::cout << "==========================================\n";

    NamedTask* t0 = new NamedTask(10, "Initialize");
    NamedTask* t1 = new NamedTask(11, "Calculate Weights");
    NamedTask* t2 = new NamedTask(12, "Update Matrix");

    // Initialize -> Calculate
    t0->dependents.push_back(t1);
    t1->pending_dependencies.store(1);

    // Calculate -> Update
    t1->dependents.push_back(t2);
    t2->pending_dependencies.store(1);

    // Update -> Calculate (THE FATAL CYCLE)
    t2->dependents.push_back(t1);
    t1->pending_dependencies.fetch_add(1);

    std::vector<Task*> bad_tasks = {t0, t1, t2};

    try {
        std::vector<Task*> execution_order = DAGCompiler::compile(bad_tasks);
        std::cout << "[FAIL] Compiler missed the cycle!\n";
    } catch (const std::runtime_error& e) {
        std::cout << "[SUCCESS] Intercepted and traced. Output:\n";
        std::cout << e.what() << "\n";
    }
}

int main() {
    run_optimizer_and_export_test();
    std::cout << "\n";
    run_cycle_traceback_test();
    return 0;
}