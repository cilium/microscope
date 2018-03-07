import argparse

from kubernetes import config
from kubernetes.client import Configuration
from kubernetes.client.apis import core_v1_api

from microscope.monitor.monitor import MonitorRunner, MonitorArgs
from microscope.ui.ui import ui


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--timeout-monitors', type=int, default=60,
                        help='Will remove monitor output which did '
                        'not update in last `timeout` seconds. '
                        'Will not work on last monitor on screen.')
    parser.add_argument('--verbose', action='store_true', default=False)
    parser.add_argument('--hex', action='store_true', default=False)

    # taken from github.com/cilium/cilium/cmd/monitor.go
    type_choices = ['drop', 'debug', 'capture', 'trace']
    parser.add_argument('--type', action='append', default=[],
                        choices=type_choices)

    parser.add_argument('--node', action='append', default=[],
                        help='Cilium pod names. Can specify multiple.')

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

    parser.add_argument('--force-command', type=str, default="",
                        help='Execute command as-provided in argument on '
                        'all specified nodes and show output.')

    parser.add_argument('--cilium-namespace', type=str, default="kube-system",
                        help='Specify namespace in which Cilium pods reside')

    parser.add_argument('--clear-monitors', action='store_true', default=False,
                        help='Kill all `cilium monitor` on Cilium nodes. '
                        'Helpful for debugging')

    args = parser.parse_args()

    try:
        config.load_kube_config()
    except FileNotFoundError:
        config.load_incluster_config()

    c = Configuration()
    c.assert_hostname = False
    Configuration.set_default(c)
    api = core_v1_api.CoreV1Api()
    runner = MonitorRunner(args.cilium_namespace, api)

    monitor_args = MonitorArgs(args.verbose, args.hex, args.selector, args.pod,
                               args.endpoint, args.to_selector, args.to_pod,
                               args.to_endpoint, args.from_selector,
                               args.from_pod, args.from_endpoint, args.type)

    try:
        if args.clear_monitors:
            cmd = "pkill -f \"cilium monitor\""
        else:
            cmd = args.force_command

        runner.run(monitor_args, args.node, cmd)
        if not args.clear_monitors:
            ui(runner, args.timeout_monitors)
    except KeyboardInterrupt as e:
        pass
    finally:
        runner.finish()


if __name__ == '__main__':
    main()
