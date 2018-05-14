from typing import List, Set, Callable, Dict
import json
import sys
from multiprocessing import Queue

from kubernetes import client
from kubernetes.client.apis import core_v1_api
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream

from microscope.monitor.monitor import Monitor


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
        crds = client.CustomObjectsApi()
        cep_resp = crds.list_cluster_custom_object("cilium.io", "v2",
                                                   "ciliumendpoints")
        ceps = [cep['status'] for cep in cep_resp['items']]

        # an array to match the older per-agent command return
        return [ceps]

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
