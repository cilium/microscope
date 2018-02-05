import time
import json
import signal
import argparse
import sys
from multiprocessing import Process, Queue
import queue as queuemodule
import threading
from typing import List, Set

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
                 endpoints: Set[int],
                 verbose: bool):
        self.pod_name = pod_name
        self.namespace = namespace
        self.queue = queue
        self.close_queue = close_queue
        self.api = api
        self.endpoints = endpoints
        self.verbose = verbose
        self.process = Process(target=connect_monitor, args=(self,))
        self.output = pod_name + "\n"
        self.output_lock = threading.Semaphore()


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

    if m.endpoints:
        for e in m.endpoints:
            exec_command.append('--related-to')
            exec_command.append(str(e))

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

    m.close_queue.cancel_join_thread()
    m.queue.cancel_join_thread()


def run_monitors(verbose: bool, selectors: List[str],
                 pod_names: List[str], endpoints: List[int], queue: Queue,
                 close_queue: Queue) -> List[Monitor]:

    try:
        config.load_kube_config()
    except FileNotFoundError:
        config.load_incluster_config()

    c = Configuration()
    c.assert_hostname = False
    Configuration.set_default(c)
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

    ids = retrieve_endpoint_ids(api, selectors, pod_names, names)
    ids.update(endpoints)

    print(ids)

    monitors = [
        Monitor(name, namespace, queue, close_queue, api, ids, verbose)
        for name in names]

    for m in monitors:
        m.process.start()

    return monitors


def close_monitors(close_queue: Queue, monitors: List[Monitor]):
    print('closing')
    close_queue.put('close')
    for m in monitors:
        m.process.join()


def retrieve_endpoint_ids(api: core_v1_api.CoreV1Api, selectors: List[str],
                          pod_names: List[str], node_names: List[str]
                          ) -> Set[int]:
    ids = set()
    for node in node_names:
        exec_command = ['cilium', 'endpoint', 'list', '-o', 'json']
        resp = stream(api.connect_get_namespaced_pod_exec, node, 'kube-system',
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
                       if any(
                           [any([selector in label for selector in selectors])
                            for label
                            in endpoint['labels']['orchestration-identity']]
                       )}
        ids.update(nameMatch, labelsMatch)

    return ids


def ui(monitors: List[Monitor]):
    monitor_columns = {m.pod_name: (urwid.Text(m.output), m)
                       for m in monitors}

    text_header = (u"Cilium Monitor Sink."
                   u"UP / DOWN / PAGE UP / PAGE DOWN scroll. F8 exits. "
                   u"s dumps nodes output to disk")

    listbox_content = [
        urwid.Columns([c[0] for c in monitor_columns.values()],
                      5, min_width=20),
    ]

    header = urwid.AttrWrap(urwid.Text(text_header), 'header')
    listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
    frame = urwid.Frame(urwid.AttrWrap(listbox, 'body'), header=header)

    palette = [
        ('body', 'black', 'light gray', 'standout'),
        ('reverse', 'light gray', 'black'),
        ('header', 'white', 'dark red', 'bold'),
        ('important', 'dark blue', 'light gray', ('standout', 'underline')),
        ('editfc', 'white', 'dark blue', 'bold'),
        ('editbx', 'light gray', 'dark blue'),
        ('editcp', 'black', 'light gray', 'standout'),
        ('bright', 'dark gray', 'light gray', ('bold', 'standout')),
        ('buttn', 'black', 'dark cyan'),
        ('buttnf', 'white', 'dark blue', 'bold'),
        ]

    screen = urwid.raw_display.Screen()

    def dump_data():
        timestamp = time.time()
        outputs = {}
        for m in monitors:
            if m.output_lock.acquire():
                outputs[m.pod_name] = m.output
                m.output_lock.release()

        for name, o in outputs.items():
            with open(name + "-" + str(timestamp), 'w') as f:
                f.write(o)

    def unhandled(key):
        if key == 'f8':
            raise urwid.ExitMainLoop()
        if key == 's':
            dump_data()

    mainloop = urwid.MainLoop(frame, palette, screen,
                              unhandled_input=unhandled)

    def wait_for_values(monitor_columns):
        m = next(iter(monitor_columns.values()))
        queue = m[1].queue
        close_queue = m[1].close_queue

        while(close_queue.empty()):
            try:
                output = queue.get(True, 5)
            except queuemodule.Empty:
                continue

            c = monitor_columns[output["name"]]
            column = c[0]
            monitor = c[1]
            if monitor.output_lock.acquire():
                monitor.output += output["output"]
                monitor.output_lock.release()
            column.set_text(monitor.output)
            mainloop.draw_screen()
    update_thread = threading.Thread(target=wait_for_values,
                                     args=(monitor_columns,))
    update_thread.start()

    mainloop.run()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', type=bool, default=False)
    parser.add_argument('--selector', action='append', default=[],
                        help='k8s equality label selectors for pods which '
                        'monitor should listen to. each selector will '
                        'retrieve its own set of pods. '
                        'Format is "label-name=label-value"')
    parser.add_argument('--pod', action='append', default=[],
                        help='pod names in form of "namespace:pod-name"')
    parser.add_argument('--endpoint', action='append', type=int, default=[],
                        help='Cilium endpoint ids')

    args = parser.parse_args()

    q = Queue()
    close_queue = Queue()
    monitors = run_monitors(args.verbose, args.selector,
                            args.pod, args.endpoint, q, close_queue)

    ui(monitors)
    close_monitors(close_queue, monitors)


if __name__ == '__main__':
    main()
