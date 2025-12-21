# Frontend Service

This is the web UI for the starter repo, built with Next.js and TypeScript.

## Tech Stack

- **Next.js 13.4** - React framework with server-side rendering
- **TypeScript** - Type-safe JavaScript
- **SASS** - CSS preprocessor for styling
- **React 18.2** - UI library

## Setup

```bash
# Install dependencies
yarn install

# Start development server
yarn dev

# Build for production
yarn build

# Start production server
yarn start

# Run linting
yarn lint
```

## Project Structure

```
frontend/
├── components/          # Reusable React components
│   └── Home/           # Home page specific components
├── pages/              # Next.js pages
│   ├── _app.tsx       # App entry point
│   └── index.tsx      # Home page
├── styles/            # Global styles and SASS modules
│   └── globals.scss   # Global SASS styles
├── utils/             # Utility functions
│   └── api.ts        # API client configuration
└── public/           # Static assets
```

## Environment Variables

Create a `.env.local` file in the root directory with these variables:

```env
NEXT_PUBLIC_API_URL=http://localhost:5001  # API URL
```

## Development Guidelines

### Components

- Use TypeScript interfaces for prop types
- Create components in the `components/` directory
- Use SASS modules for component-specific styles
- Follow the naming convention: `ComponentName.tsx` and `ComponentName.module.scss`

## Building for Production

```bash
# Build the application
yarn build

# Start the production server
yarn start
```

The production build will be created in the `.next` directory.

## Docker Support

The application includes a Dockerfile for containerized deployment. Build and run with:

```bash
# Build the image
docker build -t starter-web .

# Run the container
docker run -p 3000:3000 starter-web
```
