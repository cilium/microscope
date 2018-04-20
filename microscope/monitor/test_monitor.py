import time

from microscope.monitor.monitor import MonitorOutputProcessorSimple
from microscope.monitor.monitor import MonitorOutputProcessorVerbose


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
