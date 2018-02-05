import time
import argparse
from multiprocessing import Queue
import queue as queuemodule
import threading
from typing import List

from kubernetes import config
from kubernetes.client import Configuration
from kubernetes.client.apis import core_v1_api

import urwid
import urwid.raw_display

from monitor import Monitor, MonitorRunner


def close_monitors(close_queue: Queue, monitors: List[Monitor]):
    print('closing')
    close_queue.put('close')
    for m in monitors:
        m.process.join()


def ui(runner: MonitorRunner):
    monitor_columns = {m.pod_name: (urwid.Text(m.output), m)
                       for m in runner.monitors}

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
        for m in runner.monitors:
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

    def wait_for_values(monitor_columns, queue, close_queue):
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
                                     args=(monitor_columns,
                                           runner.data_queue,
                                           runner.close_queue))
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

    try:
        config.load_kube_config()
    except FileNotFoundError:
        config.load_incluster_config()

    c = Configuration()
    c.assert_hostname = False
    Configuration.set_default(c)
    api = core_v1_api.CoreV1Api()
    runner = MonitorRunner('kube-system', api, q, close_queue)

    runner.run(args.verbose, args.selector,
               args.pod, args.endpoint)

    ui(runner)
    close_monitors(close_queue, runner.monitors)


if __name__ == '__main__':
    main()
