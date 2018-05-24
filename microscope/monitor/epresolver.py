import re

from typing import Dict


def substitute(matcher, lookup, text):
    """Substitute matched fields in text by looking them up, then return it"""
    if matcher is None:
        return text
    # When the matcher regex matches a field, look up the substitution in
    # lookup
    return matcher.sub(lambda m: lookup[m.string[m.start():m.end()]], text)


class EndpointResolver:
    """EndpointResolver resolves various fields to the pod-name

    resolve_ips: convert IPs belonging to an endpoint to the podname
    endpoint_data: a list of lists of endpoint objects obtained from
                   cilium-agent or k8s CEPs
    """
    def __init__(self,
                 resolve_ips: bool,
                 resolve_ids: bool,
                 endpoint_data: [Dict]):

        self.ip_resolutions = {}
        self.epid_resolutions = {}
        self.ip_resolutions_regex = None
        self.epid_resolutions_regex = None

        if resolve_ips:  # if false, use the empty dict above that does no work
            for ep in endpoint_data:
                podname = ep['status']['external-identifiers']['pod-name']
                for ip in ep['status']['networking']['addressing']:
                    self.ip_resolutions[ip['ipv4']] = podname
                    self.ip_resolutions[ip['ipv6']] = podname
            self.ip_resolutions_regex = re.compile(
                "(%s)" % "|".join(map(re.escape, self.ip_resolutions.keys())))

        if resolve_ids:  # if false, use the empty dict above that does no work
            for ep in endpoint_data:
                podname = ep['status']['external-identifiers']['pod-name']
                # the str(ep['id']) below is needed because the ID is an
                # int in json
                self.epid_resolutions["endpoint "+str(ep['id'])] = (
                    "endpoint " + podname)
            self.epid_resolutions_regex = re.compile(
                "(%s)" % "|".join(map(re.escape,
                                      self.epid_resolutions.keys())))
        print(self.ip_resolutions)
        print(self.epid_resolutions)

    def resolve_to_podnames(self, line):
        """replace fields in line with the podname, if configured"""
        line = substitute(self.ip_resolutions_regex, self.ip_resolutions,
                          line)
        line = substitute(self.epid_resolutions_regex, self.epid_resolutions,
                          line)
        return line

    def ip_to_podname(self, ip) -> str:
        if ip in self.ip_resolutions:
            return self.ip_resolutions[ip]
        return ip

    def eid_to_podname(self, eid) -> str:
        if eid in self.epid_resolutions:
            return self.epid_resolutions[eid]
        return eid
