import time
import signal
import argparse
import sys
from multiprocessing import Process, Queue
import queue as queuemodule
import threading
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
        self.close_queue = close_queue
        self.api = api
        self.endpoint = endpoint
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

    m.close_queue.cancel_join_thread()
    m.queue.cancel_join_thread()


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
    except ApiException as e:
        print('could not list Cilium pods: %s\n' % e)
        sys.exit(1)

    names = [pod.metadata.name for pod in pods.items]

    monitors = [
        Monitor(name, namespace, queue, close_queue, api, endpoint, verbose)
        for name in names]

    for m in monitors:
        m.process.start()

    return monitors


def close_monitors(close_queue: Queue, monitors: List[Monitor]):
    print('closing')
    close_queue.put('close')
    for m in monitors:
        m.process.join()


def ui(monitors):
    monitor_columns = {m.pod_name: (urwid.Text(m.output), m)
                       for m in monitors}

    text_header = (u"Cilium Monitor Sink."
                   u"UP / DOWN / PAGE UP / PAGE DOWN scroll.  F8 exits.")

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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', type=int, help='endpoint id', default=0)
    parser.add_argument('--verbose', type=bool, default=False)
    args = parser.parse_args()

    q = Queue()
    close_queue = Queue()
    monitors = run_monitors(args.endpoint, args.verbose, q, close_queue)

    ui(monitors)
    close_monitors(close_queue, monitors)
