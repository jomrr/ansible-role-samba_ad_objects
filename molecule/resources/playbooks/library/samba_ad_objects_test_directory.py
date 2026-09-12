#!/usr/bin/python
"""Exercise reserved DNS names and authenticated client update restrictions."""

import tempfile
from pathlib import Path
from typing import Any

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.jomrr.samba.plugins.module_utils.samba_conn import (
    connection_argument_spec,
)

DOCUMENTATION = r"""
module: samba_ad_objects_test_directory
short_description: Verify reserved DNS names in the Molecule fixture
description:
  - Checks the reserved DNS names and refuses authenticated client updates.
extends_documentation_fragment:
  - jomrr.samba.connection
author:
  - Jonas Mauer (@jomrr)
"""

EXAMPLES = r"""
- name: SAMBA_AD_OBJECTS | Verify DNS reservations and authenticated update restrictions
  samba_ad_objects_test_directory:
    server: dc1.ad.example.test
    realm: AD.EXAMPLE.TEST
    bind_username: Administrator
    bind_password: "{{ samba_ad_objects_admin_password }}"
"""


def ticket(module: Any, username: str, password: str, cache: str) -> None:
    """Obtain an ordinary domain user ticket for authenticated DNS updates."""
    environment = {"KRB5CCNAME": f"FILE:{cache}", "LC_ALL": "C"}
    module.run_command(
        ["kinit", f"{username}@{module.params['realm']}"],
        data=password,
        environ_update=environment,
        check_rc=True,
    )


def verify_dns(module: Any, cache: str) -> None:
    """Verify reservations and attempt changes with an ordinary user's ticket."""
    domain = module.params["realm"].lower()
    for name in ("wpad", "isatap"):
        _, records, _ = module.run_command(
            ["dig", "@127.0.0.1", f"{name}.{domain}", "A", "+short"], check_rc=True
        )
        if records.strip() != "127.0.0.1":
            raise RuntimeError(f"DNS name {name} is not reserved at 127.0.0.1")
        status, output, error = module.run_command(
            ["nsupdate", "-g", "-v"],
            data=(
                f"server {module.params['server']}\nzone {domain}\n"
                f"update add {name}.{domain} 60 A 192.0.2.123\nsend\n"
            ),
            environ_update={"KRB5CCNAME": f"FILE:{cache}"},
        )
        if status == 0 or "REFUSED" not in output + error:
            raise RuntimeError(
                f"Reserved DNS name {name} did not refuse the client update"
            )


def main() -> None:
    """Run functional checks using only disposable credentials and objects."""
    module = AnsibleModule(argument_spec=connection_argument_spec())
    try:
        with tempfile.TemporaryDirectory(
            prefix="samba-ad-objects-tickets-"
        ) as temporary:
            cache = str(Path(temporary) / "ccache")
            ticket(module, "moleculereader", "Molecule-Only-Reader1!", cache)
            verify_dns(module, cache)
    except (RuntimeError, OSError) as error:
        module.fail_json(msg=f"DNS reservation verification failed: {error}")
    else:
        module.exit_json(changed=False)


if __name__ == "__main__":
    main()
