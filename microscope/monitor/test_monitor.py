# flake8: noqa: E501

import time
from microscope.monitor.parser import MonitorOutputProcessorSimple
from microscope.monitor.parser import MonitorOutputProcessorVerbose
from microscope.monitor.parser import MonitorOutputProcessorJSON


def test_non_verbose_mode():
    p = MonitorOutputProcessorSimple()

    output = """trololo
    line2
    line3
    line4 omg"""

    p.add_out(output)

    msgs = [x for x in p]
    assert len(msgs) == 4

    retrieved = "\n".join(msgs)

    assert output == retrieved

    p.add_out(output)

    msgs = [x for x in p]
    assert len(msgs) == 4

    retrieved = "\n".join(msgs)

    assert output == retrieved

    p.add_out(output)
    p.add_out(output)

    msgs = [x for x in p]
    assert len(msgs) == 8

    retrieved = "\n".join(msgs)

    assert output + '\n' + output == retrieved


def test_verbose_mode():
    p = MonitorOutputProcessorVerbose()

    output = """trololo
    line2
---
    line3
    line4 omg
---
    line5
    line6 omg"""

    p.add_out(output)

    msgs = [x for x in p]
    assert len(msgs) == 2

    assert msgs[0] == output.split("---")[0].strip("\n")

    assert msgs[1] == "---\n" + output.split("---")[1].strip("\n")

    time.sleep(p.last_event_wait_timeout / 1000)

    msgs = [x for x in p]
    assert len(msgs) == 1

    assert msgs[0] == "---\n" + output.split("---")[2].strip("\n")


def test_json_processor_get_event():
    p = MonitorOutputProcessorJSON(None, None)

    p.add_out('{"trolo1":"lolo1"}\n')
    p.add_out('{"trolo2":"')

    assert p.get_event() == '{"trolo1":"lolo1"}'
    assert p.get_event() is None

    p.add_out('lolo2"}\n')
    assert p.get_event() == '{"trolo2":"lolo2"}'


test_identities = {
    0: [],
    21877: ['reserved:health'],
    36720: ['k8s:id=app3', 'k8s:io.kubernetes.pod.namespace=default'],
    45805: ['k8s:io.kubernetes.pod.namespace=default', 'k8s:id=app2'],
    50228: ['k8s:id=app1', 'k8s:io.kubernetes.pod.namespace=default']}

test_endpoints = {
    5766: {'name': 'app2',
           'namespace': 'default',
           'networking': {'addressing': [{'ipv4': '10.0.0.1',
                                          'ipv6': 'f00d::a0f:0:0:1686'}]
                          }
           },
    30391: {
        'name': 'app1-799c454b56-xcw8t',
        'namespace': 'default',
        'networking': {'addressing': [{'ipv4': '10.0.0.2',
                                       'ipv6': 'f00d::a0f:0:0:1687'}]
                       },
    },
    29898: {
        'name': 'cilium-health-minikube',
        'namespace': 'kube-system',
        'networking': {'addressing': [{'ipv4': '10.0.0.3',
                                       'ipv6': 'f00d::a0f:0:0:1688'}]
                       },
    },
    33243: {
        'name': 'app1-799c454b56-c4q6p',
        'namespace': 'default',
        'networking': {'addressing': [{'ipv4': '10.0.0.4',
                                       'ipv6': 'f00d::a0f:0:0:1689'}]
                       },
    },
    51796: {'name': 'app3',
            'namespace': 'default',
            'networking': {'addressing': [{'ipv4': '10.0.0.5',
                                           'ipv6': 'f00d::a0f:0:0:1690'}]
                           }
            },
}


