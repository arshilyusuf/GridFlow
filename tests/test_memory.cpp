// File: test_memory.cpp
#include <iostream>
#include <vector>
#include <thread>
#include <chrono>
#include <iomanip>
#include <atomic>
#include "memory_pool.h"

constexpr int NUM_THREADS = 8;
constexpr int ALLOCATIONS_PER_THREAD = 1000000;

struct DummyTask {
    int id;
    void* payload_ptr;
    void* dependents_ptr;
    int padding[8]; 
};

// NEW: A global sink to prevent compiler Dead Code Elimination
std::atomic<uint64_t> optimization_blocker{0};

// ========================================================================
// TEST 1: The Standard OS Heap (malloc/new)
// ========================================================================
void standard_malloc_worker() {
    uint64_t local_sum = 0;
    for (int i = 0; i < ALLOCATIONS_PER_THREAD; ++i) {
        DummyTask* t = new DummyTask();
        t->id = i;
        
        // Force the compiler to use the physical memory address
        local_sum += reinterpret_cast<uintptr_t>(t) + t->id; 
        
        delete t;
    }
    // Dump the result into a global atomic
    optimization_blocker.fetch_add(local_sum, std::memory_order_relaxed);
}

// ========================================================================
// TEST 2: The Thread-Local Slab Allocator
// ========================================================================
void slab_allocator_worker() {
    auto& pool = get_thread_local_allocator<DummyTask>();
    uint64_t local_sum = 0;
    
    for (int i = 0; i < ALLOCATIONS_PER_THREAD; ++i) {
        DummyTask* t = pool.allocate();
        t->id = i;
        
        local_sum += reinterpret_cast<uintptr_t>(t) + t->id;
        
        pool.deallocate(t);
    }
    optimization_blocker.fetch_add(local_sum, std::memory_order_relaxed);
}

// ========================================================================
// BENCHMARK HARNESS
// ========================================================================
template <typename Func>
double run_benchmark(Func worker_function, const std::string& test_name) {
    std::cout << "Running: " << test_name << " (" << NUM_THREADS 
              << " threads, " << (NUM_THREADS * ALLOCATIONS_PER_THREAD) 
              << " total allocations)..." << std::endl;

    auto start_time = std::chrono::high_resolution_clock::now();

    std::vector<std::thread> threads;
    for (int i = 0; i < NUM_THREADS; ++i) {
        threads.emplace_back(worker_function);
    }

    for (auto& t : threads) {
        t.join();
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> duration = end_time - start_time;
    
    std::cout << "Time taken: " << std::fixed << std::setprecision(4) 
              << duration.count() << " seconds\n" << std::endl;
              
    return duration.count();
}

int main() {
    std::cout << "==========================================\n";
    std::cout << "   GRIDFLOW MEMORY ALLOCATOR BENCHMARK    \n";
    std::cout << "==========================================\n\n";

    double time_malloc = run_benchmark(standard_malloc_worker, "Standard OS Malloc (new/delete)");
    double time_slab = run_benchmark(slab_allocator_worker, "Thread-Local Slab Allocator");

    std::cout << "==========================================\n";
    std::cout << "                 RESULTS                  \n";
    std::cout << "==========================================\n";
    
    // Print the blocker so the compiler absolutely cannot optimize it out
    std::cout << "(Optimization sink check: " << optimization_blocker.load() << ")\n\n";

    if (time_slab < time_malloc) {
        double speedup = time_malloc / time_slab;
        std::cout << "[SUCCESS] Custom Allocator is " << std::fixed << std::setprecision(2) 
                  << speedup << "x FASTER than OS Malloc.\n";
    } else {
        std::cout << "[WARNING] OS Malloc was faster.\n";
    }

    return 0;
}