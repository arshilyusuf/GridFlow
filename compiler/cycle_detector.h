// File: compiler/cycle_detector.h
#pragma once

#include <vector>
#include <string>
#include <unordered_set>
#include <stdexcept>
#include "../core/task.h"

class CycleDetector {
public:
    static std::string trace_cycle(const std::vector<Task*>& tasks) {
        std::unordered_set<Task*> visited;
        std::unordered_set<Task*> recursion_stack;
        std::vector<Task*> path;

        for (Task* t : tasks) {
            if (visited.find(t) == visited.end()) {
                if (dfs_visit(t, visited, recursion_stack, path)) {
                    return format_path(path);
                }
            }
        }
        return "No cycle detected.";
    }

private:
    static bool dfs_visit(Task* current, 
                          std::unordered_set<Task*>& visited, 
                          std::unordered_set<Task*>& recursion_stack,
                          std::vector<Task*>& path) {
        
        visited.insert(current);
        recursion_stack.insert(current);
        path.push_back(current);

        for (Task* dependent : current->dependents) {
            // If the dependent is already in the current traversal stack, we hit a cycle!
            if (recursion_stack.find(dependent) != recursion_stack.end()) {
                path.push_back(dependent); // Add it one last time to complete the visual loop
                return true; 
            }
            if (visited.find(dependent) == visited.end()) {
                if (dfs_visit(dependent, visited, recursion_stack, path)) {
                    return true;
                }
            }
        }

        recursion_stack.erase(current);
        path.pop_back();
        return false;
    }

    static std::string format_path(const std::vector<Task*>& path) {
        std::string result = "Cycle isolated: ";
        for (size_t i = 0; i < path.size(); ++i) {
            result += "Task_" + std::to_string(path[i]->id);
            if (i < path.size() - 1) result += " -> ";
        }
        return result;
    }
};