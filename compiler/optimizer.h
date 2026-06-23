// File: compiler/optimizer.h
#pragma once

#include <vector>
#include <unordered_set>
#include "../core/task.h"

class DAGOptimizer {
public:
    static void fuse_linear_chains(std::vector<Task*>& tasks) {
        std::unordered_set<Task*> fused_and_removed;

        for (Task* current : tasks) {
            if (fused_and_removed.find(current) != fused_and_removed.end()) continue;

            // Check for a linear chain: Current has exactly 1 dependent, 
            // and that dependent has exactly 1 pending dependency (which is Current).
            while (current->dependents.size() == 1) {
                Task* child = current->dependents[0];
                
                if (child->pending_dependencies.load() == 1) {
                    // FUSION MATCH: Merge the child's payload into the current task
                    auto parent_work = current->work_payload;
                    auto child_work = child->work_payload;
                    
                    current->work_payload = [parent_work, child_work]() {
                        parent_work();
                        child_work();
                    };

                    // Inherit the child's dependents
                    current->dependents = child->dependents;
                    
                    // Mark the child for deletion from the graph
                    fused_and_removed.insert(child);
                } else {
                    break; // The child has other parents, cannot fuse safely.
                }
            }
        }

        // Clean up the task list by removing fused nodes
        std::vector<Task*> optimized_tasks;
        for (Task* t : tasks) {
            if (fused_and_removed.find(t) == fused_and_removed.end()) {
                optimized_tasks.push_back(t);
            } else {
                delete t; // Free the orphaned memory
            }
        }
        
        tasks = std::move(optimized_tasks);
    }
};