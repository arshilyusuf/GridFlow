// File: memory_pool.h
#pragma once
#include <vector>
#include <cstdint>

template <typename T, size_t CHUNK_SIZE = 8192>
class ThreadLocalSlabAllocator {
private:
    // A Union means these two variables share the EXACT same memory address.
    // If it's free, it holds 'next'. If it's in use, it holds 'data'.
    union Node {
        T data;
        Node* next;
        
        // Constructor to satisfy C++ union rules for complex types
        Node() {} 
        ~Node() {}
    };

    Node* free_list = nullptr;
    std::vector<Node*> allocated_chunks;

    // Grab a massive new chunk of memory from the OS and chop it up
    void allocate_new_chunk() {
        Node* chunk = new Node[CHUNK_SIZE];
        allocated_chunks.push_back(chunk);

        // Link all the new pieces together into a chain
        for (size_t i = 0; i < CHUNK_SIZE - 1; ++i) {
            chunk[i].next = &chunk[i + 1];
        }
        chunk[CHUNK_SIZE - 1].next = nullptr; // End of the chain
        
        free_list = chunk;
    }

public:
    ThreadLocalSlabAllocator() {}

    ~ThreadLocalSlabAllocator() {
        // Return all the massive chunks to the OS when the thread dies
        for (Node* chunk : allocated_chunks) {
            delete[] chunk;
        }
    }

    // O(1) Allocation without OS locks
    T* allocate() {
        if (!free_list) {
            allocate_new_chunk();
        }
        // Pop the first available node off the free list
        Node* node = free_list;
        free_list = free_list->next;
        
        return reinterpret_cast<T*>(node);
    }

    // O(1) Deallocation without OS locks
    void deallocate(T* ptr) {
        if (!ptr) return;
        
        // Push the used memory back onto the front of the free list
        Node* node = reinterpret_cast<Node*>(ptr);
        node->next = free_list;
        free_list = node;
    }
};

// Global function to get a unique allocator for whichever thread calls it
template<typename T>
ThreadLocalSlabAllocator<T>& get_thread_local_allocator() {
    // The 'thread_local' keyword guarantees every thread gets its own isolated pool!
    thread_local ThreadLocalSlabAllocator<T> allocator;
    return allocator;
}