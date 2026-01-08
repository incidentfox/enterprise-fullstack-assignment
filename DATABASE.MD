# Database Documentation

This document describes the default PostgreSQL setup for this starter repo.

## Connection Information

- **Host**: localhost (or `db` from within containers)
- **Port**: 5432
- **Database**: app
- **Username**: postgres
- **Password**: postgres

Connect to the database using:

```bash
make shell-db
```

Or use your preferred PostgreSQL client with the connection details above.

## Schema Overview

By default, the database is initialized with a small sample table so the API has something to read.

## Tables (default)

### records

Generic sample records returned by the demo API endpoint.

| Column     | Type        | Description                           |
| ---------- | ----------- | ------------------------------------- |
| id         | SERIAL      | Primary key                           |
| name       | TEXT        | Display name                          |
| created_at | TIMESTAMPTZ | Record creation time (default: now()) |

## Database Management

### Reset the Database

If you need to reset the database to its initial state:

```bash
make reset
```

### Explore Database Structure

```sql
-- List all tables
\dt

-- Show detailed information about a table
\d records

-- Show all schemas
\dn

-- List all tables in all schemas
\dt *.*
```
