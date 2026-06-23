# File: network_master.py
import socket
import time

class NetworkDispatcher:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = target_port

    def dispatch_task(self, task_name):
        print(f"[Master] Serializing and transmitting '{task_name}' via TCP...")
        
        try:
            # Open a raw TCP socket to the C++ node
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.target_ip, self.target_port))
                s.sendall(task_name.encode('utf-8'))
                
                # Wait for the C++ engine to finish and reply
                data = s.recv(1024)
                print(f"   <- [Master] Received reply from C++: {data.decode('utf-8')}")
        except ConnectionRefusedError:
            print(f"[Master] ERROR: Could not connect to Worker Node at {self.target_ip}:{self.target_port}. Is it running?")

if __name__ == "__main__":
    print("===========================================")
    print("   GRIDFLOW NETWORK DISPATCHER (PYTHON)    ")
    print("===========================================\n")

    # In a real cluster, this IP would be a different computer (e.g., 192.168.1.50)
    # Since we are testing on one machine, we use localhost (127.0.0.1)
    cluster = NetworkDispatcher("127.0.0.1", 8080)

    # Simulate our DAG execution order being sent across the network
    tasks = [
        "Load_10GB_Dataset",
        "Normalize_Arrays",
        "Boot_Neural_Net",
        "Backpropagate_Loss"
    ]

    for task in tasks:
        cluster.dispatch_task(task)
        time.sleep(0.2) # Artificial delay to watch the network traffic