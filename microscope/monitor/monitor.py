from typing import List
import signal
import threading
from multiprocessing import Process, Queue

from kubernetes.client.apis import core_v1_api
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream

from microscope.monitor.parser import MonitorOutputProcessorVerbose
from microscope.monitor.parser import MonitorOutputProcessorJSON
from microscope.monitor.parser import MonitorOutputProcessorSimple


# we are ignoring sigint in monitor processes as they are closed via queue
def sigint_in_monitor(signum, frame):
    pass


class Monitor:
    def __init__(self,
                 pod_name: str,
                 node_name: str,
                 namespace: str,
                 queue: Queue,
                 close_queue: Queue,
                 api: core_v1_api.CoreV1Api,
                 cmd: List[str],
                 mode: str,
                 resolver
                 ):
        self.pod_name = pod_name
        self.node_name = node_name
        self.namespace = namespace
        self.queue = queue
        self.close_queue = close_queue
        self.api = api
        self.cmd = cmd
        self.mode = mode
        self.resolver = resolver

        self.process = Process(target=self.connect)
        self.output = node_name + "\n"
        self.output_lock = threading.Semaphore()

    def connect(self):
        try:
            resp = self.api.read_namespaced_pod(name=self.pod_name,
                                                namespace=self.namespace)
        except ApiException as e:
            if e.status != 404:
                print('Unknown error: %s' % e)
                exit(1)

        # calling exec and wait for response.

        resp = stream(self.api.connect_get_namespaced_pod_exec, self.pod_name,
                      self.namespace,
                      command=["bash", "-c", " ".join(self.cmd)],
                      stderr=True, stdin=True,
                      stdout=True, tty=True,
                      _preload_content=False)

        signal.signal(signal.SIGINT, sigint_in_monitor)

        if self.mode == "":
            processor = MonitorOutputProcessorJSON(self.resolver)
        elif self.mode == "raw":
            processor = MonitorOutputProcessorSimple()
        else:
            processor = MonitorOutputProcessorVerbose()

        while resp.is_open():
            for msg in processor:
                if msg:
                    self.queue.put({
                        'name': self.pod_name,
                        'node_name': self.node_name,
                        'output': msg})

            resp.update(timeout=1)
            if not self.close_queue.empty():
                print("Closing monitor")
                resp.write_stdin('\x03')
                break
            if resp.peek_stdout():
                processor.add_out(resp.read_stdout())
            if resp.peek_stderr():
                processor.add_err(resp.read_stderr())

        for msg in processor:
            if msg:
                self.queue.put({
                    'name': self.pod_name,
                    'node_name': self.node_name,
                    'output': msg})

        resp.close()

        self.close_queue.cancel_join_thread()
        self.queue.close()
        self.queue.join_thread()
