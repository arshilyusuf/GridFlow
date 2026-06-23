// File: compiler/dag_compiler.h
#pragma once

#include <vector>
#include <unordered_map>
#include <queue>
#include <stdexcept>
#include <algorithm>
#include <iostream>
#include "../core/task.h"
#include "cycle_detector.h"
#include "optimizer.h"

class DAGCompiler {
public:
    static std::vector<Task*> compile(std::vector<Task*>& all_tasks) {
        
        // 1. Optimize the graph before doing any heavy math
        size_t original_size = all_tasks.size();
        DAGOptimizer::fuse_linear_chains(all_tasks);
        if (all_tasks.size() < original_size) {
            std::cout << "[COMPILER] Optimizer fused " 
                      << (original_size - all_tasks.size()) << " linear tasks.\n";
        }

        // 2. Kahn's Algorithm for Topological Sorting
        std::vector<Task*> topo_order = topological_sort(all_tasks);

        // 3. Cycle Detection Intercept
        if (topo_order.size() != all_tasks.size()) {
            std::string trace = CycleDetector::trace_cycle(all_tasks);
            throw std::runtime_error("FATAL COMPILER ERROR: \n" + trace);
        }

        // 4. Calculate Critical Path Priorities
        assign_critical_path_priorities(topo_order);

        return topo_order;
    }

private:
    static std::vector<Task*> topological_sort(const std::vector<Task*>& tasks) {
        std::unordered_map<Task*, int> in_degree;
        for (Task* t : tasks) {
            in_degree[t] = t->pending_dependencies.load(std::memory_order_relaxed);
        }

        std::queue<Task*> zero_in_degree;
        for (Task* t : tasks) {
            if (in_degree[t] == 0) zero_in_degree.push(t);
        }

        std::vector<Task*> sorted;
        while (!zero_in_degree.empty()) {
            Task* current = zero_in_degree.front();
            zero_in_degree.pop();
            sorted.push_back(current);

            for (Task* dependent : current->dependents) {
                in_degree[dependent]--;
                if (in_degree[dependent] == 0) {
                    zero_in_degree.push(dependent);
                }
            }
        }
        return sorted;
    }

    static void assign_critical_path_priorities(const std::vector<Task*>& topo_order) {
        for (auto it = topo_order.rbegin(); it != topo_order.rend(); ++it) {
            Task* current = *it;
            int max_child_priority = 0;
            for (Task* dependent : current->dependents) {
                max_child_priority = std::max(max_child_priority, dependent->priority);
            }
            current->priority = max_child_priority + 1;
        }
    }
};