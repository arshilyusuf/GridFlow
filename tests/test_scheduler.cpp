// File: test_scheduler.cpp
#include <iostream>
#include <vector>
#include <thread>
#include <chrono>
#include <atomic>
#include "task.h"
#include "chase_lev_deque.h"
#include "scheduler.h"

constexpr int NUM_TASKS = 100000;
constexpr int NUM_THREADS = 8;

std::atomic<int> execution_tracker[NUM_TASKS];
std::atomic<int> total_completed{0}; // NEW: Track total completions

int main() {
    std::cout << "Starting Concurrent Stress Test..." << std::endl;

    for (int i = 0; i < NUM_TASKS; ++i) {
        execution_tracker[i].store(0, std::memory_order_relaxed);
    }

    Scheduler engine(NUM_THREADS); 

    for (int i = 0; i < NUM_TASKS; ++i) {
        Task* t = new Task(i, [i]() {
            execution_tracker[i].fetch_add(1, std::memory_order_relaxed);
            total_completed.fetch_add(1, std::memory_order_relaxed); // Increment global counter
        });
        engine.get_deque(0)->push(t); 
    }

    std::vector<std::thread> workers;
    for (int i = 0; i < NUM_THREADS; ++i) {
        workers.emplace_back([&engine, i]() {
            engine.worker_loop(i, NUM_THREADS);
        });
    }

    // NEW SDET WAITING LOGIC
    // Wait until all tasks are done, with a 10-second timeout
    auto start_time = std::chrono::steady_clock::now();
    while (total_completed.load(std::memory_order_relaxed) < NUM_TASKS) {
        if (std::chrono::steady_clock::now() - start_time > std::chrono::seconds(10)) {
            std::cout << "Test timed out after 10 seconds!" << std::endl;
            break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    
    engine.stop(); 
    
    for (auto& w : workers) {
        if (w.joinable()) w.join();
    }

    int missing = 0;
    int duplicated = 0;

    for (int i = 0; i < NUM_TASKS; ++i) {
        int count = execution_tracker[i].load(std::memory_order_relaxed);
        if (count == 0) missing++;
        if (count > 1) duplicated++;
    }

    if (missing == 0 && duplicated == 0) {
        std::cout << "[PASS] 100,000 tasks executed perfectly across " << NUM_THREADS << " threads." << std::endl;
    } else {
        std::cout << "[FAIL] Data corruption detected!" << std::endl;
        std::cout << "Missing tasks: " << missing << std::endl;
        std::cout << "Duplicated tasks: " << duplicated << std::endl;
    }

    return 0;
}