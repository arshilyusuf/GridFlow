// File: task.h
#pragma once

#include <vector>
#include <atomic>
#include <functional>

struct Task {
    int id;
    // Add this line inside the Task struct in core/task.h
    int priority{0};
    // The actual work to be done (e.g., loading data, math)
    std::function<void()> work_payload;
    
    // Tasks that cannot start until THIS task finishes
    std::vector<Task*> dependents;
    
    // How many tasks THIS task is waiting on before it can start
    std::atomic<int> pending_dependencies{0};

    Task(int task_id, std::function<void()> payload) 
        : id(task_id), work_payload(std::move(payload)) {}
};