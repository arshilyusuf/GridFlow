// File: network/registry.h
#pragma once
#include <vector>
#include <string>
#include <mutex>
#include <iostream>

struct WorkerNode {
    std::string ip;
    int port;
    bool is_alive;
};

class NodeRegistry {
    std::vector<WorkerNode> workers;
    std::mutex mtx;

public:
    void register_worker(const std::string& ip, int port) {
        std::lock_guard<std::mutex> lock(mtx);
        workers.push_back({ip, port, true});
        std::cout << "[Registry] Registered Worker Node at " << ip << ":" << port << "\n";
    }

    std::vector<WorkerNode> get_healthy_workers() {
        std::lock_guard<std::mutex> lock(mtx);
        std::vector<WorkerNode> healthy;
        for (const auto& w : workers) {
            if (w.is_alive) healthy.push_back(w);
        }
        return healthy;
    }

    void mark_dead(const std::string& ip, int port) {
        std::lock_guard<std::mutex> lock(mtx);
        for (auto& w : workers) {
            if (w.ip == ip && w.port == port) {
                w.is_alive = false;
                std::cout << "[Registry] FATAL: Node " << ip << ":" << port << " flatlined. Marked as DEAD.\n";
            }
        }
    }
};