# File: frontend/gridflow.py
import gridflow_cpp


class GridFlowPipeline:
    def __init__(self, num_threads=8):
        self.num_threads = num_threads
        self.tasks = {}
        self.task_counter = 0
        self.root_tasks = []
        self.scheduler = gridflow_cpp.Scheduler(num_threads)

    def get_scheduler(self):
        return self.scheduler

    def task(self, depends_on=None):
        if depends_on is None:
            depends_on = []

        def decorator(func):
            cpp_task = gridflow_cpp.PythonTask(self.task_counter, func)
            self.tasks[func.__name__] = cpp_task
            self.task_counter += 1

            if not depends_on:
                self.root_tasks.append(cpp_task)

            for dependency_func in depends_on:
                parent_task = self.tasks[dependency_func.__name__]
                parent_task.add_dependent(cpp_task)

            return func

        return decorator

    def execute(self):
        print("=> Handing pipeline over to C++ Compiler...")
        raw_tasks = list(self.tasks.values())

        # Compile returns the post-fusion execution order (may be shorter than raw_tasks)
        execution_order = gridflow_cpp.DAGCompiler.compile(raw_tasks)
        actual_count = len(raw_tasks)  # scheduler counts original tasks, not fused ones
        print(f"=> C++ Compilation successful. Firing up {self.num_threads} cores.")

        for t in self.root_tasks:
            self.scheduler.push_task(t, 0)

        # Pass the real task count so run_workers knows when to stop
        self.scheduler.run_workers(self.num_threads, actual_count)
        print("=> C++ Engine execution complete.")
