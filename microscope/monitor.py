from typing import Set, List
import json
import sys
import signal
import threading
from multiprocessing import Process, Queue

from kubernetes.client.apis import core_v1_api
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream


# we are ignoring sigint in monitor processes as they are closed via queue
def sigint_in_monitor(signum, frame):
    pass


class Monitor:
    def __init__(self,
                 pod_name: str,
                 namespace: str,
                 queue: Queue,
                 close_queue: Queue,
                 api: core_v1_api.CoreV1Api,
                 endpoints: Set[int],
                 verbose: bool):
        self.pod_name = pod_name
        self.namespace = namespace
        self.queue = queue
        self.close_queue = close_queue
        self.api = api
        self.endpoints = endpoints
        self.verbose = verbose
        self.process = Process(target=self.connect)
        self.output = pod_name + "\n"
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
        exec_command = [
            'cilium',
            'monitor']

        if self.verbose:
            exec_command.append('-v')

        if self.endpoints:
            for e in self.endpoints:
                exec_command.append('--related-to')
                exec_command.append(str(e))

        resp = stream(self.api.connect_get_namespaced_pod_exec, self.pod_name,
                      self.namespace,
                      command=exec_command,
                      stderr=True, stdin=True,
                      stdout=True, tty=True,
                      _preload_content=False)

        signal.signal(signal.SIGINT, sigint_in_monitor)

        while resp.is_open():
            resp.update(timeout=1)
            if not self.close_queue.empty():
                print("Closing monitor")
                resp.write_stdin('\x03')
                break
            if resp.peek_stdout():
                self.queue.put({
                    'name': self.pod_name,
                    'output': resp.read_stdout()})
            if resp.peek_stderr():
                self.queue.put({
                    'name': self.pod_name,
                    'output': resp.read_stderr()})

        resp.close()

        self.close_queue.cancel_join_thread()
        self.queue.cancel_join_thread()


class MonitorRunner:
    def __init__(self, namespace, api):
        self.namespace = namespace
        self.api = api
        self.monitors = []
        self.data_queue = Queue()
        self.close_queue = Queue()

    def run(self, verbose: bool, selectors: List[str],
            pod_names: List[str], endpoints: List[int]):

        # TODO: move these two to new Monitors class
        api = core_v1_api.CoreV1Api()
        namespace = 'kube-system'

        try:
            pods = api.list_namespaced_pod(namespace,
                                           label_selector='k8s-app=cilium')
        except ApiException as e:
            print('could not list Cilium pods: %s\n' % e)
            sys.exit(1)

        names = [pod.metadata.name for pod in pods.items]

        ids = self.retrieve_endpoint_ids(selectors, pod_names, names)
        ids.update(endpoints)

        self.monitors = [
            Monitor(name, namespace, self.data_queue, self.close_queue, api,
                    ids, verbose)
            for name in names]

        for m in self.monitors:
            m.process.start()

    def retrieve_endpoint_ids(self, selectors: List[str],
                              pod_names: List[str],
                              node_names: List[str]
                              ) -> Set[int]:
        ids = set()
        for node in node_names:
            exec_command = ['cilium', 'endpoint', 'list', '-o', 'json']
            resp = stream(self.api.connect_get_namespaced_pod_exec, node,
                          self.namespace,
                          command=exec_command,
                          stderr=False, stdin=False,
                          stdout=True, tty=False, _preload_content=False,
                          _return_http_data_only=True)
            output = ""

            # _preload_content causes json to be malformed,
            # so we need to load raw data from websocket
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    output += resp.read_stdout()
                try:
                    data = json.loads(output)
                    resp.close()
                except ValueError:
                    continue

            nameMatch = {endpoint['id'] for endpoint in data
                         if endpoint['pod-name'] in pod_names}

            labelsMatch = {endpoint['id'] for endpoint in data
                           if any([
                               any(
                                   [selector in label
                                    for selector in selectors])
                               for label
                               in endpoint['labels']['orchestration-identity']
                           ])}
            ids.update(nameMatch, labelsMatch)

        return ids

    def finish(self):
        print('closing')
        self.close_queue.put('close')
        for m in self.monitors:
            m.process.join()
