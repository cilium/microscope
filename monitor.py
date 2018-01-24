import time
import signal
import argparse
import sys
from multiprocessing import Process, Queue
from typing import List

from kubernetes import config
from kubernetes.client import Configuration
from kubernetes.client.apis import core_v1_api
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
import urwid
import urwid.raw_display


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
                 endpoint: int,
                 verbose: bool):
        self.pod_name = pod_name
        self.namespace = namespace
        self.queue = queue
        self.close_queue= close_queue
        self.api = api
        self.endpoint = endpoint
        self.verbose = verbose
        self.process = Process(target=connect_monitor, args=(self,))

def connect_monitor(m: Monitor):
    try:
        resp = m.api.read_namespaced_pod(name=m.pod_name,
                                       namespace=m.namespace)
    except ApiException as e:
        if e.status != 404:
            print('Unknown error: %s' % e)
            exit(1)


# calling exec and wait for response.
    exec_command = [
        'cilium',
        'monitor']

    if m.verbose:
        exec_command.append('-v')

    if m.endpoint:
        exec_command.append('--related-to')
        exec_command.append(str(m.endpoint))

    resp = stream(m.api.connect_get_namespaced_pod_exec, m.pod_name,
                  m.namespace,
                  command=exec_command,
                  stderr=True, stdin=True,
                  stdout=True, tty=True,
                  _preload_content=False)

    signal.signal(signal.SIGINT, sigint_in_monitor)

    while resp.is_open():
        resp.update(timeout=1)
        if not m.close_queue.empty():
            print("Closing monitor")
            resp.write_stdin('\x03')
            break
        if resp.peek_stdout():
            m.queue.put({'name': m.pod_name,  'output': resp.read_stdout()})
        if resp.peek_stderr():
            m.queue.put({'name': m.pod_name,  'output': resp.read_stderr()})

    resp.close()

def run_monitors(endpoint: int, verbose: bool, queue: Queue,
                 close_queue: Queue) -> List[Monitor]:

    config.load_kube_config()
    c = Configuration()
    c.assert_hostname = False
    Configuration.set_default(c)
    api = core_v1_api.CoreV1Api()
    namespace = 'kube-system'

    try:
        pods = api.list_namespaced_pod(namespace,
                                       label_selector='k8s-app=cilium')
    except APIException as e:
        print('could not list Cilium pods: %s\n' % e)
        sys.exit(1)

    names = [pod.metadata.name for pod in pods.items]

    monitors = [Monitor(name, namespace, queue, close_queue, api, endpoint, verbose) for name in names]

    for m in monitors:
        m.process.start()

    return monitors

def close_monitors(close_queue: Queue, monitors: List[Monitor]):
    print('closing')
    close_queue.put('close')
    for m in monitors:
        m.process.join()

def wait_for_output(queue: Queue):
    while True:
        handle_output(q.get())
        time.sleep(1)

def handle_output(output):
    print(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', type=int, help='endpoint id', default=0)
    parser.add_argument('--verbose', type=bool, default=False)
    args = parser.parse_args()

    q = Queue()
    close_queue = Queue()
    monitors = run_monitors(args.endpoint, args.verbose, q, close_queue)

    try:
        wait_for_output(q)
    except KeyboardInterrupt:
        pass
    finally:
        close_monitors(close_queue, monitors)
