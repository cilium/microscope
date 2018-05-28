from typing import Dict, List


# https://github.com/cilium/cilium/blob/master/pkg/identity/numericidentity.go#L33
reserved_identities = {
    0: ["reserved:unknown"],
    1: ["reserved:host"],
    2: ["reserved:world"],
    3: ["reserved:cluster"],
    4: ["reserved:health"]
}


class EndpointResolver:
    """EndpointResolver resolves various fields to the pod-name

    resolve_ips: convert IPs belonging to an endpoint to the podname
    endpoint_data: a list of lists of endpoint objects obtained from
                   cilium-agent or k8s CEPs
    """
    def __init__(self,
                 endpoint_data: [Dict]):

        self.ip_resolutions = {}
        self.epid_resolutions = {}

        for ep in endpoint_data:
            podname = ep['status']['external-identifiers']['pod-name']
            for ip in ep['status']['networking']['addressing']:
                self.ip_resolutions[ip['ipv4']] = podname
                self.ip_resolutions[ip['ipv6']] = podname

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
