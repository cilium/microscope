import time

from microscope.monitor.parser import MonitorOutputProcessorSimple
from microscope.monitor.parser import MonitorOutputProcessorVerbose
from microscope.monitor.parser import MonitorOutputProcessorL7
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


def test_l7_processor_parse():
    p = MonitorOutputProcessorL7()

    res = p.parse_l7_line(
        "<- Request http from 0 ([k8s:io.kubernetes.pod.namespace=default k8s"
        ":id=app2]) to 48896 ([k8s:id=app1 k8s:io.kubernetes.pod.namespace=de"
        "fault]), identity 63904->14152, verdict Forwarded GET http://10.110."
        "31.154/public => 0")

    assert res == (
                   "([k8s:id=app2]) ="
                   "> ([k8s:id=app1])"
                   " http GET http://10.110.31.154/public Forwarded")

    res = p.parse_l7_line(
        "<- Request kafka from 0 ([k8s:app=empire-backup k8s:io.kubernetes.pod"
        ".namespace=default]) to 173 ([k8s:io.kubernetes.pod.namespace=default"
        " k8s:app=kafka]), identity 28858->48339, verdict Forwarded offsetfetc"
        "h topic deathstar-plans => 0"
    )

    assert res == (
        "([k8s:app=empire-backup]) => "
        "([k8s:app=kafka]) "
        "kafka"
        " offsetfetch topic deathstar-plans Forwarded"
    )


def test_l7_line_break():
    p = MonitorOutputProcessorL7()

    p.add_out(
        "<- Request http from 0 ([k8s:io.kubernetes.pod.namespace=default k8s"
        ":id=app2]) to 48896 ([k8s:id=app1 k8s:io.kubernetes.pod.namespace=de"
    )

    p.add_out(
        "fault]), identity 63904->14152, verdict Forwarded GET http://10.110."
        "31.154/public => 0"
    )

    lines = [x for x in p]
    assert len(lines) == 1

    assert lines[0] == (
        "([k8s:id=app2]) ="
        "> ([k8s:id=app1]) "
        "http GET http://10.110.31.154/public Forwarded"
    )

    p.add_out("Listening for events on 2 CPUs with 64x4096 of shared memory\n")
    p.add_out("Press Ctrl-C to quit\n")

    p.add_out(
        "<- Request http from 0 ([k8s:io.kubernetes.pod.namespace=default k8s"
        ":id=app2]) to 48896 ([k8s:id=app1 k8s:io.kubernetes.pod.namespace=de"
    )

    lines = [x for x in p]
    assert len(lines) == 2

    p.add_out(
        "fault]), identity 63904->14152, verdict Forwarded GET http://10.110."
        "31.154/public => 0\n"
    )

    p.add_out(
        "<- Request http from 0 ([k8s:io.kubernetes.pod.namespace=default k8s"
        ":id=app2]) to 48896 ([k8s:id=app1 k8s:io.kubernetes.pod.namespace=de"
    )

    p.add_out(
        "fault]), identity 63904->14152, verdict Forwarded GET http://10.110."
        "31.154/public => 0"
    )

    lines = [x for x in p]
    assert len(lines) == 2

    for x in lines:
        assert x == (
            "([k8s:id=app2]) ="
            "> ([k8s:id=app1]) "
            "http GET http://10.110.31.154/public Forwarded"
        )


def test_l7_multiple_lines():
    p = MonitorOutputProcessorL7()

    p.add_out(
        "<- Request http from 0 ([k8s:io.kubernetes.pod.namespace=default k8s"
        ":id=app2]) to 48896 ([k8s:id=app1 k8s:io.kubernetes.pod.namespace=de"
    )

    p.add_out(
        "fault]), identity 63904->14152, verdict Forwarded GET http://10.110."
        "31.154/public => 0\n"
    )

    p.add_out(
        "<- Request http from 0 ([k8s:io.kubernetes.pod.namespace=default k8s"
        ":id=app2]) to 48896 ([k8s:id=app1 k8s:io.kubernetes.pod.namespace=de"
    )

    p.add_out(
        "fault]), identity 63904->14152, verdict Forwarded GET http://10.110."
        "31.154/public => 0\n"
    )

    p.add_out(
        "<- Request http from 0 ([k8s:io.kubernetes.pod.namespace=default k8s"
        ":id=app2]) to 48896 ([k8s:id=app1 k8s:io.kubernetes.pod.namespace=de"
    )

    p.add_out(
        "fault]), identity 63904->14152, verdict Forwarded GET http://10.110."
        "31.154/public => 0\n"
    )
    p.add_out(
        "<- Request http from 0 ([k8s:io.kubernetes.pod.namespace=default k8s"
        ":id=app2]) to 48896 ([k8s:id=app1 k8s:io.kubernetes.pod.namespace=de"
    )

    p.add_out(
        "fault]), identity 63904->14152, verdict Forwarded GET http://10.110."
        "31.154/public => 0\n"
    )
    p.add_out(
        "<- Request http from 0 ([k8s:io.kubernetes.pod.namespace=default k8s"
        ":id=app2]) to 48896 ([k8s:id=app1 k8s:io.kubernetes.pod.namespace=de"
    )

    p.add_out(
        "fault]), identity 63904->14152, verdict Forwarded GET http://10.110."
        "31.154/public => 0\n"
    )

    lines = [x for x in p]
    assert len(lines) == 5

    for x in lines:
        assert x == (
            "([k8s:id=app2]) ="
            "> ([k8s:id=app1]) "
            "http GET http://10.110.31.154/public Forwarded"
        )


def test_json_processor_get_event():
    p = MonitorOutputProcessorJSON(None)

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


def test_json_processor():
    p = MonitorOutputProcessorJSON(test_identities)

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
"mark": "0xf5a98afe",
"ifindex": "lxc9e076",
"state": "established",
"observationPoint": "to-endpoint",
"source": 30391,
"bytes": 66,
"srcLabel": 45805,
"dstLabel": 50228,
"dstID": 30391,
"summary": {
"ethernet": "Ethernet\t{Contents=[..14..] Payload=[..86..]  Length=0}"
}
}
""")

    events = [x for x in p]

    assert len(events) == 3
    assert events[0] == (
        "(k8s:id=app2) => (k8s:id=app1) http GET /private Denied"
    )

    assert events[1] == (
        "(k8s:app=empire-backup) => (k8s:app=kafka)"
        " kafka fetch deathstar-plans Forwarded"
    )

    assert events[2] == (
        "(k8s:id=app2) => (k8s:id=app1)"
    )
