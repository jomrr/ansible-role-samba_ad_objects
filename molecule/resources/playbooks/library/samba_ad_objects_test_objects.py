#!/usr/bin/python
"""Exercise role-managed directory objects and memberships."""

import importlib
from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.jomrr.samba.plugins.module_utils.samba_conn import (
    connect_samdb,
    connection_argument_spec,
)

DOCUMENTATION = r"""
module: samba_ad_objects_test_objects
short_description: Exercise managed objects throughout the Molecule lifecycle
description:
  - Verifies users, OUs, nested groups and membership policies.
  - Verifies requested deletions and changes on existing directory objects.
extends_documentation_fragment:
  - jomrr.samba.connection
options:
  phase:
    description: Fixture phase to seed or verify.
    type: str
    required: true
    choices: [initial, seed, seeded, updated]
author:
  - Jonas Mauer (@jomrr)
"""

EXAMPLES = r"""
- name: SAMBA_AD_OBJECTS | Verify managed directory objects
  samba_ad_objects_test_objects:
    server: dc1.ad.example.test
    bind_username: Administrator
    bind_password: "{{ samba_ad_objects_admin_password }}"
    phase: initial
"""

ATTRIBUTES = [
    "distinguishedName",
    "displayName",
    "description",
    "member",
    "uidNumber",
    "gidNumber",
    "groupType",
    "userAccountControl",
]


def expect(record: Any, attribute: str, values: list[str]) -> None:
    """Compare directory attributes without returning any account secrets."""
    actual = [value.decode() for value in record.get(attribute, [])]
    if sorted(actual) != sorted(values):
        raise RuntimeError(f"Unexpected {attribute} on {record.dn}: {actual}")


class DirectoryChecks:
    """Check the fixture's lifecycle using native directory queries."""

    def __init__(self, samdb: Any) -> None:
        self.samdb = samdb
        self.ldb = importlib.import_module("ldb")
        self.base = str(samdb.domain_dn())
        self.root = f"OU=Molecule,{self.base}"

    def read(self, dn: str) -> Any:
        """Read attributes relevant to role-owned state, or return None."""
        matches = self.samdb.search(
            base=self.base,
            expression=f"(distinguishedName={self.ldb.binary_encode(dn)})",
            attrs=ATTRIBUTES,
        )
        return matches[0] if matches else None

    def account(self, name: str) -> Any:
        """Resolve a fixture account by its unique logon name."""
        matches = self.samdb.search(
            expression=f"(sAMAccountName={self.ldb.binary_encode(name)})",
            attrs=ATTRIBUTES,
        )
        if len(matches) != 1:
            raise RuntimeError(f"Expected one fixture account: {name}")
        return matches[0]

    def seed(self) -> None:
        """Add an unlisted member to exercise additive group management."""
        self.samdb.add_remove_group_members(
            "molecule-parent-group", ["moleculereader"], True
        )

    def initial(self, *, seeded: bool = False) -> None:
        """Verify creation, nesting and unchanged state after a check-mode run."""
        managed = self.account("molecule-managed")
        expect(
            managed, "distinguishedName", [f"CN=molecule-managed,OU=Staff,{self.root}"]
        )
        expect(managed, "displayName", ["Initial managed user"])
        expect(managed, "uidNumber", ["21001"])
        expect(managed, "gidNumber", ["21000"])
        expect(self.read(f"OU=Staff,{self.root}"), "description", ["Initial staff OU"])
        self.account("molecule-retired")
        group = self.account("molecule-managed-group")
        expect(group, "member", [str(managed.dn)])
        expect(group, "gidNumber", ["21000"])
        parent_members = [str(group.dn)]
        if seeded:
            parent_members.append(str(self.account("moleculereader").dn))
        expect(self.account("molecule-parent-group"), "member", parent_members)
        variant = self.account("molecule-scope-group")
        expect(variant, "groupType", ["8"])
        expect(variant, "member", [str(group.dn)])

    def updated(self) -> None:
        """Verify moves, membership policy overrides and deletions."""
        managed = self.account("molecule-managed")
        reader = self.account("moleculereader")
        expect(managed, "distinguishedName", [f"CN=molecule-managed,{self.root}"])
        expect(managed, "displayName", ["Updated managed user"])
        if not int(managed["userAccountControl"][0]) & 2:
            raise RuntimeError("The managed account was not disabled")
        group = self.account("molecule-managed-group")
        expect(group, "member", [str(reader.dn)])
        expect(group, "description", ["Updated managed group"])
        expect(
            self.account("molecule-parent-group"),
            "member",
            [str(group.dn), str(reader.dn)],
        )
        variant = self.account("molecule-scope-group")
        expect(variant, "groupType", ["-2147483644"])
        expect(variant, "distinguishedName", [f"CN=molecule-scope-group,{self.root}"])
        expect(variant, "member", [str(reader.dn)])
        expect(self.read(f"OU=Staff,{self.root}"), "description", ["Updated staff OU"])
        retired = self.samdb.search(
            expression=(
                "(|(sAMAccountName=molecule-retired)"
                "(sAMAccountName=molecule-retired-group))"
            ),
            attrs=[],
        )
        if retired or self.read(f"OU=Retired,{self.root}") is not None:
            raise RuntimeError("Retired accounts or their organizational units remain")


def main() -> None:
    """Seed or verify role-managed state without printing credentials."""
    module = AnsibleModule(
        argument_spec={
            **connection_argument_spec(),
            "phase": {
                "type": "str",
                "required": True,
                "choices": ["initial", "seed", "seeded", "updated"],
            },
        }
    )
    checks = DirectoryChecks(connect_samdb(module))
    phase = module.params["phase"]
    try:
        if phase == "seed":
            checks.seed()
        elif phase == "updated":
            checks.updated()
        else:
            checks.initial(seeded=phase == "seeded")
    except (checks.ldb.LdbError, RuntimeError) as error:
        module.fail_json(msg=f"Managed directory verification failed: {error}")
    else:
        module.exit_json(changed=phase == "seed")


if __name__ == "__main__":
    main()
