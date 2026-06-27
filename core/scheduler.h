// File: scheduler.h
#pragma once

#include <vector>
#include <thread>
#include <atomic>
#include <random>
#include "task.h"
#include "chase_lev_deque.h"

class Scheduler {
private:
    std::vector<WorkStealingDeque*> deques;
    std::atomic<bool> is_running{true};
    std::atomic<int> active_workers{0};
    std::atomic<int> tasks_completed{0};
    std::atomic<int> expected_tasks{0};

public:
    Scheduler(int num_threads) {
        for (int i = 0; i < num_threads; ++i) {
            deques.push_back(new WorkStealingDeque());
        }
    }

    ~Scheduler() {
        for (auto d : deques) {
            delete d;
        }
    }

    WorkStealingDeque* get_deque(int thread_id) {
        return deques[thread_id];
    }

    void stop() {
        is_running.store(false, std::memory_order_relaxed);
    }

    void reset_for_run(int total_tasks) {
        is_running.store(true, std::memory_order_relaxed);
        tasks_completed.store(0, std::memory_order_relaxed);
        active_workers.store(0, std::memory_order_relaxed);
        expected_tasks.store(total_tasks, std::memory_order_relaxed);
    }

    bool is_idle() const {
        if (active_workers.load(std::memory_order_acquire) > 0) {
            return false;
        }
        for (auto d : deques) {
            if (!d->empty()) {
                return false;
            }
        }
        return true;
    }
    // 1. Get number of active threads (total deques)
int get_active_threads() const {
    return static_cast<int>(deques.size());
}

// 2. Get total task count across all deques (load)
int get_total_task_count() {
    int count = 0;
    for (auto d : deques) {
        // You'll need to ensure WorkStealingDeque has a .size() method
        count += d->size(); 
    }
    return count;
}
size_t get_total_tasks_queued() {
    size_t total = 0;
    for (auto d : deques) total += d->size();
    return total;
}

// Simple approximation of active thread load
int get_active_worker_count() const {
    return active_workers.load(std::memory_order_relaxed);
}

int get_tasks_completed() const {
    return tasks_completed.load(std::memory_order_relaxed);
}

// 3. Engine utilization based on workers actively executing tasks
double get_cpu_utilization() const {
    if (deques.empty()) return 0.0;
    return static_cast<double>(active_workers.load(std::memory_order_relaxed))
         / static_cast<double>(deques.size()) * 100.0;
}
    void worker_loop(int my_thread_id, int total_threads) {
        thread_local std::mt19937 rng(my_thread_id);
        std::uniform_int_distribution<int> dist(0, total_threads - 1);
        WorkStealingDeque* my_deque = deques[my_thread_id];

        int spin_count = 0; // HFT backoff counter

        while (is_running.load(std::memory_order_relaxed)) {
            Task* task = my_deque->pop();

            if (task == nullptr) {
                int victim_id = dist(rng);
                if (victim_id != my_thread_id) {
                    task = deques[victim_id]->steal();
                }
            }

            if (task != nullptr) {
                spin_count = 0; // Reset spin counter on successful work
                active_workers.fetch_add(1, std::memory_order_relaxed);
                task->work_payload();
                active_workers.fetch_sub(1, std::memory_order_relaxed);
                tasks_completed.fetch_add(1, std::memory_order_relaxed);

                for (Task* dependent : task->dependents) {
                    int remaining = dependent->pending_dependencies.fetch_sub(1, std::memory_order_acq_rel) - 1;
                    if (remaining == 0) {
                        my_deque->push(dependent);
                    }
                }
            } else {
                // HFT Spin-Wait Logic (Keep the CPU awake!)
                spin_count++;
                if (spin_count < 1000) {
                    // Do nothing, just burn a few cycles to stay hot
                } else {
                    // ONLY yield if we've been starving for a long time
                    std::this_thread::yield(); 
                }
            }
        }
    }
};