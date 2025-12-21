# Coolify Setup (Optional)

This guide shows a generic way to deploy this repo with Coolify using the included `docker-compose.yaml`.

## 1) Install / access Coolify

- **Local**: run Coolify via Docker (see Coolify’s official docs)
- **Cloud**: use a hosted Coolify instance

## 2) Connect your Git repository

In the Coolify UI:

1. Go to **Settings** → **Sources**
2. Add your Git provider (GitHub/GitLab/etc.)
3. Grant access to your fork of this repo

## 3) Create an application from Docker Compose

1. Go to **Applications** → **New Application**
2. Choose **Docker Compose**
3. Select this repository
4. Set **Docker Compose File** to `docker-compose.yaml`

## 4) Environment variables

The compose file already sets sane defaults. If you want to override them in Coolify, common ones are:

```
# Web -> API (inside the compose network)
NEXT_PUBLIC_API_URL=http://api:5000

# DB
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=app
```

## 5) Deploy

Trigger a deploy from Coolify. After it’s up:

- Web: port **3000**
- API: port **5000** (published as **5001** externally by default compose)

