# DEMO: Full-Stack Engineer Take-Home Assignment

Welcome to the Chartmetric Full-Stack Engineer take-home assignment! This repository contains a complete development environment for you to demonstrate your full-stack engineering skills.

## Environment Overview

The environment includes:

- **Frontend**: NextJS application running on port 3000
- **Backend**: NodeJS/Express API running on port 5000
- **Database**: PostgreSQL database running on port 5432 (pre-loaded with music industry data)

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

- Frontend: http://localhost:3000
- Backend: http://localhost:5001
- Database: Available on localhost:5432
  - Username: postgres
  - Password: postgres
  - Database: chartmetric

## Database Schema

The database contains a schema called `chartmetric` with tables storing music industry data.
You can explore the database schema using:

```bash
make shell-db
```

Then, inside the PostgreSQL shell:

```sql
\dt chartmetric.*
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
make shell-frontend  # Open a shell in the frontend container
make shell-backend   # Open a shell in the backend container
make shell-db        # Open a PostgreSQL shell to the database
make reset           # Reset all containers (fresh start)
make help            # Show help information
```

## Assignment Task

1. Understand the pre-made database schema

   - Explore the database using `make shell-db`

2. Build backend API endpoints
3. Create a frontend interface following the instructions in the handed documentation.

## Contact

If you have any questions or need assistance, please contact enterprise@chartmetric.com
