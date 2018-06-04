from typing import Dict, List, Set, Callable


# https://github.com/cilium/cilium/blob/master/pkg/identity/numericidentity.go#L33
reserved_identities = {
    0: ["reserved:unknown"],
    1: ["reserved:host"],
    2: ["reserved:world"],
    3: ["reserved:cluster"],
    4: ["reserved:health"],
    5: ["reserved:init"]
}


class EndpointResolver:
    """EndpointResolver resolves various fields to the pod-name

    endpoint_data: a list of lists of endpoint objects obtained from
                   cilium-agent or k8s CEPs
    """
    def __init__(self,
                 endpoint_data: [Dict]):

        self.ip_resolutions = {}
        self.epid_resolutions = {}
        self.ip_to_epid_resolutions = {}
        self.endpoint_data = endpoint_data

        for ep in endpoint_data:
            podname = ep['status']['external-identifiers']['pod-name']
            for ip in ep['status']['networking']['addressing']:
                self.ip_resolutions[ip['ipv4']] = podname
                self.ip_resolutions[ip['ipv6']] = podname
                self.ip_to_epid_resolutions[ip['ipv4']] = ep['id']
                self.ip_to_epid_resolutions[ip['ipv6']] = ep['id']

            # the str(ep['id']) below is needed because the ID is an
            # int in json
            self.epid_resolutions[str(ep['id'])] = podname

        ep_identities = {id["id"]: id["labels"] for id in
                           [e["status"]["identity"]
                            for e in endpoint_data]}

        self.identities = {**ep_identities, **reserved_identities}

    def resolve_ip(self, ip) -> str:
        if ip in self.ip_resolutions:
            return self.ip_resolutions[ip]
        return ""

    def resolve_eid(self, eid) -> str:
        if eid in self.epid_resolutions:
            return self.epid_resolutions[eid]
        return ""

    def resolve_identity(self, id) -> List:
        if id in self.identities:
            return self.identities[id]
        return ""

    def resolve_id_from_ip(self, ip) -> str:
        if ip in self.ip_to_epid_resolutions:
            return self.ip_to_epid_resolutions[ip]
        return ""

    def resolve_endpoint_ids(self, selectors: List[str],
                             pod_names: List[str],
                             ips: List[str],
                             namespace: str) -> Set[int]:
        """resolve_endpoint_ids returns endpoint ids that match
        selectors, pod names and ips provided
        """
        ids = set()
        ids.update(
            self.resolve_endpoint_ids_from_pods(pod_names),
            self.resolve_endpoint_ids_from_selectors(selectors, namespace),
            self.resolve_endpoint_ids_from_ips(ips)
        )
        return ids

    def resolve_endpoint_ids_from_pods(self, pod_names: List[str]):

        try:
            namesMatch = {
                endpoint['id'] for endpoint in self.endpoint_data
                if
                endpoint['status']['external-identifiers']['pod-name']
                in pod_names
            }
        except (KeyError, TypeError):
            # fall back to older API structure
            namesMatch = {endpoint['id'] for endpoint in self.endpoint_data
                          if endpoint['pod-name'] in pod_names}
        return namesMatch

    def resolve_endpoint_ids_from_selectors(self, selectors: List[str],
                                            namespace: str):

        namespace_matcher = f"k8s:io.kubernetes.pod.namespace={namespace}"

        def labels_match(data, selectors: List[str],
                         labels_getter: Callable[[Dict], List[str]]):
            return {
                endpoint['id'] for endpoint in data
                if any([
                    any(
                        [selector in label
                         for selector in selectors])
                    for label
                    in labels_getter(endpoint)
                ]) and namespace_matcher in labels_getter(endpoint)
            }

        getters = [
                lambda x: x['status']['labels']['security-relevant'],
                lambda x: x['labels']['orchestration-identity'],
                lambda x: x['labels']['security-relevant']
        ]
        labelsMatch = []
        for getter in getters:
            try:
                labelsMatch = labels_match(
                  self.endpoint_data, selectors, getter)
            except (KeyError, TypeError):
                continue
            break
        return labelsMatch

    def resolve_endpoint_ids_from_ips(self, ips: List[str]):
        return {self.resolve_id_from_ip(ip) for ip in ips} - {''}
