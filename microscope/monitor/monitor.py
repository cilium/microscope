from typing import List, Set
import json
import sys
import signal
import threading
from multiprocessing import Process, Queue
import queue as queuemodule

from kubernetes.client.apis import core_v1_api
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream


class MonitorArgs:
    def __init__(self,
                 verbose: bool,
                 hex: bool,
                 related_selectors: List[str],
                 related_pods: List[str],
                 related_endpoints: List[int],
                 to_selectors: List[str],
                 to_pods: List[str],
                 to_endpoints: List[int],
                 from_selectors: List[str],
                 from_pods: List[str],
                 from_endpoints: List[int],
                 types: List[str]):
        self.verbose = verbose
        self.hex = hex
        self.related_selectors = related_selectors
        self.related_pods = self.preprocess_pod_names(related_pods)
        self.related_endpoints = related_endpoints
        self.to_selectors = to_selectors
        self.to_pods = self.preprocess_pod_names(to_pods)
        self.to_endpoints = to_endpoints
        self.from_selectors = from_selectors
        self.from_pods = self.preprocess_pod_names(from_pods)
        self.from_endpoints = from_endpoints
        self.types = types

    def preprocess_pod_names(self, names: List[str]) -> List[str]:
        def defaultize(name: str):
            if ':' in name:
                return name
            else:
                return 'default:' + name
        return [defaultize(n) for n in names]


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
                 cmd: List[str],
                 ):
        self.pod_name = pod_name
        self.namespace = namespace
        self.queue = queue
        self.close_queue = close_queue
        self.api = api
        self.cmd = cmd

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

        resp = stream(self.api.connect_get_namespaced_pod_exec, self.pod_name,
                      self.namespace,
                      command=["bash", "-c", " ".join(self.cmd)],
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

    def run(self, monitor_args: MonitorArgs, nodes: List[str],
            cmd_override: str):

        api = core_v1_api.CoreV1Api()

        try:
            pods = api.list_namespaced_pod(self.namespace,
                                           label_selector='k8s-app=cilium')
        except ApiException as e:
            print('could not list Cilium pods: %s\n' % e)
            sys.exit(1)

        if nodes:
            names = [pod.metadata.name for pod in pods.items
                     if pod.metadata.name in nodes]
        else:
            names = [pod.metadata.name for pod in pods.items]

        if not names:
            raise ValueError('No Cilium nodes in cluster match provided names'
                             ', or Cilium is not deployed')

        if cmd_override:
            cmd = cmd_override.split(" ")
        else:
            cmd = self.get_monitor_command(monitor_args, names)

        self.monitors = [
            Monitor(name, self.namespace, self.data_queue, self.close_queue,
                    api, cmd)
            for name in names]

        for m in self.monitors:
            m.process.start()

    def get_monitor_command(self, args: MonitorArgs, names: List[str]
                            ) -> List[str]:
        endpoint_data = self.retrieve_endpoint_data(names)

        related_ids = self.retrieve_endpoint_ids(endpoint_data,
                                                 args.related_selectors,
                                                 args.related_pods)
        related_ids.update(args.related_endpoints)

        to_ids = self.retrieve_endpoint_ids(endpoint_data,
                                            args.to_selectors,
                                            args.to_pods)
        to_ids.update(args.to_endpoints)

        from_ids = self.retrieve_endpoint_ids(endpoint_data,
                                              args.from_selectors,
                                              args.from_pods)
        from_ids.update(args.from_endpoints)

        exec_command = [
            'cilium',
            'monitor']

        if args.verbose:
            exec_command.append('-v')

        if args.hex:
            if '-v' not in exec_command:
                exec_command.append('-v')
            exec_command.append('--hex')

        if related_ids:
            for e in related_ids:
                exec_command.append('--related-to')
                exec_command.append(str(e))

        if to_ids:
            for e in to_ids:
                exec_command.append('--to')
                exec_command.append(str(e))

        if from_ids:
            for e in from_ids:
                exec_command.append('--from')
                exec_command.append(str(e))

        if args.types:
            for t in args.types:
                exec_command.append('--type')
                exec_command.append(t)

        print(exec_command)
        return exec_command

    def retrieve_endpoint_data(self, node_names: List[str]) -> Set[int]:
        getters = [Process(target=self.get_node_endpoint_data,
                           args=(node,))
                   for node in node_names]

        for p in getters:
            p.start()

        try:
            outputs = [self.data_queue.get(timeout=10) for _ in getters]
        except queuemodule.Empty as e:
            for p in getters:
                p.terminate()
            raise e

        for p in getters:
            p.join()

        return outputs

    def retrieve_endpoint_ids(self, endpoint_data, selectors: List[str],
                              pod_names: List[str]) -> Set[int]:
        ids = set()

        for data in endpoint_data:
            namesMatch = {endpoint['id'] for endpoint in data
                          if endpoint['pod-name'] in pod_names}

            labelsMatch = {endpoint['id'] for endpoint in data
                           if any([
                               any(
                                   [selector in label
                                    for selector in selectors])
                               for label
                               in endpoint['labels']['orchestration-identity']
                           ])}
            ids.update(namesMatch, labelsMatch)

        return ids

    def get_node_endpoint_data(self, node: str):
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

        self.data_queue.put(data)

    def finish(self):
        print('closing')
        self.close_queue.put('close')
        for m in self.monitors:
            m.process.join()
