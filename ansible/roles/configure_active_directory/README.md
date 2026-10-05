# Role: configure_active_directory

Prepares Active Directory for a new customer deployment: customer OU, security groups, agent and deployer users, and the computer objects of the new VMs. It runs on the domain controller (inventory group `domain_controllers`, host `dc01`) over WinRM and uses the `microsoft.ad` collection (`ansible/requirements.yml`).

## What it does

`tasks/main.yml` includes four task files in this order:

| Order | File | Behaviour |
|---|---|---|
| 1 | `ou.yml` | Creates the OU `ad_info.ad_ou` under `ad_customers_ou` (`microsoft.ad.ou`), protected from accidental deletion, with the description `ad_info.ad_desc` (company name) |
| 2 | `groups.yml` | Creates every group in `ad_info.groups` inside the customer OU, using the given scope, category and description |
| 3 | `users.yml` | Looks up existing users by `sAMAccountName`, then creates or updates every user in `ad_info.users` and adds them to their groups (details below) |
| 4 | `computer.yml` | For each VM in `vms`: sets the computer description to `ad_info.ad_ou` and moves the object into the customer OU; then adds `<hostname>$` to the group `<OU>Computers` |

### Users (`users.yml`)

- Created in `OU=<item.ou>,<ad_customers_ou>`: the agent in the customer OU, the deployer in `OU=Deploy`.
- Attributes: UPN `<username>@<ad_info.domain>`, display name, first name (first word of the full name), surname (the rest), company, e-mail, description `<Role> of <OU>`, telephone number, enabled.
- Group membership comes from `item.groups` (added, never removed).
- Password: set from `local_admin_password` **only on creation** (`update_password: on_create`).
- "User must change password at next logon" is set **only for newly created users** (`password_expired` is omitted for users found by the lookup), so re-runs do not reset it.

## Requirements

- WinRM from the runner to the domain controller (`AD_SERVER`) with `AD_ANSIBLE_USER` / `AD_ANSIBLE_PASSWORD` (GitLab variables read by the generated inventory).
- That account can create OUs, groups and users under `OU=Customers,DC=cloud,DC=local` and modify computer objects.
- Collections from `ansible/requirements.yml` (already in the `tap` image).
- **Must already exist** in AD (the role does not create them): `OU=Customers`, `OU=Deploy,OU=Customers` (when a deployer is requested), and the groups `ADSelfServiceEnrollment` and `DeployMembers`.
- The Windows computer objects exist before `computer.yml` runs: Terraform joins Windows VMs to the domain during guest customization. Linux VMs are not joined.

## Variables

### Role defaults (`defaults/main.yml`)

| Variable | Default | Meaning |
|---|---|---|
| `ad_customers_ou` | `OU=Customers,DC=cloud,DC=local` | Parent OU of all customers |
| `ad_customer_ou` | `OU={{ ad_info.ad_ou }},{{ ad_customers_ou }}` | Distinguished name of this customer's OU |

### Variables supplied from outside

| Variable | Source | Meaning |
|---|---|---|
| `ad_info` | `vms.tfvars.json` (`-e "@../vms.tfvars.json"`) | See below |
| `vms` | `vms.tfvars.json` | Map of VMs keyed by hostname; only the keys are used here |
| `local_admin_password` | **TODO** confirm (probably set in the playbook from `LOCAL_ADMIN_PASSWORD`) | Initial password of new AD users |

`ad_info` keys:

| Key | Meaning |
|---|---|
| `ad_ou` | Customer OU name (VM base name for new customers, ticket `ad_ou` field otherwise) |
| `ad_desc` | Description (company name) |
| `domain` | AD domain, used for the UPN |
| `users[]` | `role` (`agent` or `deployer`), `username` (national ID), `full_name`, `email`, `phone`, `company`, `ou`, `groups[]` |
| `groups[]` | `name`, `description`, `scope`, `category` |

### Group naming convention

| Group | Purpose |
|---|---|
| `<OU>Deploy` | Deployers of the customer (local administrators on its VMs) |
| `<OU>Support` | Support staff of the customer (local administrators) |
| `<OU>Members` | Customer members (Remote Desktop access on its VMs) |
| `<OU>Computers` | Computer objects of the customer |
| `<OU><hostname>Members` | Per-VM administrators group (created empty, managed manually) |

## Usage

Run from the `ansible/` directory (this is what the `2_configure_ad` CI job does):

```bash
ansible-playbook -i inventory/hosts.yml \
  playbooks/configure_active_directory.yml \
  -e "@../vms.tfvars.json"
```

Playbook sketch (**TODO** replace with the real playbook):

```yaml
- hosts: domain_controllers
  gather_facts: false
  roles:
    - configure_active_directory
```

## Idempotency

- OU, groups and computer objects use `state: present`, so re-runs make no change.
- Users are only created once; password and "must change password" are applied on creation only.
- The CI job retries twice on failure, which relies on the points above.

## Known gaps

- `ad_customers_ou` hard-codes `DC=cloud,DC=local`; derive it from `ad_info.domain`.
- `local_admin_password` is also the local administrator password of every Windows VM. Use a random per-user initial password instead, and add `no_log: true` to the password-handling task.
- `computer.yml` loops over every VM in `vms`, including Linux VMs, so it can create stray computer objects for them (verify); filter on `os_type == 'windows'`.
- A user whose national ID already exists in another customer OU may be moved by the `path` parameter (verify).
- A missing prerequisite OU or group makes the run fail; consider a pre-check task listing them.