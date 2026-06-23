// File: network/serializer.h
#pragma once
#include <vector>
#include <string>
#include <cstring>

// A packed struct representing the exact byte layout we will send over the wire
struct TaskPayload {
    int id;
    char name[64]; // Fixed-size char array prevents dynamic memory issues over sockets
    int priority;
};

class Serializer {
public:
    // Flattens task data into a raw byte array
    static std::vector<char> serialize(int id, const std::string& name, int priority) {
        TaskPayload p;
        p.id = id;
        
        // Safely copy the string into the fixed buffer, ensuring null-termination
        std::strncpy(p.name, name.c_str(), sizeof(p.name) - 1);
        p.name[sizeof(p.name) - 1] = '\0';
        
        p.priority = priority;
        
        std::vector<char> buffer(sizeof(TaskPayload));
        std::memcpy(buffer.data(), &p, sizeof(TaskPayload));
        return buffer;
    }

    // Reconstructs the C++ struct from raw bytes
    static TaskPayload deserialize(const std::vector<char>& buffer) {
        TaskPayload p;
        std::memcpy(&p, buffer.data(), sizeof(TaskPayload));
        return p;
    }
};