def test_json_processor():
    p = MonitorOutputProcessorJSON(test_identities, test_endpoints)

    p.add_out('{"type":"logRecord","observationPoint":"Ingress","flowType":')
    p.add_out('"Request","l7Proto":"http","srcEpID":0,"srcEpLabels":["k8s:i')
    p.add_out('o.kubernetes.pod.namespace=default","k8s:id=app2"],"srcIdent')
    p.add_out('ity":3338,"dstEpID":13949,"dstEpLabels":["k8s:id=app1","k8s:')
    p.add_out('io.kubernetes.pod.namespace=default"],"DstIdentity":45459,"v')
    p.add_out('erdict":"Denied","http":{"Code":403,"Method":"GET","URL":{"S')
    p.add_out('cheme":"http","Opaque":"","User":null,"Host":"app1-service",')
    p.add_out('"Path":"/private","RawPath":"","ForceQuery":false,"RawQuery"')
    p.add_out(':"","Fragment":""},"Protocol":"HTTP/1.1","Headers":{"Accept"')
    p.add_out(':["*/*"],"User-Agent":["curl/7.54.0"],"X-Request-Id":["05199')
    p.add_out('9d8-6987-4d79-9fad-729c87cb49ae"]}}}')

    p.add_out('{"type":"logRecord","observationPoi')
    p.add_out('nt":"Ingress","flowType":"Request",')
    p.add_out('"l7Proto":"kafka","srcEpID":0,"srcE')
    p.add_out('pLabels":["k8s:app=empire-backup","')
    p.add_out('k8s:io.kubernetes.pod.namespace=def')
    p.add_out('ault"],"srcIdentity":8370,"dstEpID"')
    p.add_out(':29381,"dstEpLabels":["k8s:io.kuber')
    p.add_out('netes.pod.namespace=default","k8s:a')
    p.add_out('pp=kafka"],"DstIdentity":12427,"ver')
    p.add_out('dict":"Forwarded","kafka":{"ErrorCo')
    p.add_out('de":0,"APIVersion":5,"APIKey":"fetc')
    p.add_out('h","CorrelationID":10,"Topic":{"Top')
    p.add_out('ic":"deathstar-plans"}}}')

    p.add_out("""
{
    "cpu": "CPU 01:",
    "type": "trace",
    "mark": "0xd3f88100",
    "ifindex": "lxca3b25",
    "state": "reply",
    "observationPoint": "to-endpoint",
    "traceSummary": "-> endpoint 5766",
    "source": 5766,
    "bytes": 66,
    "srcLabel": 49055,
    "dstLabel": 20496,
    "dstID": 5766,
    "summary": {"""
      '"ethernet": "Ethernet\t{Contents=[..14..] Payload=[..54..] SrcMAC=22:46:9b:ed:13:e9 DstMAC=06:ea:01:96:66:ef EthernetType=IPv4 Length=0}",'  # noqa: E501
      '"ipv4": "IPv4\t{Contents=[..20..] Payload=[..32..] Version=4 IHL=5 TOS=0 Length=52 Id=6649 Flags=DF FragOffset=0 TTL=63 Protocol=TCP Checksum=8653 SrcIP=10.0.0.1 DstIP=10.0.0.2 Options=[] Padding=[]}",'  #noqa: E501
      '"tcp": "TCP\t{Contents=[..32..] Payload=[] SrcPort=80(http) DstPort=37934 Seq=60693151 Ack=4035039026 DataOffset=8 FIN=true SYN=false RST=false PSH=false ACK=true URG=false ECE=false CWR=false NS=false Window=219 Checksum=37 Urgent=0 Options=[TCPOption(NOP:), TCPOption(NOP:), TCPOption(Timestamps:23462012/23462009 0x0166007c01660079)] Padding=[]}"'  # noqa: E501
    """}
}
""")

    p.add_out("""
{
    "cpu": "CPU 00:",
    "type": "drop",
    "mark": "0xa9263786",
    "ifindex": "lxc05f8b",
    "reason": "Policy denied (L3)",
    "source": 5766,
    "bytes": 66,
    "srcLabel": 49055,
    "dstLabel": 20496,
    "dstID": 5766,
    "summary": {"""
      '"ethernet": "Ethernet\t{Contents=[..14..] Payload=[..54..] SrcMAC=22:46:9b:ed:13:e9 DstMAC=06:ea:01:96:66:ef EthernetType=IPv4 Length=0}",'  # noqa: E501
      '"ipv4": "IPv4\t{Contents=[..20..] Payload=[..32..] Version=4 IHL=5 TOS=0 Length=52 Id=6649 Flags=DF FragOffset=0 TTL=63 Protocol=TCP Checksum=8653 SrcIP=10.0.0.1 DstIP=10.0.0.2 Options=[] Padding=[]}",'  #noqa: E501
      '"tcp": "TCP\t{Contents=[..32..] Payload=[] SrcPort=80(http) DstPort=37934 Seq=60693151 Ack=4035039026 DataOffset=8 FIN=true SYN=false RST=false PSH=false ACK=true URG=false ECE=false CWR=false NS=false Window=219 Checksum=37 Urgent=0 Options=[TCPOption(NOP:), TCPOption(NOP:), TCPOption(Timestamps:23462012/23462009 0x0166007c01660079)] Padding=[]}"'  # noqa: E501
    """}
}
""")

    events = [x for x in p]

    assert len(events) == 4
    assert events[0] == (
        "(k8s:id=app2) => (k8s:id=app1) http GET /private Denied"
    )

    assert events[1] == (
        "(k8s:app=empire-backup) => (k8s:app=kafka)"
        " kafka fetch deathstar-plans Forwarded"
    )

    assert events[2] == (
        "trace (default:app2 10.0.0.1:80(http)) => (default:app1-799c454b56-xcw8t 10.0.0.2:37934)"
    )

    assert events[3] == (
        "drop: Policy denied (L3) (default:app2 10.0.0.1:80(http)) => (default:app1-799c454b56-xcw8t 10.0.0.2:37934)"
    )


