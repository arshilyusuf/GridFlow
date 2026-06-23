// File: network/tcp_worker.cpp
#include <iostream>
#include <vector>
#include <thread>
#include <future>
#include <memory>
#include <winsock2.h>
#include "../core/scheduler.h"
#include "../core/task.h"
#include "serializer.h"

#pragma comment(lib, "ws2_32.lib")

constexpr int PORT = 8080;

void process_network_payload(const std::vector<char>& buffer, Scheduler& engine, SOCKET client_socket) {
    // 1. Deserialize the raw bytes back into a known structure
    TaskPayload payload = Serializer::deserialize(buffer);
    std::cout << "[Worker Node] Received binary payload: " << payload.name 
              << " (ID: " << payload.id << ", Priority: " << payload.priority << ")\n";
    
    // 2. Setup cross-thread synchronization
    auto task_promise = std::make_shared<std::promise<void>>();
    std::future<void> task_future = task_promise->get_future();

    // 3. Create the executable Task
    Task* net_task = new Task(payload.id, [payload, task_promise]() {
        std::cout << " -> [Engine Core] Executing remote task: " << payload.name << "\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(500)); 
        
        // Signal background completion
        task_promise->set_value(); 
    });
    net_task->priority = payload.priority;

    // 4. Dispatch to the 8-core engine and block the network thread
    engine.get_deque(0)->push(net_task);
    task_future.wait(); 

    // 5. Send binary ACK
    std::string ack = "ACK_OK";
    send(client_socket, ack.c_str(), ack.length(), 0);
}

int main() {
    std::cout << "==========================================\n";
    std::cout << "   GRIDFLOW WORKER NODE (BINARY MODE)     \n";
    std::cout << "==========================================\n";

    WSADATA wsaData;
    WSAStartup(MAKEWORD(2, 2), &wsaData);

    Scheduler engine(8);
    std::thread engine_thread([&engine]() { engine.worker_loop(0, 8); });
    std::cout << "[System] 8-Core Local Engine Online.\n";

    SOCKET server_fd = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in address;
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(PORT);

    bind(server_fd, (struct sockaddr*)&address, sizeof(address));
    listen(server_fd,SOMAXCONN);
    std::cout << "[Network] Listening for binary tasks on TCP Port " << PORT << "...\n\n";

    while (true) {
        SOCKET client_socket = accept(server_fd, nullptr, nullptr);
        if (client_socket == INVALID_SOCKET) continue;

        std::vector<char> buffer(sizeof(TaskPayload));
        int bytes_read = recv(client_socket, buffer.data(), buffer.size(), 0);
        
        if (bytes_read == sizeof(TaskPayload)) {
            process_network_payload(buffer, engine, client_socket);
        } else {
            std::cerr << "[Network] Error: Malformed packet received.\n";
        }
        closesocket(client_socket);
    }

    engine.stop();
    engine_thread.join();
    closesocket(server_fd);
    WSACleanup();
    return 0;
}