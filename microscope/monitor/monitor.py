from typing import List, Set, Callable, Dict
import json
import sys
import signal
import time
import threading
from multiprocessing import Process, Queue
import queue as queuemodule
import re

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
                 types: List[str],
                 namespace: str):
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
        self.namespace = namespace

    def preprocess_pod_names(self, names: List[str]) -> List[str]:
        def defaultize(name: str):
            if ':' in name:
                return name
            else:
                return f'{self.namespace}:' + name
        return [defaultize(n) for n in names]


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
                 mode: str
                 ):
        self.pod_name = pod_name
        self.node_name = node_name
        self.namespace = namespace
        self.queue = queue
        self.close_queue = close_queue
        self.api = api
        self.cmd = cmd
        self.mode = mode

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
            processor = MonitorOutputProcessorSimple()
        elif self.mode == "l7":
            processor = MonitorOutputProcessorL7()
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


class MonitorOutputProcessorSimple:
    def __init__(self):
        self.std_output = queuemodule.Queue()
        self.std_err = queuemodule.Queue()

    def add_out(self, out: str):
        for line in out.split("\n"):
            self.std_output.put(line)

    def add_err(self, err: str):
        for line in err.split("\n"):
            self.std_err.put(line)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        err = []
        while not self.std_err.empty():
            line = self.std_err.get()
            err.append(line)
        if err:
            return "\n".join(err)

        try:
            return self.std_output.get_nowait()
        except queuemodule.Empty:
            raise StopIteration

        raise StopIteration


class MonitorOutputProcessorVerbose(MonitorOutputProcessorSimple):
    def __init__(self):
        self.std_output = queuemodule.Queue()
        self.std_err = queuemodule.Queue()
        self.current_msg = []
        self.last_event_wait_timeout = 1500
        self.last_event_time = 0

    def __next__(self) -> str:
        err = []
        while not self.std_err.empty():
            line = self.std_err.get()
            err.append(line)
        if err:
            return "\n".join(err)

        prev_event = self.last_event_time
        while not self.std_output.empty():
            line = self.std_output.get()

            self.last_event_time = int(round(time.time() * 1000))

            if '---' in line:
                return self.pop_current(line)
            else:
                self.current_msg.append(line)

        now = int(round(time.time() * 1000))
        if prev_event + self.last_event_wait_timeout < now:
            if self.current_msg:
                return self.pop_current()

        raise StopIteration

    def pop_current(self, init: str="") -> str:
        tmp = "\n".join(self.current_msg)
        if init:
            self.current_msg = [init]
        else:
            self.current_msg = []
        return tmp


class MonitorOutputProcessorL7(MonitorOutputProcessorSimple):
    def __init__(self):
        self.std_output = ""
        self.std_err = queuemodule.Queue()
        self.label_regex = re.compile(r'\(\[.*?\]\)')
        self.namespace_regex = re.compile(
            r'k8s:io.kubernetes.pod.namespace=.*?(?=[ \]])')

    def add_out(self, out: str):
        self.std_output += out

    def getline(self) -> str:
        lines = self.std_output.strip().split("\n")
        if self.is_full(lines[0]):
            try:
                self.std_output = "\n".join(lines[1:])
            except IndexError:
                # only one line, clear stdoutput just in case
                self.std_output = ""
            finally:
                return lines[0]
        else:
            return ""

    def is_full(self, line: str) -> bool:
        return ("=>" in line or "Listening for events" in line
                or "Press Ctrl-C" in line)

    def __next__(self) -> str:
        err = []
        while not self.std_err.empty():
            line = self.std_err.get()
            err.append(line)
        if err:
            return "\n".join(err)

        if not self.std_output:
            raise StopIteration

        line = self.getline()
        if not line:
            raise StopIteration

        try:
            return self.parse_l7_line(line)
        except IndexError:
            return line

        raise StopIteration

    def parse_l7_line(self, line: str):
            parts = line.split(',')
            labels = [self.namespace_regex.sub("", x).replace(
                "([ ", "(["
            ).replace(
                " ])", "])")
                      for x in self.label_regex.findall(parts[0])]
            labelsString = " => ".join(labels)
            protocol = parts[0].strip().split(" ")[2]

            tmp = parts[2].strip().split(" ")
            verdict = tmp[1]
            action = " ".join(tmp[2:-2])
            return f"{labelsString} {protocol} {action} {verdict}"


