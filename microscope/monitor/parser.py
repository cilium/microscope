import queue as queuemodule
import time
import json
from typing import List, Dict, Tuple


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


class MonitorOutputProcessorJSON(MonitorOutputProcessorSimple):
    def __init__(self, identities: Dict, endpoints: Dict):
        self.std_output = ""
        self.std_err = queuemodule.Queue()
        self.identities = identities
        self.endpoints = endpoints

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
        src_ip_l4 = ""
        dst_ip_l4 = ""

        try:
            src_ip, dst_ip = self.get_ips4(event)
        except (KeyError, StopIteration):
            pass
        try:
            src_ip, dst_ip = self.get_ips6(event)
        except KeyError:
            pass

        try:
            src_port, dst_port = self.get_ports(event)
        except (KeyError, StopIteration):
            pass

        if src_port and src_ip:
            src_ip_l4 = src_ip + ":" + src_port

        if dst_port and dst_ip:
            dst_ip_l4 = dst_ip + ":" + dst_port

        try:
            if src_ip:
                src_ep = self.get_ep_by_ip(src_ip)
                src_repr = (
                    f"{src_ep['namespace']}:{src_ep['name']}"
                    f" {src_ip_l4 if src_ip_l4 else src_ip}"
                )
        except (KeyError, StopIteration):
            pass

        try:
            if not src_repr:
                src_ep = self.endpoints[event["source"]]
                src_repr = (
                    f"{src_ep['namespace']}:{src_ep['name']}"
                    f" {src_ip_l4 if src_ip_l4 else src_ip}"
                )
        except KeyError:
            pass
        try:
            if not src_repr:
                src_repr = self.parse_labels(
                    self.identities[event["srcLabel"]])
        except KeyError:
            if not src_repr:
                src_repr = str(event["source"])

        try:
            if dst_ip:
                dst_ep = self.get_ep_by_ip(dst_ip)
                dst_repr = (
                    f"{dst_ep['namespace']}:{dst_ep['name']}"
                    f" {dst_ip_l4 if dst_ip_l4 else dst_ip}"
                )
        except (KeyError, StopIteration):
            pass

        try:
            if not dst_repr:
                dst_ep = self.endpoints[event["dstID"]]
                dst_repr = (
                    f"{dst_ep['namespace']}:{dst_ep['name']}"
                    f" {dst_ip_l4 if dst_ip_l4 else dst_ip}"
                )
        except KeyError:
            pass
        try:
            if not dst_repr:
                dst_repr = self.parse_labels(
                    self.identities[event["dstLabel"]])
        except KeyError:
            if not dst_repr:
                dst_repr = str(event["dstID"])

        return (src_repr, dst_repr)

    def get_ips4(self, event: Dict) -> Tuple[str, str]:
        ipv4 = event["summary"]["ipv4"]
        fields = ipv4.split(" ")
        src = next(x for x in fields if "SrcIP=" in x).split("=")[1]
        dst = next(x for x in fields if "DstIP=" in x).split("=")[1]
        return (src, dst)

    def get_ips6(self, event: Dict) -> Tuple[str, str]:
        ipv4 = event["summary"]["ipv6"]
        fields = ipv4.split(" ")
        src = next(x for x in fields if "SrcIP=" in x).split("=")[1]
        dst = next(x for x in fields if "DstIP=" in x).split("=")[1]
        return (src, dst)

    def get_ep_by_ip(self, ip: str) -> Dict:
        return next(e for e in self.endpoints.values()
                    if any(ip == a["ipv4"] or ip == a["ipv6"]
                           for a in e["networking"]["addressing"]))

    def get_ports(self, event: Dict) -> Tuple[str, str]:
        try:
            l4 = event["summary"]["tcp"]
        except KeyError:
            l4 = event["summary"]["udp"]

        fields = l4.split(" ")
        src = next(x for x in fields if "SrcPort=" in x).split("=")[1]
        dst = next(x for x in fields if "DstPort=" in x).split("=")[1]
        return (src, dst)

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
