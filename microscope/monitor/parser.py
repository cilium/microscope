import queue as queuemodule
import time
import re
import json
from typing import List, Dict


class MonitorOutputProcessorSimple:
    def __init__(self, resolver):
        self.resolver = resolver
        self.std_output = queuemodule.Queue()
        self.std_err = queuemodule.Queue()

    def add_out(self, out: str):
        for line in out.split("\n"):
            self.std_output.put(self.resolver.resolve_to_podnames(line))

    def add_err(self, err: str):
        for line in err.split("\n"):
            self.std_err.put(line)

    def get_err(self) -> str:
        err = []
        while not self.std_err.empty():
            line = self.std_err.get()
            err.append(line)
        if err:
            return "\n".join(err)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        err = self.get_err()
        if err:
            return err

        try:
            return self.std_output.get_nowait()
        except queuemodule.Empty:
            raise StopIteration

        raise StopIteration


class MonitorOutputProcessorVerbose(MonitorOutputProcessorSimple):
    def __init__(self, resolver):
        self.std_output = queuemodule.Queue()
        self.std_err = queuemodule.Queue()
        self.resolver = resolver
        self.current_msg = []
        self.last_event_wait_timeout = 1500
        self.last_event_time = 0

    def __next__(self) -> str:
        err = self.get_err()
        if err:
            return err

        prev_event = self.last_event_time
        while not self.std_output.empty():
            line = self.std_output.get()

            self.last_event_time = int(round(time.time() * 1000))

            if '---' in line:
                resolver = self.resolver
                return resolver.resolve_to_podnames(self.pop_current(line))
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
    def __init__(self, resolver):
        self.resolver = resolver
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
        err = self.get_err()
        if err:
            return err

        if not self.std_output:
            raise StopIteration

        line = self.getline()
        if not line:
            raise StopIteration

        try:
            return self.parse_l7_line(line)
        except IndexError:
            return self.resolver.resolve_to_podnames(line)

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


class MonitorOutputProcessorJSON(MonitorOutputProcessorSimple):
    def __init__(self, identities: Dict):
        self.std_output = ""
        self.std_err = queuemodule.Queue()
        self.identities = identities

    def add_out(self, out: str):
        self.std_output += out

    def get_event(self) -> str:
        stack = []
        opening = 0
        closing = 0

        for i, c in enumerate(self.std_output):
            if c == "{":
                stack.append(i)
            if c == "}":
                opening = stack.pop()
                if len(stack) == 0:
                    closing = i
                    break
        if closing > opening:
            ret = self.std_output[opening:closing+1]
            self.std_output = self.std_output[closing+1:]
            return ret
        else:
            return None

    def parse_event(self, e: str) -> str:
        event = json.loads(e, strict=False)

        if event["type"] == "logRecord":
            return self.parse_l7(event)
        if event["type"] == "trace":
            return self.parse_trace(event)

        return e

    def parse_labels(self, labels: List[str]) -> str:
        return ", ".join([l for l in labels
                          if "k8s:io.kubernetes.pod.namespace=" not in l])

    def parse_l7(self, event: Dict):
        src_labels = self.parse_labels(event["srcEpLabels"])
        dst_labels = self.parse_labels(event["dstEpLabels"])

        action = ""
        if "http" in event:
            http = event['http']
            action = f"{http['Method']} {http['URL']['Path']}"

        if "kafka" in event:
            kafka = event['kafka']
            action = f"{kafka['APIKey']} {kafka['Topic']['Topic']}"

        return (f"({src_labels}) => ({dst_labels}) {event['l7Proto']}"
                f" {action} {event['verdict']}")

    def parse_trace(self, event: Dict):
        src_labels = self.parse_labels(self.identities[event["srcLabel"]])
        dst_labels = self.parse_labels(self.identities[event["dstLabel"]])

        return f"({src_labels}) => ({dst_labels})"

    def __next__(self) -> str:
        err = self.get_err()
        if err:
            return err

        if not self.std_output:
            raise StopIteration

        event = self.get_event()
        if event is None:
            raise StopIteration

        return self.parse_event(event)
