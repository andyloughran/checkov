import re
from typing import Union, Dict, Any

from checkov.common.models.enums import CheckResult, CheckCategories
from checkov.arm.base_resource_check import BaseResourceCheck

# https://docs.microsoft.com/en-us/azure/templates/microsoft.network/networksecuritygroups
# https://docs.microsoft.com/en-us/azure/templates/microsoft.network/networksecuritygroups/securityrules

INTERNET_ADDRESSES = ["*", "0.0.0.0", "<nw>/0", "/0", "internet", "any"]  # nosec
PORT_RANGE = re.compile(r"\d+-\d+")


class NSGRulePortAccessRestricted(BaseResourceCheck):
    def __init__(self, name: str, check_id: str, port: int) -> None:
        supported_resources = (
            "Microsoft.Network/networkSecurityGroups",
            "Microsoft.Network/networkSecurityGroups/securityRules",
        )
        categories = (CheckCategories.NETWORKING,)
        super().__init__(name=name, id=check_id, categories=categories, supported_resources=supported_resources)
        self.port = port

    def is_port_in_range(self, port_range: Union[int, str]) -> bool:
        if re.match(PORT_RANGE, str(port_range)):
            start, end = int(port_range.split("-")[0]), int(port_range.split("-")[1])
            if start <= self.port <= end:
                return True
        if port_range in (str(self.port), "*"):
            return True
        return False

    def scan_resource_conf(self, conf: Dict[str, Any]) -> CheckResult:
        if "properties" in conf:
            securityRules = []
            if "type" in conf and conf["type"] == "Microsoft.Network/networkSecurityGroups":
                if "securityRules" in conf["properties"]:
                    securityRules.extend(conf["properties"]["securityRules"])
            if "type" in conf and conf["type"] == "Microsoft.Network/networkSecurityGroups/securityRules":
                securityRules.append(conf)

            for rule in securityRules:
                portRanges = []
                sourcePrefixes = []
                if "properties" in rule:
                    if "access" in rule["properties"] and rule["properties"]["access"].lower() == "allow":
                        if "direction" in rule["properties"] and rule["properties"]["direction"].lower() == "inbound":
                            if "protocol" in rule["properties"] and rule["properties"]["protocol"].lower() == "tcp":
                                if "destinationPortRanges" in rule["properties"]:
                                    portRanges.extend(rule["properties"]["destinationPortRanges"])
                                if "destinationPortRange" in rule["properties"]:
                                    portRanges.append(rule["properties"]["destinationPortRange"])

                                if "sourceAddressPrefixes" in rule["properties"]:
                                    sourcePrefixes.extend(rule["properties"]["sourceAddressPrefixes"])
                                if "sourceAddressPrefix" in rule["properties"]:
                                    sourcePrefixes.append(rule["properties"]["sourceAddressPrefix"])

                                for portRange in portRanges:
                                    if self.is_port_in_range(portRange):
                                        for prefix in sourcePrefixes:
                                            if prefix in INTERNET_ADDRESSES:
                                                return CheckResult.FAILED

        return CheckResult.PASSED
