# MinMin OS quick start

[Tiếng Việt](QUICKSTART.md) · [English](QUICKSTART.en.md)

## Windows PC

Install Python 3.12 and Node.js LTS. Download and extract the ZIP from [MinMin's repository](https://github.com/haincbbg-coder/minminos). Open CMD in the folder containing `install.ps1`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

Open `http://localhost:7777`. Use `start-minmin.bat` on later visits and `stop-minmin.bat` to stop. Restart after installing additional CLI tools.

## Hostinger

In **Docker Manager → Compose → URL**, paste:

```text
https://raw.githubusercontent.com/haincbbg-coder/minminos/main/docker-compose.minmin.hostinger.yml
```

Set your `DOMAIN_NAME`, `MINMIN_ADMIN_USER` and `MINMIN_ADMIN_PASSWORD` before deploying. Configure DNS and HTTPS; see [deployment instructions](DEPLOY.en.md).

## VPS with Docker

On a VPS with Git, Docker and Docker Compose:

```bash
git clone https://github.com/haincbbg-coder/minminos.git /opt/minminos
cd /opt/minminos
cp .env.minmin.example .env
nano .env
```

Replace the example password, then start:

```bash
docker compose -f docker-compose.minmin.yml up -d --pull always
```

Open `http://<VPS-IP>:7777`. Set up HTTPS before connecting service accounts.

## First setup and maintenance

Connect your AI provider in **Models**, shop accounts in **Connections**, and choose **Skills** and **Agents**. See the [user guide](docs/en/README.md).

Back up data before updating. Docker installations must retain the Compose file and project they were created with. For the new configuration above, repeat the `up -d --pull always` command. Never use `down -v` for updates.

On Windows, use `stop-minmin.bat` then `start-minmin.bat` to restart and check `server/minmin.log` for errors. ZIP installations require a backup and data-migration check before replacing the old folder. Refresh with Ctrl + F5 after updating.
