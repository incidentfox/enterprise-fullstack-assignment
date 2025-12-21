#!/bin/bash
# Quick test script for IncidentFox - Tests analysis engine without infrastructure

set -e

echo "🦊 IncidentFox Quick Test"
echo "========================="
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating one now..."
    echo ""

    # Prompt for API key
    read -p "Enter your Anthropic API key (sk-ant-...): " ANTHROPIC_KEY

    if [ -z "$ANTHROPIC_KEY" ]; then
        echo "❌ API key is required. Exiting."
        exit 1
    fi

    # Create minimal .env
    cat > .env << EOF
# Minimal config for offline testing
ANTHROPIC_API_KEY=$ANTHROPIC_KEY
LOG_LEVEL=INFO

# Optional: Add these later for full functionality
# GITHUB_APP_ID=
# GITHUB_INSTALLATION_ID=
# GITHUB_WEBHOOK_SECRET=
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/incidentfox
EOF

    echo "✅ Created .env file"
    echo ""
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
    echo ""
fi

# Activate venv
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Run tests
echo "🧪 Running test scenarios..."
echo "================================"
echo ""

echo "Test 1: Missing Environment Variable"
echo "-------------------------------------"
python test_runner.py --scenario missing-env-var
echo ""
echo "Press Enter to continue to next test..."
read

echo ""
echo "Test 2: Port Mismatch"
echo "-------------------------------------"
python test_runner.py --scenario port-mismatch
echo ""
echo "Press Enter to continue to next test..."
read

echo ""
echo "Test 3: Build Failure"
echo "-------------------------------------"
python test_runner.py --scenario build-failure
echo ""
echo "Press Enter to continue to next test..."
read

echo ""
echo "Test 4: Runtime Crash"
echo "-------------------------------------"
python test_runner.py --scenario runtime-crash
echo ""

echo "================================"
echo "✅ All tests completed!"
echo ""
echo "Next steps:"
echo "  1. Review the analysis results above"
echo "  2. Check TESTING_GUIDE.md for full bot testing"
echo "  3. See README.md for deployment options"
echo ""
