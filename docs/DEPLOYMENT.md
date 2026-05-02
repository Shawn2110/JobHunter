# JobHunt — Deployment

JobHunt is single-user, single-tenant, BYO-keys. There is no
"production cluster" — the deployment paths below are about getting
a personal instance running where you can reach it.

The three paths ranked by complexity:

1. **Local-only** (default, recommended for v1).
2. **Oracle Cloud Free Tier + Cloudflare Tunnel + Access**
   (free forever, requires ARM-aware Docker setup).
3. **Hetzner CX22 + Coolify** (~₹400/month, near-zero-friction
   redeploys).

For *running* the app once deployed, see [SETUP.md](SETUP.md).

---

## 1. Local-only

If your laptop or desktop is on whenever you're job hunting, run
JobHunt right there. `docker compose up`, visit `localhost:3000`,
done. The backend binds to `127.0.0.1` only — nothing exposed.

Cost: ₹0. Limitations: only available while the machine is on,
only accessible from that machine.

## 2. Oracle Cloud Free Tier (free forever)

Oracle's Always-Free tier offers a 4 vCPU / 24GB RAM ARM Ampere
instance — many times what JobHunt needs.

### Provision

1. Sign up at oracle.com/cloud/free.
2. Create a "VM.Standard.A1.Flex" (Ampere ARM) instance:
   - 2 OCPUs, 12GB RAM (well inside the free quota)
   - Ubuntu 22.04 ARM image
3. Allow your SSH key.
4. SSH in and install Docker:

   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
   sudo usermod -aG docker $USER && newgrp docker
   ```

### Deploy

```bash
git clone https://github.com/Shawn2110/JobHunter.git
cd JobHunter
cp .env.example .env
# Edit .env — fill in your keys, set BIND_PUBLIC=1
nano .env
```

Set:
```
BIND_PUBLIC=1
FRONTEND_ORIGIN=https://jobhunt.your-domain.com
NEXT_PUBLIC_API_BASE_URL=https://jobhunt.your-domain.com/api
```

```bash
docker compose up -d
```

The ARM-base images we depend on (python:3.12-slim, node:22-alpine)
are multi-arch — no special flags needed.

### Expose via Cloudflare Tunnel + Access

Tunnel handles ingress without opening firewall ports; Access gates
the URL to your email only.

1. Install cloudflared on the VM:

   ```bash
   curl -L --output cloudflared.deb \
     https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
   sudo dpkg -i cloudflared.deb
   ```

2. Authenticate and create a tunnel:

   ```bash
   cloudflared tunnel login
   cloudflared tunnel create jobhunt
   ```

3. Configure `~/.cloudflared/config.yml`:

   ```yaml
   tunnel: <tunnel-id>
   credentials-file: /home/ubuntu/.cloudflared/<tunnel-id>.json
   ingress:
     - hostname: jobhunt.your-domain.com
       service: http://localhost:3000
     - service: http_status:404
   ```

4. Route DNS:

   ```bash
   cloudflared tunnel route dns jobhunt jobhunt.your-domain.com
   sudo cloudflared service install
   ```

5. In the Cloudflare dashboard:
   - Zero Trust → Access → Applications → Add Application
   - Type: Self-hosted
   - Subdomain: jobhunt
   - Policy: Email = your address only

That's it — `https://jobhunt.your-domain.com` is now gated to your
email and reachable from anywhere. Cost: ₹0.

### Updates

```bash
ssh ubuntu@<vm>
cd JobHunter
git pull && docker compose up --build -d
```

## 3. Hetzner CX22 + Coolify (~₹400/month)

If Oracle's signup process or the ARM nuance doesn't appeal, Hetzner
CX22 is the cheapest reliable paid option.

### Provision

1. Sign up at hetzner.com/cloud, create a project.
2. Add a server: location EU (closest to India is Falkenstein/
   Nuremberg), CX22 (2 vCPU, 4GB RAM, 40GB SSD), Ubuntu 22.04.
3. Add your SSH key.

### Install Coolify

```bash
ssh root@<server>
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Visit `http://<server>:8000`, finish the Coolify setup wizard.

### Deploy via Coolify

1. New Resource → Public Repository → paste GitHub URL.
2. Build pack: Docker Compose.
3. Set environment variables (paste from your `.env`).
4. Set `BIND_PUBLIC=1`.
5. Add a domain in Coolify; it will provision Let's Encrypt automatically.

Push to GitHub → Coolify rebuilds and redeploys.

Cost: ~₹400/mo Hetzner + your domain. EU latency to India is
100-150ms — fine for a non-realtime app.

## 4. Home server / always-on Pi

Same shape as the Oracle path, on hardware you already own:

```bash
docker compose up -d
# install cloudflared, set up tunnel + access as above
```

Cost: electricity only.

## 5. What's explicitly not recommended

- **Vercel + Railway + managed Postgres.** The architecture is
  built around single-tenant local SQLite. Splitting into managed
  services adds cost, complexity, multi-region data residency
  questions, and platform lock-in for capabilities the system
  doesn't need.
- **Public deployment without access gating.** The system has no
  auth (single-user trust model). Exposing without Cloudflare Access
  (or equivalent) means anyone who finds the URL can run searches
  that consume your Claude budget.

## 6. Backup

The whole user dataset is `data/jobhunt.db` plus `data/resumes/`.
Back them up with whatever you already use. From the running app:

```bash
curl http://localhost:8000/admin/export > $(date +%F).json
```

## 7. Rollback

```bash
git checkout <previous-tag-or-sha>
docker compose up --build -d
```

Migrations are forward-only by default. If a downgrade is needed:

```bash
docker compose exec backend python -m alembic downgrade -1
```

(Verify the specific migration's `downgrade()` is implemented before
relying on this — see `backend/migrations/versions/`.)
