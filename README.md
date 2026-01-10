# Full-Stack Starter (Next.js + Express + Postgres)

Forked from a public Chartmetric take-home assignment repository as a demo baseline (credit to Chartmetric for the original scaffold).

## Environment Overview

The environment includes:

- **Web**: Next.js application running on port 3000
- **API**: Node.js/Express API running on port 5000
- **DB**: PostgreSQL database running on port 5432

## Prerequisites

Make sure you have the following installed on your system:

- Docker
- Docker Compose
- Make

## Getting Started

To start the development environment, simply run:

```bash
make
```

This command will:

1. Pull the necessary Docker images
2. Start all the services
3. Make the application available on your local machine

Once started, you can access:

- Web: http://localhost:3000
- API: http://localhost:5001
- Database: Available on localhost:5432
  - Username: postgres
  - Password: postgres
  - Database: app

## Database Schema

The database is initialized with a small sample table so the stack works out of the box.
You can explore the database schema using:

```bash
make shell-db
```

Then, inside the PostgreSQL shell:

```sql
\dt
```

For more details on the schema, refer to the [DATABASE.md](DATABASE.md) file.

## Available Commands

```bash
make          # Pull images and start all services
make pull     # Pull the latest Docker images
make start    # Start all services
make stop     # Stop all services
make clean    # Stop services and remove containers/volumes
make logs     # View logs from all services
make shell-web       # Open a shell in the web container
make shell-api       # Open a shell in the api container
make shell-frontend  # Alias for shell-web
make shell-backend   # Alias for shell-api
make shell-db        # Open a PostgreSQL shell to the database
make reset           # Reset all containers (fresh start)
make help            # Show help information
```

## What to Customize First

1. Update the sample API route in `backend/routes/index.js` and the DB query in `backend/models/model.js`
2. Replace the sample UI in `frontend/components/Home/Home.tsx`