class MonitorRunner:
    def __init__(self, namespace, api, endpoint_namespace):
        self.namespace = namespace
        self.api = api
        self.endpoint_namespace = endpoint_namespace
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
            names = [(pod.metadata.name, pod.spec.node_name)
                     for pod in pods.items
                     if
                     pod.metadata.name in nodes
                     or
                     pod.spec.node_name in nodes]
        else:
            names = [(pod.metadata.name, pod.spec.node_name)
                     for pod in pods.items]

        if not names:
            raise ValueError('No Cilium nodes in cluster match provided names'
                             ', or Cilium is not deployed')

        if cmd_override:
            cmd = cmd_override.split(" ")
        else:
            cmd = self.get_monitor_command(monitor_args,
                                           [name[0] for name in names])

        mode = ""

        if monitor_args.verbose:
            mode = "verbose"
        if "l7" in monitor_args.types:
            mode = "l7"

        self.monitors = [
            Monitor(name[0], name[1], self.namespace, self.data_queue,
                    self.close_queue, api, cmd, mode)
            for name in names]

        for m in self.monitors:
            m.process.start()

    def get_monitor_command(self, args: MonitorArgs, names: List[str]
                            ) -> List[str]:
        endpoint_data = self.retrieve_endpoint_data(names)

        related_ids = self.retrieve_endpoint_ids(endpoint_data,
                                                 args.related_selectors,
                                                 args.related_pods,
                                                 self.endpoint_namespace)
        if (args.related_selectors or args.related_pods) and not related_ids:
            raise NoEndpointException("No related endpoints found")

        related_ids.update(args.related_endpoints)

        to_ids = self.retrieve_endpoint_ids(endpoint_data,
                                            args.to_selectors,
                                            args.to_pods,
                                            self.endpoint_namespace)
        if (args.to_selectors or args.to_pods) and not to_ids:
            raise NoEndpointException("No to endpoints found")

        to_ids.update(args.to_endpoints)

        from_ids = self.retrieve_endpoint_ids(endpoint_data,
                                              args.from_selectors,
                                              args.from_pods,
                                              self.endpoint_namespace)
        if (args.from_selectors or args.from_pods) and not from_ids:
            raise NoEndpointException("No from endpoints found")

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
                              pod_names: List[str],
                              namespace: str) -> Set[int]:
        ids = set()
        namespace_matcher = f"k8s:io.kubernetes.pod.namespace={namespace}"

        for data in endpoint_data:
            try:
                namesMatch = {
                    endpoint['id'] for endpoint in data
                    if
                    endpoint['status']['external-identifiers']['pod-name']
                    in pod_names
                }
            except (KeyError, TypeError):
                # fall back to older API structure
                namesMatch = {endpoint['id'] for endpoint in data
                              if endpoint['pod-name'] in pod_names}

            def labels_match(endpoint_data, selectors: List[str],
                             labels_getter: Callable[[Dict], List[str]]):
                return {
                    endpoint['id'] for endpoint in data
                    if any([
                        any(
                            [selector in label
                             for selector in selectors])
                        for label
                        in labels_getter(endpoint)
                    ]) and namespace_matcher in labels_getter(endpoint)
                }

            getters = [
                    lambda x: x['status']['labels']['security-relevant'],
                    lambda x: x['labels']['orchestration-identity'],
                    lambda x: x['labels']['security-relevant']
            ]
            labelsMatch = []
            for getter in getters:
                try:
                    labelsMatch = labels_match(
                      endpoint_data, selectors, getter)
                except (KeyError, TypeError):
                    continue
                break

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
        print('\nclosing')
        self.close_queue.put('close')
        for m in self.monitors:
            m.process.join()

    def is_alive(self):
        return any([m.process.is_alive() for m in self.monitors])


class NoEndpointException(Exception):
    pass
