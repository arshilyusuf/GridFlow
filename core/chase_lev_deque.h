// File: chase_lev_deque.h
#pragma once

#include <atomic>
#include <stdexcept>
#include <cstdint>

// Forward declaration of our Task struct (will hold DAG node info later)
struct Task; 

class WorkStealingDeque {
private:
    // Capacity MUST be a power of 2 for bitwise modulo (CAPACITY - 1)
    static constexpr size_t CAPACITY = 131072; 
    static constexpr size_t MASK = CAPACITY - 1;

    // The circular buffer holding task pointers
    std::atomic<Task*> buffer[CAPACITY];

    // Top is modified by thieves (stealing), read by owner
    std::atomic<int64_t> top;

    // Bottom is modified ONLY by the owner (push/pop), read by thieves
    std::atomic<int64_t> bottom;

public:
    WorkStealingDeque() : top(0), bottom(0) {
        // Initialize buffer with nullptrs
        for (size_t i = 0; i < CAPACITY; ++i) {
            buffer[i].store(nullptr, std::memory_order_relaxed);
        }
    }
    // Add to public section of WorkStealingDeque in chase_lev_deque.h
size_t size() const {
    int64_t b = bottom.load(std::memory_order_relaxed);
    int64_t t = top.load(std::memory_order_relaxed);
    return (b >= t) ? static_cast<size_t>(b - t) : 0;
}
bool empty() const {
    int64_t b = bottom.load(std::memory_order_relaxed);
    int64_t t = top.load(std::memory_order_relaxed);
    return b <= t;
}
    // Owner only
    void push(Task* task);
    Task* pop();

    // Thieves only
    Task* steal();
};