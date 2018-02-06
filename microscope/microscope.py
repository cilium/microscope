import argparse

from kubernetes import config
from kubernetes.client import Configuration
from kubernetes.client.apis import core_v1_api

from monitor import MonitorRunner
from ui import ui


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', type=bool, default=False)
    parser.add_argument('--selector', action='append', default=[],
                        help='k8s equality label selectors for pods which '
                        'monitor should listen to. each selector will '
                        'retrieve its own set of pods. '
                        'Format is "label-name=label-value" '
                        'Can specify multiple.')
    parser.add_argument('--pod', action='append', default=[],
                        help='pod names in form of "namespace:pod-name" '
                        'Can specify multiple.')
    parser.add_argument('--endpoint', action='append', type=int, default=[],
                        help='Cilium endpoint ids. Can specify multiple.')
    parser.add_argument('--node', action='append', default=[],
                        help='Cilium pod names. Can specify multiple.')

    args = parser.parse_args()

    try:
        config.load_kube_config()
    except FileNotFoundError:
        config.load_incluster_config()

    c = Configuration()
    c.assert_hostname = False
    Configuration.set_default(c)
    api = core_v1_api.CoreV1Api()
    runner = MonitorRunner('kube-system', api)

    try:
        runner.run(args.verbose, args.selector,
                   args.pod, args.endpoint, args.node)
    except ValueError as e:
        print(e)
        runner.finish()
        return

    ui(runner)
    runner.finish()


if __name__ == '__main__':
    main()
