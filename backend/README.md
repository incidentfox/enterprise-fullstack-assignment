# Backend Service

This is the API service for the starter repo. It provides a small REST API backed by PostgreSQL.

## Setup

```bash
# Install dependencies
npm install

# Start the service
npm start

# Start in development mode (with hot reload)
npm run dev
```

## Environment Variables

The service can be configured using the following environment variables:

```env
DB_HOST=db              # PostgreSQL host (default: 'db')
DB_PORT=5432           # PostgreSQL port (default: 5432)
DB_USER=postgres       # PostgreSQL user (default: 'postgres')
DB_PASSWORD=postgres   # PostgreSQL password (default: 'postgres')
DB_NAME=app            # PostgreSQL database name (default: 'app')
```

## Database Functions

The `db.js` module provides several utility functions for database operations:

### query(text, params)

Execute a SQL query with optional parameters.

```javascript
const { query } = require('./db');

// Example: Get recent records
const getRecentRecords = async (limit = 10) => {
  const text = 'SELECT * FROM records ORDER BY id DESC LIMIT $1';
  const params = [limit];
  const result = await query(text, params);
  return result.rows;
};
```

### ping()

Check database connectivity.

```javascript
const { ping } = require('./db');

// Example: Health check endpoint
app.get('/health', async (req, res) => {
  try {
    await ping();
    res.json({ status: 'healthy' });
  } catch (err) {
    res.status(500).json({ status: 'unhealthy', error: err.message });
  }
});
```

### transaction(callback)

Execute multiple queries within a transaction. The callback receives a client instance to run queries.

```javascript
const { transaction } = require('./db');

// Example: Insert a record in a transaction
const insertRecord = async (name) => {
  await transaction(async (client) => {
    await client.query(
      'INSERT INTO records (name) VALUES ($1)',
      [name]
    );
  });
};
```

## API Routes

The API routes are organized in the `routes` directory. Each route module exports an Express router with its endpoints.
