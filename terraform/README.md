# Rapidly Infrastructure as Code (IaC)

We use [Terraform](https://developer.hashicorp.com/terraform) to provision and
manage Rapidly's production infrastructure on [Hetzner Cloud](https://www.hetzner.com/cloud).

State, secrets and runs are managed on
[HCP Terraform Cloud](https://app.terraform.io/app/rapidly-tech/workspaces/rapidly).

## Infrastructure overview

| Component        | Resource                                         | Notes                                              |
|------------------|--------------------------------------------------|----------------------------------------------------|
| Compute          | `hcloud_server.app`                              | Runs the Docker stack from `deploy/hetzner/`       |
| PostgreSQL       | `hcloud_server.database` + `hcloud_volume.pgdata` | Persistent volume mounted at `/var/lib/postgresql` |
| Redis            | `hcloud_server.cache`                            | In-memory broker / cache                           |
| Private network  | `hcloud_network.rapidly` + `hcloud_network_subnet.private` | All servers attached, services bind to private IPs |
| Firewalls        | `hcloud_firewall.app/db/cache`                   | Public surface limited to SSH from trusted IPs     |
| SSH key          | `hcloud_ssh_key.deploy`                          | Used by GitHub Actions to deploy                   |
| Cloudflare DNS   | (managed in Cloudflare dashboard)                | A records point to the app server's public IP      |
| Object storage   | Cloudflare R2                                    | S3-compatible, accessed via the app code           |
| Ingress          | Cloudflare Tunnel (cloudflared)                  | Runs as a systemd service on the app server        |

## Layout

```
terraform/
├── main.tf            # Provider configuration
├── versions.tf        # Required Terraform / provider versions
├── variables.tf       # Input variables
├── outputs.tf         # Output values
├── network.tf         # Private network and subnet
├── firewall.tf        # Firewall rules per role
├── ssh.tf             # SSH key registered with Hetzner
├── app.tf             # Application server
├── database.tf        # Postgres server + volume
└── cache.tf           # Redis server
```

## HCP Terraform Cloud

The infrastructure is divided into a workspace per environment:

```
Projects:
├── prod
├── sandbox
└── test
```

The Hetzner API token (`hcloud_token`) and SSH public key
(`ssh_public_key`) are configured as workspace variables — the token must be
marked **sensitive**.

## Adding environment variables for the application

Application secrets (database URL, Stripe keys, etc.) live in
`/opt/rapidly/.env.production` on the app server, **not** in Terraform.
Terraform provisions infrastructure; the runtime configuration is rolled out
by the deploy workflow (`.github/workflows/deploy-hetzner.yml`).

If you need to add a new infrastructure-level variable (e.g. server type,
location, firewall rule), declare it in `variables.tf` and set the value in
the HCP Terraform Cloud workspace as a **Terraform Variable**.

## Local commands

```bash
cd terraform
terraform init
terraform fmt -recursive
terraform validate
terraform plan
```

CI runs `terraform fmt -check -recursive -diff` and `tflint --recursive` on
every PR — see `.github/workflows/terraform.yaml`.
