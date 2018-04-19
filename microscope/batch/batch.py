import time
import sys

import queue as queuemodule

from microscope.monitor.monitor import MonitorRunner


def batch(runner: MonitorRunner, timeout: int):
    start_time = time.time()
    while(runner.is_alive() and runner.close_queue.empty()
          and (start_time + timeout > time.time() or timeout == 0)):
        while True:
            try:
                output = runner.data_queue.get(True, 1)
                if ("output" in output):
                    print(f"\n{output['node_name']}: {output['output']}",
                          end="")
            except queuemodule.Empty:
                break

    # drain queue
    while True:
        try:
            output = runner.data_queue.get(True, 1)
            if ("output" in output):
                print(f"\n{output['node_name']}: {output['output']}",
                      end="")
        except queuemodule.Empty:
            break
    sys.stdout.flush()
