# Role: configure_windows_client

Configures newly created Windows VMs: local group membership and the Zabbix Agent 2. It runs against the inventory group `windows_clients` over WinRM.

## What it does

`tasks/main.yml` includes:

| Order | File | Behaviour | State |
|---|---|---|---|
| 1 | `local_groups.yml` | Adds the AD groups in `admin_groups` to local **Administrators** and the groups in `rdp_groups` to **Remote Desktop Users** (`ansible.windows.win_group_membership`) | Active |
| 2 | `zabbix_agent2.yml` | Installs or upgrades Zabbix Agent 2 and deploys the agent configuration (steps below) | Active |
| 3 | `splunk_forwarder.yml` | Splunk Forwarder service restart | **Disabled**: commented out in `main.yml` |

### Zabbix Agent 2 steps

1. Download the MSI from Nexus to the Ansible controller (`/tmp/zabbix_agent2.msi`, once per run, `validate_certs: false`).
2. Create `agent2_temp_dir` on the VM and copy the MSI to it.
3. Install it silently with `win_package` (`/qn /norestart`).
4. Copy `files/zabbix/config_files/<zabbix_server>/zabbix_agent2.conf` to the install directory.
5. Set the `Zabbix Agent 2` service to automatic and restart it.
6. Print the last 20 lines of `zabbix_agent2.log`.
7. Remove the MSI from the VM.

## Requirements

- WinRM access to the VM with `WINDOWS_ANSIBLE_USER` / `WINDOWS_ANSIBLE_PASSWORD` (from the generated inventory).
- The VM is domain joined and the AD groups already exist (created by `configure_active_directory`), plus the shared group `Server_Administrators`.
- The runner can download from `https://vnk-nexus.abramad.com/repository/zabbix-cdn/...`.
- The host variable `zabbix_server` is set in the inventory (copied from `vms.<name>.zabbix_server`). It must be `vnk-customerzabbix` or `me-customerzabbix`.

## Variables (`defaults/main.yml`)

| Variable | Default                                                                       | Meaning                                               |
|---|-------------------------------------------------------------------------------|-------------------------------------------------------|
| `admin_groups` | `<OU>Deploy`, `<OU>Support`, `Server_Administrators`, `<OU><hostname>Members` | Domain groups added to local **Administrators**       |
| `rdp_groups` | `<OU>Members`                                                                 | Domain groups added to local **Remote Desktop Users** |
| `agent2_version` | `ZABBIX_AGENT2_VERSION`                                                       | Zabbix Agent 2 version taken from Gitlab CI variables |
| `agent2_download_url` | Nexus `zabbix-cdn` MSI URL built from `agent2_version`                        | Download location                                     |
| `agent2_temp_dir` | `C:\Temp\zabbix_agent2`                                                       | Temporary folder on the VM                            |
| `agent2_install_dir` | `C:\Program Files\Zabbix Agent 2`                                             | Installation folder                                   |

`<OU>` is `ad_info.ad_ou` and `<hostname>` is `inventory_hostname`; both come from `vms.tfvars.json` (`-e "@../vms.tfvars.json"`). The group names match the ones created by `configure_active_directory`.

## Agent configuration files

| Folder (`files/zabbix/config_files/`) | `zabbix_server` value | Used for |
|---|---|---|
| `vnk-customerzabbix/zabbix_agent2.conf` | `vnk-customerzabbix` | Vanak customer Zabbix |
| `me-customerzabbix/zabbix_agent2.conf` | `me-customerzabbix` | Miremad customer Zabbix |

The same file is copied to every VM of that datacenter.

## Usage

Run from the `ansible/` directory (this is what the `3_configure_windows` CI job does):

```bash
ansible-playbook -i inventory/hosts.yml \
  playbooks/configure_windows_client.yml \
  -e "@../vms.tfvars.json"
```

## Idempotency

- Group membership tasks make no change on re-runs.
- The Zabbix part always downloads, copies, restarts the service and removes the MSI, so it reports changes on every run.
