import queue as queuemodule
import time
import re


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
