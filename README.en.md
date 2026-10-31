# MinMin OS

MinMin OS is a self-hosted AI assistant for your PC or VPS. Connect your shop data, use skills and agents, maintain a private knowledge base, and choose an AI provider for your work.

**[Tiếng Việt](README.md) · [English](README.en.md)**

## Installation

### Windows PC

Install Python 3.12 and Node.js LTS from their official websites. Download this repository using **Code → Download ZIP**, extract it, and open CMD in the folder containing `install.ps1`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

Open [http://localhost:7777](http://localhost:7777). On later visits, run `start-minmin.bat`; stop with `stop-minmin.bat`. Restart MinMin after installing additional CLI tools.

### Hostinger Docker Manager

Choose **VPS → Docker Manager → Compose → URL** and paste:

```text
https://raw.githubusercontent.com/haincbbg-coder/minminos/main/docker-compose.minmin.hostinger.yml
```

Set the environment values before deploying:

```dotenv
DOMAIN_NAME=minmin.example.com
MINMIN_ADMIN_USER=admin
MINMIN_ADMIN_PASSWORD=ReplaceWithYourOwnPassword
```

Point DNS to the VPS, deploy, and open `https://<DOMAIN_NAME>`. Without a domain, use `http://<VPS-IP>:7777` temporarily. Configure HTTPS before entering service credentials. Optional: `MINMIN_AUTO_UPDATE=true` enables daily update checks.

### Linux VPS with Docker

Install Git, Docker and Docker Compose, then:

```bash
git clone https://github.com/haincbbg-coder/minminos.git /opt/minminos
cd /opt/minminos
cp .env.minmin.example .env
nano .env
```

Set your own admin password, then start:

```bash
docker compose -f docker-compose.minmin.yml up -d --pull always
docker compose -f docker-compose.minmin.yml ps
```

Open `http://<VPS-IP>:7777`. See [deployment instructions](DEPLOY.en.md) for HTTPS and updates. Existing installations must keep using their current Compose file until their volumes and migration are checked.

### Native Linux or macOS

```bash
chmod +x install.sh
./install.sh
```

Follow the installer output and open `http://localhost:7777`.

## First setup

Connect an AI provider in **Models**, add your shop accounts in **Connections**, and select or customize **Skills** and **Agents**. Each customer supplies their own accounts. Some applications require a separate license, and AI usage is billed by the chosen provider.

MinMin provides chat and voice, memory and wiki, a knowledge graph, skills, agents, workflows, recurring work, business connections, file management, sessions, usage tracking and backups. See the [user guide](docs/en/README.md).

## Updates and troubleshooting

For a new Docker installation following this guide:

```bash
docker compose -f docker-compose.minmin.yml up -d --pull always
docker compose -f docker-compose.minmin.yml logs --tail=80
```

Back up configuration, brains and customer data first. Never use `docker compose down -v` as an update command: it deletes data volumes. ZIP installations do not automatically support Git updates; use a separate folder for the new version until data migration is verified.

On Windows, check `server/minmin.log`; restart CMD after installing Python or Node.js. Refresh the dashboard with **Ctrl + F5** after updating. Do not share passwords, keys or customer brains in support screenshots.

## Documentation and license

- [Quick start](QUICKSTART.en.md)
- [VPS and Hostinger deployment](DEPLOY.en.md)
- [User guide](docs/en/README.md)
- [MIT license and copyright notice](LICENSE)
