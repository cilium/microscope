import time

from microscope.monitor.monitor import MonitorOutputProcessorSimple
from microscope.monitor.monitor import MonitorOutputProcessorVerbose
from microscope.monitor.monitor import MonitorOutputProcessorL7


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
