// File: chase_lev_deque.cpp
#include "chase_lev_deque.h"

void WorkStealingDeque::push(Task* task) {
    // Owner reads its own bottom index. Relaxed is safe because no one else modifies it.
    int64_t b = bottom.load(std::memory_order_relaxed);
    
    // Read top to check for queue full. 
    // Acquire ensures we see the most recent steals from other threads.
    int64_t t = top.load(std::memory_order_acquire);

    // If the queue is full, we must abort or resize. 
    // For this implementation, we throw to keep the atomics clear.
    if (b - t >= static_cast<int64_t>(CAPACITY)) {
        throw std::runtime_error("WorkStealingDeque capacity exceeded!");
    }

    // Write the task pointer into the circular buffer. 
    // Relaxed is fine here because the thief can't see it until bottom updates.
    buffer[b & MASK].store(task, std::memory_order_relaxed);

    // CRITICAL MEMORY BARRIER
    // We must ensure the task pointer is visible to all cores BEFORE bottom updates.
    std::atomic_thread_fence(std::memory_order_release);

    // Increment bottom. Relaxed is used because the fence above handles the ordering.
    bottom.store(b + 1, std::memory_order_relaxed);
}

// File: chase_lev_deque.cpp (Continued)

Task* WorkStealingDeque::pop() {
    // 1. You move your sticky note back one space (claiming the item)
    int64_t b = bottom.load(std::memory_order_relaxed) - 1;
    // buffer[b & MASK].store(nullptr, std::memory_order_relaxed); //  cleanup
    bottom.store(b, std::memory_order_relaxed);
    
    // Memory Barrier: Ensure the new 'bottom' is visible before we check 'top'
    std::atomic_thread_fence(std::memory_order_seq_cst);

    // 2. See where the thieves are
    int64_t t = top.load(std::memory_order_relaxed);
    
    Task* task = nullptr;

    if (t <= b) {
        // Safe zone: There is at least one item left. Grab it.
        task = buffer[b & MASK].load(std::memory_order_relaxed);
        
        if (t == b) {
            // DANGER ZONE: This is the VERY LAST ITEM.
            // A thief might be stealing this exact item right now.
            
            // We use 'compare_exchange_strong' to race the thief.
            // "If 'top' is still equal to 't', change 'top' to 't + 1'."
            if (!top.compare_exchange_strong(t, t + 1, 
                                             std::memory_order_seq_cst, 
                                             std::memory_order_relaxed)) {
                // We lost the race. The thief got it first.
                task = nullptr; 
            }
            // Reset the tray to empty
            bottom.store(t + 1, std::memory_order_relaxed);
        }
    } else {
        // The tray was already empty.
        bottom.store(t, std::memory_order_relaxed);
    }

    return task;
}

Task* WorkStealingDeque::steal() {
    // 1. Look at where the top is
    int64_t t = top.load(std::memory_order_acquire);
    
    // Memory Barrier: Ensure we see the latest 'bottom'
    std::atomic_thread_fence(std::memory_order_seq_cst);
    
    // 2. Look at where the owner's bottom is
    int64_t b = bottom.load(std::memory_order_acquire);

    if (t < b) {
        // There is at least one item to steal! Grab the pointer.
        Task* task = buffer[t & MASK].load(std::memory_order_relaxed);

        // RACE CONDITION: Another thief (or the owner) might be grabbing this too.
        // We use the CAS mouse trap again.
        if (!top.compare_exchange_strong(t, t + 1, 
                                         std::memory_order_seq_cst, 
                                         std::memory_order_relaxed)) {
            // We lost the race to another thief. Return nothing.
            return nullptr;
        }

        // We won the race! The task is ours.
        return task;
    }

    // The tray is empty.
    return nullptr;
}