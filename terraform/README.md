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

## Relationship to production

> **Important:** the live production Hetzner stack was provisioned
> **manually** before this terraform tree existed. The code in this
> directory describes the *intended* shape of the infrastructure but has
> **not** been `terraform apply`d against the running production servers.
> Running `terraform apply` today will create a **parallel** set of
> Hetzner resources sitting alongside the existing production (duplicate
> servers, duplicate network, duplicate volume). It will not touch or
> reconfigure the live stack.

### Path A: create parallel infrastructure via CI

This is what the one-shot `.github/workflows/terraform-apply.yml` workflow
implements. It runs `terraform init && terraform apply` in a GitHub Actions
runner using two repo secrets. Use it when you want a blank new stack for
staging, DR rehearsal, or eventual migration.

**Before you click "Run workflow":**

1. Create a Hetzner Cloud API token with read+write scope in the
   [Hetzner Cloud Console](https://console.hetzner.cloud) under
   *Project → Security → API Tokens*. Add it to this repo as secret
   `HCLOUD_TOKEN` (Settings → Secrets and variables → Actions).
2. Add your SSH public key (the `ssh-ed25519 AAAA... user@host` line, not
   the path or the private half) as secret `HETZNER_SSH_PUBLIC_KEY`.
3. Trigger the workflow manually: Actions → *Terraform Apply (Hetzner)* →
   *Run workflow*. You must type `apply-for-real` into the `confirm`
   input field or the workflow refuses to run.
4. Watch the Terraform plan output, confirm the created resources match
   what you expected, and download the `terraform-state-<run-id>` artifact
   at the end of the run. **Keep that state file safe** — without it,
   terraform forgets about the resources and you'd have to `terraform
   import` each one back.

**Estimated monthly cost of a Path A apply with default server types:**

| Resource         | Type           | Price      |
|------------------|----------------|------------|
| `hcloud_server.app`       | `ccx23`        | ~€28/mo    |
| `hcloud_server.database`  | `ccx13`        | ~€14/mo    |
| `hcloud_server.cache`     | `cx22`         | ~€4/mo     |
| `hcloud_volume.pgdata`    | 100 GB         | ~€4/mo     |
| Network + firewalls + SSH | (free)         | €0         |
| **Total**        |                | **~€50/mo** |

**Path A does NOT migrate production.** After a successful apply you still
have to: dump postgres from the old database server, restore it on the new
one, copy `/opt/rapidly/.env.production` and `docker-compose.production.yml`
to the new app server, install `cloudflared` there, update the `HETZNER_HOST`
GitHub secret, and decommission the old servers from the Hetzner dashboard.

### Path B: adopt existing infrastructure via `terraform import`

The safer long-term approach. Use `terraform import` (or the declarative
`import { ... }` blocks introduced in Terraform 1.5+) to tell terraform
about the existing manually-provisioned resources, then iteratively fix
drift between the HCL and the live state until `terraform plan` says
"no changes". Requires knowing the Hetzner resource IDs of the current
production stack — grab them from the Hetzner Cloud console or via the
`hcloud` CLI.

This path is not yet scripted. When you're ready, ask for import blocks
to be scaffolded and a `dev/fetch-hetzner-ids.sh` helper written.

### Path C: delete the terraform tree

If IaC discipline is not a priority, delete `terraform/` and
`.github/workflows/terraform.yaml` entirely and document the manual
Hetzner setup in `DEPLOYMENT.md` instead.
