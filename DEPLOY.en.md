# Deploy MinMin OS on a VPS

[Tiếng Việt](DEPLOY.md) · [English](DEPLOY.en.md)

This guide creates a new installation. Back up existing installations and retain their Compose file, project name and volumes when updating.

## Requirements

Use a Linux VPS with Git, Docker Engine and Docker Compose. Install Docker using its [official instructions](https://docs.docker.com/engine/install/ubuntu/). The application image is `ghcr.io/haincbbg-coder/minminos:latest`; a separate Python or Node.js installation is not required on the host.

## Hostinger Docker Manager

Choose **VPS → Docker Manager → Compose → URL** and paste:

```text
https://raw.githubusercontent.com/haincbbg-coder/minminos/main/docker-compose.minmin.hostinger.yml
```

Set these Environment values before deploying:

```dotenv
DOMAIN_NAME=minmin.example.com
MINMIN_ADMIN_USER=admin
MINMIN_ADMIN_PASSWORD=ReplaceWithYourOwnPassword
```

Point your domain DNS to the VPS, deploy, and open `https://<DOMAIN_NAME>`. Without a domain, temporarily use `http://<VPS-IP>:7777`. Set up HTTPS before entering service credentials.

For another installation on the same VPS, create a separate stack/project and use different `MINMIN_NAME`, `MINMIN_HOST_PORT` and `DOMAIN_NAME` values. Projects must have separate data volumes.

## Docker Compose over SSH

```bash
ssh root@VPS-IP
git clone https://github.com/haincbbg-coder/minminos.git /opt/minminos
cd /opt/minminos
cp .env.minmin.example .env
nano .env
```

Set a private admin password of at least eight characters:

```dotenv
MINMIN_NAME=minminos
MINMIN_HOST_PORT=7777
MINMIN_ADMIN_USER=admin
MINMIN_ADMIN_PASSWORD=ReplaceWithYourOwnPassword
```

Save, then start:

```bash
chmod 600 .env
docker compose -f docker-compose.minmin.yml up -d --pull always
docker compose -f docker-compose.minmin.yml ps
```

Open `http://<VPS-IP>:7777`. Allow time for startup. Check the VPS provider's TCP 7777 rules and application logs if it is unavailable:

```bash
docker compose -f docker-compose.minmin.yml logs --tail=80
```

## Domains and HTTPS

Hostinger uses the Traefik labels in its dedicated Compose file. On other VPS providers, configure a Caddy or Nginx HTTPS reverse proxy to `127.0.0.1:7777`, then set `MINMIN_BIND=127.0.0.1`. Configure the proxy before restricting the bind address.

## First setup and updates

Sign in with the admin account you configured. Connect your AI provider in **Models**, shop accounts in **Connections**, then select **Skills** and **Agents**.

For a new installation following this guide:

```bash
cd /opt/minminos
docker compose -f docker-compose.minmin.yml up -d --pull always
```

On Hostinger, use the application update action when its updater is available, or redeploy the same stack. Optional `MINMIN_AUTO_UPDATE=true` enables daily checks. It is off by default to avoid unexpected restarts during work.

Existing installations must use their existing Compose file and project. Switching project names or deployment files can create empty volumes instead of loading existing data.

## Backups and access

Back up application data, brains, credentials and encryption keys before upgrades or migration. Do not use `docker compose down -v` for updates: it deletes volumes. Keep `.env`, secrets and customer data out of public repositories and support screenshots.

If image pulls return `unauthorized` or `denied`, check the visibility and permissions of **GitHub → Packages → minminos**. Repository and container-package visibility are separate settings.

See [Quick start](QUICKSTART.en.md), the [user guide](docs/en/README.md) and the [license](LICENSE).
