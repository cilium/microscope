import queue as queuemodule
import time
import json
from typing import List, Dict, Tuple


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
    def __init__(self):
        self.std_output = queuemodule.Queue()
        self.std_err = queuemodule.Queue()
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
                return self.pop_current(line)
            else:
                self.current_msg.append(line)

        now = int(round(time.time() * 1000))
        if prev_event + self.last_event_wait_timeout < now:
            if self.current_msg:
                return self.pop_current()

        raise StopIteration

    def pop_current(self, init: str = "") -> str:
        tmp = "\n".join(self.current_msg)
        if init:
            self.current_msg = [init]
        else:
            self.current_msg = []
        return tmp


class MonitorOutputProcessorJSON(MonitorOutputProcessorSimple):
    def __init__(self, resolver):
        self.std_output = ""
        self.std_err = queuemodule.Queue()
        self.resolver = resolver

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
        if event["type"] == "drop":
            return self.parse_drop(event)
        if event["type"] == "debug":
            return self.parse_debug(event)
        if event["type"] == "capture":
            return self.parse_capture(event)
        if event["type"] == "agent":
            return self.parse_agent(event)

        return e

    def parse_labels(self, labels: List[str]) -> str:
        return ", ".join([l for l in labels
                          if "k8s:io.kubernetes.pod.namespace=" not in l])

    def parse_l7(self, event: Dict) -> str:
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

    def parse_trace(self, event: Dict) -> str:
        src_ep, dst_ep = self.get_eps_repr(event)

        return (f"trace ({src_ep}) =>"
                f" ({dst_ep})")

    def parse_drop(self, event: Dict) -> str:
        src_ep, dst_ep = self.get_eps_repr(event)

        return (f"drop: {event['reason']} ({src_ep}) =>"
                f" ({dst_ep})")

    def parse_debug(self, event: Dict) -> str:
        return f"debug: {event['message']} on {event['cpu']}"

    def parse_capture(self, event: Dict) -> str:
        return f"{event['prefix']}: {event['summary']}"

    def parse_agent(self, event: Dict) -> str:
        return f"{event['subtype']}: {event['message']}"

    def get_eps_repr(self, event: Dict) -> Tuple[str, str]:
        """
        get_eps_repr returns tuple with source endpoint
        and destination endpoint representation
        """
        src_repr = ""
        dst_repr = ""
        src_ip = ""
        dst_ip = ""
        src_port = ""
        dst_port = ""

        try:
            src_ip, dst_ip = self.get_ips(event)
        except (KeyError, StopIteration):
            pass
        try:
            src_ip, dst_ip = self.get_ips(event)
        except KeyError:
            pass

        try:
            src_port, dst_port = self.get_ports(event)
        except (KeyError, StopIteration):
            pass

        src_repr = self.get_ep_repr(src_ip, src_port, event.get("source"),
                                    event.get("srcLabel"))

        dst_repr = self.get_ep_repr(dst_ip, dst_port, event.get("dstID"),
                                    event.get("dstLabel"))
        return (src_repr, dst_repr)

    def get_ep_repr(self, ip, port, ep_id, identity):
        ip_l4 = ""
        repr = ""
        if ip and port:
            ip_l4 = ip + ":" + port

        if ip:
            repr = self.resolver.resolve_ip(ip)

        if not repr:
            repr = self.resolver.resolve_eid(ep_id)

        if not repr:
            labels = self.resolver.resolve_identity(identity)
            if labels is not None:
                repr = self.parse_labels(labels)
            else:
                repr = str(identity)

        if ip_l4:
            repr += f" {ip_l4}"
        elif ip:
            repr += f" {ip}"

        return repr

    def get_ips(self, event: Dict) -> Tuple[str, str]:
        return (event["summary"]["l3"]["src"], event["summary"]["l3"]["dst"])

    def get_ports(self, event: Dict) -> Tuple[str, str]:
        return (event["summary"]["l4"]["src"], event["summary"]["l4"]["dst"])

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
