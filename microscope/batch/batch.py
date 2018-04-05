import time
import queue as queuemodule
import sys

from microscope.monitor.monitor import MonitorRunner


def batch(runner: MonitorRunner, timeout: int):
    start_time = time.time()
    while(runner.is_alive() and runner.close_queue.empty()
          and (start_time + timeout > time.time() or timeout == 0)):
        try:
            output = runner.data_queue.get(True, 1)
        except queuemodule.Empty:
            continue
        if ("output" in output):
            sys.stdout.write(output["output"])
