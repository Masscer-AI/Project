import time
import psutil

class ResourceMonitor:
    def __init__(self):
        self.start_time = time.perf_counter()
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss

    def end(self):
        end_time = time.perf_counter()
        final_memory = self.process.memory_info().rss
        return {
            "time": end_time - self.start_time,
            "memory": final_memory - self.initial_memory
        }

# Usage
monitor = ResourceMonitor()
# ... your code to monitor ...
result = monitor.end()
print(result)  # Outputs: {'time': ..., 'memory': ...}
