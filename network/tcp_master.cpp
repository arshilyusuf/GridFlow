// File: network/tcp_master.cpp
#include <iostream>
#include <vector>
#include <string>
#include <winsock2.h>
#include <ws2tcpip.h>
#include "serializer.h"
#include "registry.h"

#pragma comment(lib, "ws2_32.lib")

class MasterDispatcher {
    NodeRegistry registry;

public:
    MasterDispatcher() {
        WSADATA wsaData;
        WSAStartup(MAKEWORD(2, 2), &wsaData);
    }

    ~MasterDispatcher() {
        WSACleanup();
    }

    void add_worker(const std::string& ip, int port) {
        registry.register_worker(ip, port);
    }

    void dispatch_task(int id, const std::string& name, int priority) {
        std::vector<WorkerNode> healthy_nodes = registry.get_healthy_workers();
        if (healthy_nodes.empty()) {
            std::cerr << "[Master] SYSTEM HALT: No healthy workers available.\n";
            return;
        }

        // Round-robin or basic load balancing could be implemented here. 
        // For now, route to the first healthy node.
        WorkerNode target = healthy_nodes[0];

        std::cout << "[Master] Serializing task '" << name << "' -> Routing to " << target.ip << ":" << target.port << "...\n";

        SOCKET sock = socket(AF_INET, SOCK_STREAM, 0);
        sockaddr_in server_addr;
        server_addr.sin_family = AF_INET;
        server_addr.sin_port = htons(target.port);
        inet_pton(AF_INET, target.ip.c_str(), &server_addr.sin_addr);

        if (connect(sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) == SOCKET_ERROR) {
            std::cerr << "[Master] ERROR: Connection refused. Worker node down.\n";
            registry.mark_dead(target.ip, target.port);
            closesocket(sock);
            return;
        }

        // Serialize and Transmit
        std::vector<char> buffer = Serializer::serialize(id, name, priority);
        send(sock, buffer.data(), buffer.size(), 0);

        // Wait for worker ACK
        char ack_buffer[128] = {0};
        recv(sock, ack_buffer, sizeof(ack_buffer), 0);
        std::cout << "   <- [Worker Reply]: " << ack_buffer << "\n";

        closesocket(sock);
    }
};

int main() {
    std::cout << "==========================================\n";
    std::cout << "   GRIDFLOW CLUSTER DISPATCHER (C++)      \n";
    std::cout << "==========================================\n\n";

    MasterDispatcher master;
    
    // Register local testing node
    master.add_worker("127.0.0.1", 8080);

    // Simulated compiled DAG tasks
    master.dispatch_task(1, "Load_10GB_Dataset", 4);
    master.dispatch_task(2, "Normalize_Arrays", 3);
    master.dispatch_task(3, "Boot_Neural_Net", 3);
    master.dispatch_task(4, "Backpropagate_Loss", 1);

    return 0;
}