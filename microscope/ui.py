import time
import threading
import queue as queuemodule

import urwid
import urwid.raw_display

from .monitor import MonitorRunner


def ui(runner: MonitorRunner):
    monitor_columns = {m.pod_name: (urwid.Text(m.output), m)
                       for m in runner.monitors}

    text_header = (u"Cilium Microscope."
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
