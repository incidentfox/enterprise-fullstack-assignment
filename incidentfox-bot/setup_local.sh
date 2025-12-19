#!/bin/bash
# Local setup script for IncidentFox + Coolify integration

set -e

echo "🦊 IncidentFox + Coolify Local Setup"
echo "====================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker Desktop.${NC}"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.11+.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites met${NC}"
echo ""

# Check .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
    echo "Creating from .env.example..."
    cp .env.example .env
    echo -e "${RED}Please edit .env with your credentials before continuing!${NC}"
    echo ""
    echo "Required values:"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - GITHUB_APP_ID"
    echo "  - GITHUB_INSTALLATION_ID"
    echo "  - GITHUB_WEBHOOK_SECRET"
    echo "  - GITHUB_APP_PRIVATE_KEY_PATH (save private-key.pem in this directory)"
    echo ""
    read -p "Press Enter when .env is configured..."
fi

# Verify critical env vars
source .env

if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "sk-ant-your-anthropic-key-here" ]; then
    echo -e "${RED}❌ ANTHROPIC_API_KEY not set in .env${NC}"
    exit 1
fi

if [ -z "$GITHUB_APP_ID" ] || [ "$GITHUB_APP_ID" = "your_app_id_here" ]; then
    echo -e "${RED}❌ GITHUB_APP_ID not set in .env${NC}"
    exit 1
fi

if [ ! -f "$GITHUB_APP_PRIVATE_KEY_PATH" ]; then
    echo -e "${RED}❌ GitHub private key not found at: $GITHUB_APP_PRIVATE_KEY_PATH${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Configuration validated${NC}"
echo ""

# Set up Python environment
echo "📦 Setting up Python environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

source venv/bin/activate

echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Start database
echo "🗄️  Starting PostgreSQL..."
docker-compose up -d postgres

# Wait for database to be ready
echo "⏳ Waiting for database..."
sleep 5

# Check if database is ready
until docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done

echo -e "${GREEN}✅ Database ready${NC}"
echo ""

# Run migrations
echo "🔄 Running database migrations..."
if command -v alembic &> /dev/null; then
    alembic upgrade head
    echo -e "${GREEN}✅ Migrations complete${NC}"
else
    echo -e "${YELLOW}⚠️  Alembic not found, skipping migrations${NC}"
fi
echo ""

# Start IncidentFox
echo "🦊 Starting IncidentFox bot..."
echo ""
echo -e "${GREEN}=== IncidentFox is starting ===${NC}"
echo ""
echo "The bot will be available at: http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Next steps:"
echo "  1. Set up Coolify (see ../COOLIFY_LOCAL_SETUP.md)"
echo "  2. Configure Coolify webhooks to point to:"
echo "     http://host.docker.internal:8000/webhooks/coolify"
echo "  3. Create a test PR with a deliberate bug"
echo "  4. Watch IncidentFox analyze and fix it!"
echo ""
echo "To test without Coolify:"
echo "  python simulate_webhook.py --scenario missing-env-var --pr 123"
echo ""
echo -e "${GREEN}Press Ctrl+C to stop${NC}"
echo ""

# Start the bot
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
