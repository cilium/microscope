from typing import Dict, List


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

        for ep in endpoint_data:
            podname = ep['status']['external-identifiers']['pod-name']
            # the str(ep['id']) below is needed because the ID is an
            # int in json
            self.epid_resolutions[str(ep['id'])] = podname

        self.identities = {id["id"]: id["labels"] for id in
                           [e["status"]["identity"]
                            for e in endpoint_data]}

        self.identities[0] = ["reserved:unknown"]
        self.identities[1] = ["reserved:host"]
        self.identities[2] = ["reserved:world"]
        self.identities[3] = ["reserved:cluster"]
        self.identities[4] = ["reserved:health"]

    def resolve_ip(self, ip) -> str:
        return self.ip_resolutions[ip]

    def resolve_eid(self, eid) -> str:
        return self.epid_resolutions[eid]

    def resolve_identity(self, id) -> List:
        return self.identities[id]
