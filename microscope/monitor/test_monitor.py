import time
from microscope.monitor.parser import MonitorOutputProcessorSimple
from microscope.monitor.parser import MonitorOutputProcessorVerbose
from microscope.monitor.parser import MonitorOutputProcessorJSON
from microscope.monitor.epresolver import EndpointResolver


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
    p = MonitorOutputProcessorJSON(None)

    p.add_out('{"trolo1":"lolo1"}\n')
    p.add_out('{"trolo2":"')

    assert p.get_event() == '{"trolo1":"lolo1"}'
    assert p.get_event() is None

    p.add_out('lolo2"}\n')
    assert p.get_event() == '{"trolo2":"lolo2"}'


test_endpoints = [
    {
        'id': 5766,
        'status': {
            'external-identifiers': {
                'pod-name': 'default:app2'
            },
            'networking': {'addressing': [{'ipv4': '10.0.0.1',
                                           'ipv6': 'f00d::a0f:0:0:1686'}]
                           },
            'identity': {
                'id': 21877,
                'labels': ['k8s:id=app2',
                           'k8s:io.kubernetes.pod.namespace=default']
            },
            'labels': {
                'security-relevant': [
                    'k8s:id=app2',
                    'k8s:io.kubernetes.pod.namespace=default']
            }
        }
    },
    {
        'id': 30391,
        'status': {
            'external-identifiers': {
                'pod-name': 'default:app1-799c454b56-xcw8t'
            },
            'networking': {'addressing': [{'ipv4': '10.0.0.2',
                                           'ipv6': 'f00d::a0f:0:0:1687'}]
                           },
            'identity': {
                'id': 50228,
                'labels': ['k8s:id=app1',
                           'k8s:io.kubernetes.pod.namespace=default']
            },
            'labels': {
                'security-relevant': [
                    'k8s:id=app1',
                    'k8s:io.kubernetes.pod.namespace=default']
            }
        }
    },
    {
        'id': 29898,
        'status': {
            'external-identifiers': {
                'pod-name': 'kube-system:cilium-health-minikube'
            },
            'networking': {'addressing': [{'ipv4': '10.0.0.3',
                                           'ipv6': 'f00d::a0f:0:0:1688'}]
                           },
            'identity': {
                'id': 21877,
                'labels': ['reserved:health']
            },
            'labels': {
                'security-relevant': ['reserved:health']
            }
        }
    },
    {
        'id': 33243,
        'status': {
            'external-identifiers': {
                'pod-name': 'default:app1-799c454b56-c4q6p'
            },
            'networking': {'addressing': [{'ipv4': '10.0.0.4',
                                           'ipv6': 'f00d::a0f:0:0:1689'}]
                           },
            'identity': {
                'id': 50228,
                'labels': ['k8s:id=app1',
                           'k8s:io.kubernetes.pod.namespace=default']
            },
            'labels': {
                'security-relevant': [
                    'k8s:id=app1',
                    'k8s:io.kubernetes.pod.namespace=default']
            }
        }
    },
    {
        'id': 51796,
        'status': {
            'external-identifiers': {
                'pod-name': 'default:app3'
            },
            'networking': {'addressing': [{'ipv4': '10.0.0.5',
                                           'ipv6': 'f00d::a0f:0:0:1690'}]
                           },
            'identity': {
                'id': 36720,
                'labels': ['k8s:id=app3',
                           'k8s:io.kubernetes.pod.namespace=default'],
            },
            'labels': {
                'security-relevant': [
                    'k8s:id=app3',
                    'k8s:io.kubernetes.pod.namespace=default']
            }
        }
    }
]


def test_json_processor():
    resolver = EndpointResolver(test_endpoints)
    p = MonitorOutputProcessorJSON(resolver)

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
    "summary": {
        "l2":{"src":"22:46:9b:ed:13:e9", "dst":"06:ea:01:96:66:ef"},
        "l3":{"src":"10.0.0.1", "dst":"10.0.0.2"},
        "l4":{"src":"80", "dst":"37934"}
    }
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
    "summary": {
        "l2":{"src":"22:46:9b:ed:13:e9", "dst":"06:ea:01:96:66:ef"},
        "l3":{"src":"10.0.0.1", "dst":"10.0.0.2"},
        "l4":{"src":"80", "dst":"37934"}
    }
}
""")

    p.add_out('{"type":"debug","message":"debug message","cpu":"CPU 01"}')

    p.add_out("""
{
    "cpu": "CPU 01:",
    "type": "capture",
    "mark": "0x8b0fe309",
    "message": "Delivery to ifindex 51",
    "source": 29898,
    "bytes": 66,
    "summary": "capture summary",
    "prefix": "-> cilium_health"
}
    """)

    p.add_out("""
{
    "type": "agent",
    "subtype": "Policy updated",
    "message": {
        "labels": [
            "unspec:io.cilium.k8s.policy.name=rule1",
            "unspec:io.cilium.k8s.policy.namespace=default"
        ],
        "revision": 10,
        "rule_count": 1
    }
}
    """)

    events = [x for x in p]

    assert len(events) == 7
    assert events[0] == (
        "(k8s:id=app2) => (k8s:id=app1) http GET /private Denied"
    )

    assert events[1] == (
        "(k8s:app=empire-backup) => (k8s:app=kafka)"
        " kafka fetch deathstar-plans Forwarded"
    )

    assert events[2] == (
        "trace (default:app2 10.0.0.1:80) => (default:app1-799c454b56-xcw8t 10.0.0.2:37934)"  # noqa: E501
    )

    assert events[3] == (
        "drop: Policy denied (L3) (default:app2 10.0.0.1:80) => (default:app1-799c454b56-xcw8t 10.0.0.2:37934)"  # noqa: E501
    )

    assert events[4] == (
        "debug: debug message on CPU 01"
    )

    assert events[5] == (
        "-> cilium_health: capture summary"
    )

    assert events[6] == (
        "Policy updated: {'labels': ['unspec:io.cilium.k8s.policy.name=rule1', 'unspec:io.cilium.k8s.policy.namespace=default'], 'revision': 10, 'rule_count': 1}"  # noqa: E501

    )


def test_resolver_retrieve_ep_ids():
    resolver = EndpointResolver(test_endpoints)

    ids = resolver.resolve_endpoint_ids(
        [], [],
        ["10.0.0.1", "f00d::a0f:0:0:1687"], "default")

    assert 5766 in ids
    assert 30391 in ids


def test_resolver_endpoint_ids_by_selectors():
    resolver = EndpointResolver(test_endpoints)
    app1_ids = resolver.resolve_endpoint_ids(['id=app1'], [], [], 'default')

    assert 30391 in app1_ids
    assert 33243 in app1_ids
    assert len(app1_ids) == 2


def test_resolver_endpoint_ids_by_names():
    resolver = EndpointResolver(test_endpoints)
    ids = resolver.resolve_endpoint_ids(
        [],
        ['default:app1-799c454b56-xcw8t',
         'default:app3'],
        [], 'default')

    assert 30391 in ids
    assert 51796 in ids
    assert len(ids) == 2
