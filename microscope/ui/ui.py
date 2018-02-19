import time
import threading
from typing import Dict
import queue as queuemodule

import urwid
import urwid.raw_display

from microscope.monitor.monitor import MonitorRunner, Monitor


class MonitorColumn:
    def __init__(self, monitor: Monitor):
        self.monitor = monitor
        self.widget = urwid.Text(monitor.output)
        self.last_updated = time.time()

    def set_text(self, text):
        self.widget.set_text(text)
        self.last_updated = time.time()


def remove_stale_columns(content: urwid.MonitoredList,
                         columns: Dict, timeout: int):
    if len(columns) == 1:
        return
    now = time.time()
    to_remove = []
    for k, c in columns.items():
        if now - c.last_updated > timeout:
            content.remove((c.widget, ('weight', 1, False)))
            to_remove.append(k)

    for key in to_remove:
        del columns[k]


def ui(runner: MonitorRunner, empty_column_timeout: int):
    monitor_columns = {m.pod_name: MonitorColumn(m)
                       for m in runner.monitors}

    text_header = (u"Cilium Microscope."
                   u"UP / DOWN / PAGE UP / PAGE DOWN scroll. F8 exits. "
                   u"s dumps nodes output to disk")

    listbox_content = [
        urwid.Columns([c.widget for c in monitor_columns.values()],
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
        elif key == 's':
            dump_data()
        else:
            runner.data_queue.put({})

    mainloop = urwid.MainLoop(frame, palette, screen,
                              unhandled_input=unhandled)

    def wait_for_values(monitor_columns, queue, close_queue):
        while(close_queue.empty()):
            try:
                output = queue.get(True, 1)
            except queuemodule.Empty:
                continue

            if ("name" in output and "output" in output
                    and output["name"] in monitor_columns):
                c = monitor_columns[output["name"]]
                if c.monitor.output_lock.acquire():
                    c.monitor.output += output["output"]
                    c.set_text(c.monitor.output)
                    c.monitor.output_lock.release()

            remove_stale_columns(listbox_content[0].contents,
                                 monitor_columns, empty_column_timeout)
            try:
                mainloop.draw_screen()
            except AssertionError as e:
                # this error is encountered when program is closing
                # returning so it doesn't clutter the output
                return

    update_thread = threading.Thread(target=wait_for_values,
                                     args=(monitor_columns,
                                           runner.data_queue,
                                           runner.close_queue))
    update_thread.start()

    mainloop.run()