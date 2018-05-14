import time
import sys
from multiprocessing import Queue
import queue as queuemodule
import typing.io

from microscope.monitor.runner import MonitorRunner


def batch(runner: MonitorRunner, timeout: int):
    start_time = time.time()
    while(runner.is_alive() and runner.close_queue.empty()
          and (start_time + timeout > time.time() or timeout == 0)):
        drain_and_print(runner.data_queue, sys.stdout)

    # drain queue
    drain_and_print(runner.data_queue, sys.stdout)


def drain_and_print(queue: Queue, stream: typing.io):
    while True:
        try:
            output = queue.get(True, 1)
            if ("output" in output):
                print(f"\n{output['node_name']}: {output['output']}",
                      end="", file=stream)
                stream.flush()
        except queuemodule.Empty:
            break