def test_json_processor_ipv4_retrieve():
    p = MonitorOutputProcessorJSON(None, None)
    event = {
        "summary": {
            "ipv4": 'IPv4\t{Contents=[..20..] Payload=[..32..] Version=4 IHL=5 TOS=0 Length=52 Id=6649 Flags=DF FragOffset=0 TTL=63 Protocol=TCP Checksum=8653 SrcIP=10.0.0.1 DstIP=10.0.0.2 Options=[] Padding=[]}'  #noqa: E501
        }
    }
    src, dst = p.get_ips4(event)

    assert src == "10.0.0.1"
    assert dst == "10.0.0.2"

def test_json_processor_retrieve_ep_by_ip():
    p = MonitorOutputProcessorJSON(None, test_endpoints)

    ep = p.get_ep_by_ip("10.0.0.2")

    assert ep == test_endpoints[30391]

    ep = p.get_ep_by_ip("f00d::a0f:0:0:1687")
    assert ep == test_endpoints[30391]

    try:
        p.get_ep_by_ip("trololo")
        assert False
    except StopIteration:
        pass

    for endpoint in test_endpoints.values():
        ep = p.get_ep_by_ip(endpoint["networking"]["addressing"][0]["ipv4"])
        assert ep == endpoint
        ep = p.get_ep_by_ip(endpoint["networking"]["addressing"][0]["ipv6"])
        assert ep == endpoint

def test_json_processor_port_retrieve():
    p = MonitorOutputProcessorJSON(None, None)
    event = {
        "summary": {
            "tcp": "TCP\t{Contents=[..32..] Payload=[] SrcPort=80(http) DstPort=37934 Seq=60693151 Ack=4035039026 DataOffset=8 FIN=true SYN=false RST=false PSH=false ACK=true URG=false ECE=false CWR=false NS=false Window=219 Checksum=37 Urgent=0 Options=[TCPOption(NOP:), TCPOption(NOP:), TCPOption(Timestamps:23462012/23462009 0x0166007c01660079)] Padding=[]}"  # noqa: E501
        }
    }
    src, dst = p.get_ports(event)

    assert src == "80(http)"
    assert dst == "37934"
