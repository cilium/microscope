import argparse
import signal

from kubernetes import config
from kubernetes.client import Configuration
from kubernetes.client.apis import core_v1_api

from microscope.monitor.runner import MonitorRunner, MonitorArgs
from microscope.monitor.runner import NoEndpointException
from microscope.ui.ui import ui
from microscope.batch.batch import batch


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--timeout-monitors', type=int, default=0,
                        help='Will remove monitor output which did '
                        'not update in last `timeout` seconds. '
                        'Will not work on last monitor on screen.')
    parser.add_argument('--verbose', action='store_true', default=False)
    parser.add_argument('--hex', action='store_true', default=False)

    # taken from github.com/cilium/cilium/cmd/monitor.go
    type_choices = ['drop', 'debug', 'capture', 'trace', 'l7', 'agent']
    parser.add_argument('--type', action='append', default=[],
                        choices=type_choices)

    parser.add_argument('--node', action='append', default=[],
                        help='Specify which nodes monitor will be run on. '
                        'Can match either by cilium pod names or k8s node '
                        'names. Can specify multiple.')

    parser.add_argument('--selector', action='append', default=[],
                        help='k8s equality label selectors for pods which '
                        'monitor should listen to. each selector will '
                        'retrieve its own set of pods. '
                        'Format is "label-name=label-value" '
                        'Can specify multiple.')
    parser.add_argument('--pod', action='append', default=[],
                        help='pod names in form of "namespace:pod-name", '
                        'if there is no namespace, default is assumed. '
                        'Can specify multiple.')
    parser.add_argument('--endpoint', action='append', type=int, default=[],
                        help='Cilium endpoint ids. Can specify multiple.')
    parser.add_argument('--ip', action='append', default=[],
                        help='K8s pod ips. Can specify multiple.')

    parser.add_argument('--to-selector', action='append', default=[],
                        help='k8s equality label selectors for pods which '
                        'monitor should listen to. each selector will '
                        'retrieve its own set of pods. '
                        'Matches events that go to selected pods. '
                        'Format is "label-name=label-value" '
                        'Can specify multiple.')
    parser.add_argument('--to-pod', action='append', default=[],
                        help='pod names in form of "namespace:pod-name", '
                        'if there is no namespace, default is assumed. '
                        'Matches events that go to specified pods. '
                        'Can specify multiple.')
    parser.add_argument('--to-endpoint', action='append', type=int, default=[],
                        help='Cilium endpoint ids. '
                        'Matches events that go to specified endpoints. '
                        'Can specify multiple.')
    parser.add_argument('--to-ip', action='append', default=[],
                        help='K8s pod ips. Can specify multiple.')

    parser.add_argument('--from-selector', action='append', default=[],
                        help='k8s equality label selectors for pods which '
                        'monitor should listen to. each selector will '
                        'retrieve its own set of pods. '
                        'Matches events that come from selected pods. '
                        'Format is "label-name=label-value" '
                        'Can specify multiple.')
    parser.add_argument('--from-pod', action='append', default=[],
                        help='pod names in form of "namespace:pod-name", '
                        'if there is no namespace, default is assumed. '
                        'Matches events that come from specified pods. '
                        'Can specify multiple.')
    parser.add_argument('--from-endpoint', action='append', type=int,
                        default=[],
                        help='Cilium endpoint ids. '
                        'Matches events that come from specified endpoints. '
                        'Can specify multiple.')
    parser.add_argument('--from-ip', action='append', default=[],
                        help='K8s pod ips. Can specify multiple.')

    parser.add_argument('--send-command', type=str, default="",
                        help='Execute command as-provided in argument on '
                        'all specified nodes and show output.')

    parser.add_argument('--cilium-namespace', type=str, default="kube-system",
                        help='Specify namespace in which Cilium pods reside')

    parser.add_argument('--clear-monitors', action='store_true', default=False,
                        help='Kill all `cilium monitor` on Cilium nodes. '
                        'Helpful for debugging')

    parser.add_argument('--rich', action='store_true', default=False,
                        help='Opens rich ui version')

    parser.add_argument('-n', '--namespace', type=str, default='default',
                        help='Namespace to look for selected endpoints in')

    parser.add_argument('--raw', action='store_true', default=False,
                        help='Print out raw monitor output without parsing')

    args = parser.parse_args()

    try:
        config.load_kube_config()
    except FileNotFoundError:
        config.load_incluster_config()

    c = Configuration()
    c.assert_hostname = False
    Configuration.set_default(c)
    api = core_v1_api.CoreV1Api()
    runner = MonitorRunner(args.cilium_namespace, api, args.namespace)

    monitor_args = MonitorArgs(args.verbose, args.hex,
                               args.selector, args.pod, args.endpoint,
                               args.to_selector, args.to_pod,
                               args.to_endpoint, args.from_selector,
                               args.from_pod, args.from_endpoint, args.type,
                               args.namespace, args.raw,
                               args.ip, args.to_ip, args.from_ip)

    def handle_signals(_, __):
        runner.finish()

    try:
        if args.clear_monitors:
            cmd = "pkill -f \"cilium monitor\""
        else:
            cmd = args.send_command

        runner.run(monitor_args, args.node, cmd)
        signal.signal(signal.SIGHUP, handle_signals)
        if args.rich:
            ui(runner, args.timeout_monitors)
        elif not args.clear_monitors:
            batch(runner, args.timeout_monitors)
    except KeyboardInterrupt:
        pass
    except NoEndpointException:
        print("Cilium endpoints matching pod names/label selectors not found.")
    except Exception as e:
        print("Exception encountered: " + repr(e) + " stack trace below")
        raise e
    finally:
        runner.finish()


if __name__ == '__main__':
    main()
