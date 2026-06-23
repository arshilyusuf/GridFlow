// File: compiler/graph_exporter.h
#pragma once

#include <vector>
#include <string>
#include <fstream>
#include "../core/task.h"

class GraphExporter {
public:
    static void export_to_dot(const std::vector<Task*>& tasks, const std::string& filename) {
        std::ofstream file(filename);
        if (!file.is_open()) {
            throw std::runtime_error("Failed to open file for graph export.");
        }

        file << "digraph GridFlow_DAG {\n";
        file << "    node [shape=box, style=filled, color=lightblue];\n";

        // Write nodes with their calculated compiler priority
        for (Task* t : tasks) {
            file << "    T" << t->id << " [label=\"Task " << t->id 
                 << "\\nPriority: " << t->priority << "\"];\n";
        }

        file << "\n";

        // Write directed edges (Dependencies)
        for (Task* t : tasks) {
            for (Task* dependent : t->dependents) {
                file << "    T" << t->id << " -> T" << dependent->id << ";\n";
            }
        }

        file << "}\n";
        file.close();
    }
};