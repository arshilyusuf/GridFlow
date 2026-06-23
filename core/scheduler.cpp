// File: scheduler.cpp (Core Worker Loop)
#include "task.h"
#include "chase_lev_deque.h"
#include <vector>
#include <thread>
#include <random>

class Scheduler {
private:
    std::vector<WorkStealingDeque*> deques;
    std::atomic<bool> is_running{true};

public:
    // This is the function that runs on every thread
    void worker_loop(int my_thread_id, int total_threads) {
        
        // Fast random number generator for stealing
        thread_local std::mt19937 rng(my_thread_id);
        std::uniform_int_distribution<int> dist(0, total_threads - 1);

        WorkStealingDeque* my_deque = deques[my_thread_id];

        while (is_running.load(std::memory_order_relaxed)) {
            
            // 1. Try to take work from my own queue (Fast path)
            Task* task = my_deque->pop();

            // 2. If my queue is empty, try to steal (Slow path)
            if (task == nullptr) {
                int victim_id = dist(rng); // Pick a random thread
                if (victim_id != my_thread_id) {
                    task = deques[victim_id]->steal();
                }
            }

            // 3. If I got a task, execute it
            if (task != nullptr) {
                // Do the actual work
                task->work_payload();

                // 4. Resolve Dependencies Lock-Free
                for (Task* dependent : task->dependents) {
                    // Subtract 1 from the dependent's wait counter
                    int remaining = dependent->pending_dependencies.fetch_sub(1, std::memory_order_acq_rel) - 1;
                    
                    // If it hits 0, it's ready! Push it to my queue.
                    if (remaining == 0) {
                        my_deque->push(dependent);
                    }
                }
            } else {
                // Optional: yield the thread briefly if completely starved of work
                std::this_thread::yield();
            }
        }
    }
};  