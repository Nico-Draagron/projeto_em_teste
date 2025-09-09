#!/bin/bash
# backend/scripts/setup_complete.sh

echo "🚀 WeatherBiz Analytics - Complete Backend Setup"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1 completed successfully${NC}"
    else
        echo -e "${RED}❌ $1 failed${NC}"
        exit 1
    fi
}

# 1. Navigate to backend directory
cd backend || exit

# 2. Create virtual environment
echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
python -m venv venv
source venv/bin/activate
check_status "Virtual environment creation"

# 3. Upgrade pip
echo -e "${YELLOW}📦 Upgrading pip...${NC}"
pip install --upgrade pip
check_status "Pip upgrade"

# 4. Install dependencies
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
pip install -r requirements.txt
check_status "Dependencies installation"

# 5. Create necessary directories
echo -e "${YELLOW}📁 Creating directory structure...${NC}"
mkdir -p app/tasks
mkdir -p app/schemas
mkdir -p exports
mkdir -p logs
mkdir -p ml_models
check_status "Directory structure creation"

# 6. Initialize Alembic
echo -e "${YELLOW}🗄️ Initializing Alembic...${NC}"
if [ ! -d "alembic" ]; then
    alembic init alembic
    # Copy our env.py over the default
    cp scripts/alembic_env.py alembic/env.py
    check_status "Alembic initialization"
else
    echo -e "${GREEN}✅ Alembic already initialized${NC}"
fi

# 7. Run initial migration
echo -e "${YELLOW}🗄️ Running database migrations...${NC}"
alembic upgrade head
check_status "Database migrations"

# 8. Setup environment variables
echo -e "${YELLOW}⚙️ Setting up environment variables...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}📝 Please edit .env file with your configuration${NC}"
else
    echo -e "${GREEN}✅ .env file already exists${NC}"
fi

# 9. Start Redis (if Docker is available)
if command -v docker &> /dev/null; then
    echo -e "${YELLOW}🐳 Starting Redis with Docker...${NC}"
    docker run -d --name redis-weatherbiz -p 6379:6379 redis:7-alpine
    check_status "Redis startup"
else
    echo -e "${YELLOW}⚠️ Docker not found. Please install Redis manually${NC}"
fi

# 10. Run tests
echo -e "${YELLOW}🧪 Running tests...${NC}"
pytest tests/ -v --tb=short
test_status=$?
if [ $test_status -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed${NC}"
else
    echo -e "${YELLOW}⚠️ Some tests failed (this might be expected if external services are not configured)${NC}"
fi

echo ""
echo -e "${GREEN}✨ Setup completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys and configuration"
echo "2. Start the FastAPI server: uvicorn app.main:app --reload"
echo "3. Start Celery worker: celery -A app.tasks worker --loglevel=info"
echo "4. Start Celery beat: celery -A app.tasks beat --loglevel=info"
echo "5. Access API documentation: http://localhost:8000/docs"