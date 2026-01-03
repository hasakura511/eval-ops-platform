#!/bin/bash

echo "🚀 Setting up Eval Ops Platform..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f backend/.env ]; then
    echo "📝 Creating .env file..."
    cp backend/.env.example backend/.env
    echo "✅ Created backend/.env (edit if needed)"
fi

# Start services
echo "🐳 Starting Docker services..."
docker compose up -d

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 10

# Run migrations
echo "🗄️  Running database migrations..."
docker compose exec -T backend python -c "
from app.models.database import Base
from app.core.database import engine

Base.metadata.create_all(bind=engine)
print('✅ Database tables created')
"

# Create initial workspace
echo "🏗️  Creating initial workspace..."
docker compose exec -T backend python -c "
from app.models.database import Organization, Workspace
from app.core.database import SessionLocal
import uuid

db = SessionLocal()

# Create org
org = Organization(id='org-default', name='Default Organization')
db.add(org)

# Create workspace
workspace = Workspace(
    id='ws-default',
    organization_id='org-default',
    name='Default Workspace'
)
db.add(workspace)

db.commit()
print('✅ Created default organization and workspace')
"

echo ""
echo "✨ Setup complete!"
echo ""
echo "🌐 Services:"
echo "   API:      http://localhost:8000"
echo "   Docs:     http://localhost:8000/docs"
echo "   Database: postgresql://postgres:postgres@localhost:5432/evalops"
echo ""
echo "📖 Next steps:"
echo "   1. Visit http://localhost:8000/docs to explore the API"
echo "   2. Try compiling a workflow: POST /api/v1/workflows/compile"
echo "   3. Check the README.md for detailed usage examples"
echo ""