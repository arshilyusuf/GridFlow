# File: frontend/gridflow.py
import gridflow_cpp  

class GridFlowPipeline:
    def __init__(self, num_threads=8):
        self.num_threads = num_threads
        self.tasks = {}
        self.task_counter = 0
        self.root_tasks = [] # NEW: Track the entry points of the graph

    def task(self, depends_on=None):
        if depends_on is None:
            depends_on = []

        def decorator(func):
            # 1. Create the C++ Task 
            cpp_task = gridflow_cpp.PythonTask(self.task_counter, func)
            self.tasks[func.__name__] = cpp_task
            self.task_counter += 1

            # NEW: If it has no dependencies, it is a Root Node
            if not depends_on:
                self.root_tasks.append(cpp_task)

            # 2. Wire up the C++ graph dependencies
            for dependency_func in depends_on:
                parent_task = self.tasks[dependency_func.__name__]
                parent_task.add_dependent(cpp_task)

            return func
        return decorator

    def execute(self):
        print("=> Handing pipeline over to C++ Compiler...")
        raw_tasks = list(self.tasks.values())
        
        # The C++ compiler still analyzes everything for cycles and critical paths
        execution_order = gridflow_cpp.DAGCompiler.compile(raw_tasks)
        print(f"=> C++ Compilation successful. Firing up {self.num_threads} cores.")

        engine = gridflow_cpp.Scheduler(self.num_threads)
        
        # THE FIX: Only push the Root Nodes into the starting queue!
        # The C++ worker loop will automatically queue up dependents as it works.
        for t in self.root_tasks:
            engine.push_task(t, 0)

        # Unleash the threads 
        engine.run_workers(self.num_threads)
        print("=> C++ Engine execution complete.")