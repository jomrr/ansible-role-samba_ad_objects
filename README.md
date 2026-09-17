# Ansible Role: samba_ad_objects

![GitHub](https://img.shields.io/github/license/jomrr/ansible-role-samba_ad_objects)
![GitHub last commit](https://img.shields.io/github/last-commit/jomrr/ansible-role-samba_ad_objects)
![GitHub issues](https://img.shields.io/github/issues-raw/jomrr/ansible-role-samba_ad_objects)
[![dev](https://img.shields.io/github/actions/workflow/status/jomrr/ansible-role-samba_ad_objects/dev.yml?branch=dev&label=dev)](https://github.com/jomrr/ansible-role-samba_ad_objects/actions/workflows/dev.yml?query=branch%3Adev)
[![main](https://img.shields.io/github/actions/workflow/status/jomrr/ansible-role-samba_ad_objects/main.yml?branch=main&label=main)](https://github.com/jomrr/ansible-role-samba_ad_objects/actions/workflows/main.yml?query=branch%3Amain)

Ansible role for managing Samba AD users, groups, organizational units, and DNS
reservations.

## Scope

### Managed

- Reserved DNS names.
- Domain users, organizational units, groups, and additive or authoritative
  group memberships.

### Not Managed

- DC installation, provisioning, joins, and service configuration.
- Windows LAPS schema and delegation.
- Domain password policies and Password Settings Objects (PSOs).

## Requirements

- An existing Samba AD domain with working DNS and Kerberos discovery.
- Native Samba Python bindings for the interpreter executing the role.
- Administrator credentials supplied through Ansible Vault or another secret
  store.
- RFC2307 enabled in the domain when managing POSIX attributes.

## Dependencies

```yaml
collections:
  - name: community.general
    version: '>=12.0.0'
  - name: jomrr.samba
    version: '>=1.0.1'
```

## Role Variables

### `samba_ad_objects_server`

Type: `str`. Required: `true`.

DNS hostname of the existing Samba AD domain controller.

### `samba_ad_objects_realm`

Type: `str`. Required: `true`.

Kerberos realm of the existing domain.

### `samba_ad_objects_admin_password`

Type: `str`. Required: `true`.

Administrator password for directory operations, supplied through a secret
store.

### `samba_ad_objects_dns_reserved_names`

Type: `list`. Required: `false`.

DNS names reserved with administrator-owned loopback A records; an empty list
stops management.

Default:

```yaml
samba_ad_objects_dns_reserved_names:
  - wpad
  - isatap
```

### `samba_ad_objects_ous`

Type: `list`. Required: `false`.

Organizational units in parent-before-child order; deletion uses reverse order
and requires empty OUs.

Default:

```yaml
samba_ad_objects_ous: []
```

### `samba_ad_objects_users`

Type: `list`. Required: `false`.

Domain user accounts; omitted entries are left unmanaged.

Default:

```yaml
samba_ad_objects_users: []
```

### `samba_ad_objects_groups`

Type: `list`. Required: `false`.

Domain groups and optional memberships; all groups are created before resolving
nested memberships.

Default:

```yaml
samba_ad_objects_groups: []
```

### `samba_ad_objects_user_update_password`

Type: `str`. Required: `false`.

User password update policy; always intentionally changes passwords on every
run. Overridable per user.

Default:

```yaml
samba_ad_objects_user_update_password: on_create
```

### `samba_ad_objects_group_members_purge`

Type: `bool`. Required: `false`.

Remove unlisted group members when members is supplied; overridable per group.

Default:

```yaml
samba_ad_objects_group_members_purge: false
```

## Check Mode

Check mode previews changes to an existing domain.

## Security Notes

- The role reserves wpad and isatap as administrator-owned A records pointing to
  127.0.0.1. Configure samba_ad_objects_dns_reserved_names to select the names;
  removing a name stops management and preserves the record. Existing record
  ownership and ACLs are not changed.

## Operational Notes

- Directory operations authenticate as Administrator using
  samba_ad_objects_admin_password against samba_ad_objects_server. Run the role
  once per domain; AD replicates the resulting changes to other DCs.
- samba_ad_objects_ous, samba_ad_objects_users, and samba_ad_objects_groups
  manage only listed objects. Removing an item stops management; state: absent
  explicitly deletes it. List OUs in parent-before-child order. Empty OUs marked
  absent are removed in reverse order after users and groups are managed. OU
  deletion never removes unlisted child objects recursively.
- All groups are created before membership is reconciled, so nested groups may
  appear in any order. Omitted members leaves membership unmanaged.
  samba_ad_objects_group_members_purge defaults to false (additive); true makes
  a supplied members list authoritative. Each group may override members_purge.
  An empty members list removes all members only in authoritative mode.
- New users require a password supplied through a secret store.
  samba_ad_objects_user_update_password defaults to on_create and may be
  overridden per user with update_password. always deliberately resets a
  supplied password on every run and is not idempotent. Optional user and group
  attributes remain unchanged when omitted, except enabled, scope, category, and
  location, which use the documented module defaults. Omitted path places or
  moves users and groups to the default Users container.

## Supported Platforms

| OS Family | Distribution | Version | Container Image |
| --------- | ------------ | ------- | --------------- |
| RedHat | AlmaLinux | latest | [jomrr/molecule-almalinux:latest](https://hub.docker.com/r/jomrr/molecule-almalinux) |
| Debian | Debian | latest | [jomrr/molecule-debian:latest](https://hub.docker.com/r/jomrr/molecule-debian) |
| RedHat | Fedora | latest | [jomrr/molecule-fedora:latest](https://hub.docker.com/r/jomrr/molecule-fedora) |
| Suse | OpenSuse Tumbleweed | latest | [jomrr/molecule-opensuse-tumbleweed:latest](https://hub.docker.com/r/jomrr/molecule-opensuse-tumbleweed) |
| Debian | Ubuntu | latest | [jomrr/molecule-ubuntu:latest](https://hub.docker.com/r/jomrr/molecule-ubuntu) |

## Example Playbook

### Manage an existing domain

```yaml
---

- name: SAMBA_AD_OBJECTS | Manage directory objects
  hosts: dc1
  gather_facts: false
  roles:
    - role: jomrr.samba_ad_objects
      samba_ad_objects_server: dc1.ad.example.com
      samba_ad_objects_realm: AD.EXAMPLE.COM
      samba_ad_objects_admin_password: "{{ vault_samba_ad_admin_password }}"

```

### Manage directory objects

Group entries support `name`, `path`, `scope`, `category`, `description`,
`gid_number`, `members`, `members_purge`, and `state`. `scope` accepts
`global` (default), `domain_local`, or `universal`; `category` accepts
`security` (default) or `distribution`. All user and OU object options are
exposed in the role argument schema as well. Directory operations use
Administrator and `samba_ad_objects_admin_password` against the configured DC.

```yaml
samba_ad_objects_ous:
  - name: Staff
    path: DC=ad,DC=example,DC=com
  - name: Engineering
    path: OU=Staff,DC=ad,DC=example,DC=com
samba_ad_objects_users:
  - username: jdoe
    path: OU=Engineering,OU=Staff,DC=ad,DC=example,DC=com
    given_name: Jane
    surname: Doe
    password: "{{ vault_jdoe_password }}"
samba_ad_objects_groups:
  - name: engineers
    path: OU=Engineering,OU=Staff,DC=ad,DC=example,DC=com
    members: [jdoe]
  - name: announcements
    scope: universal
    category: distribution
    members: [engineers]
```

## References

- [jomrr.samba collection](https://github.com/jomrr/ansible-collection-samba)

## Author

[Jonas Mauer](https://github.com/jomrr)

## License

This project is licensed under the MIT License.
See [LICENSE](LICENSE) for the full license text.

Copyright (c) 2026 Jonas Mauer.
