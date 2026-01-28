#!/bin/bash
# Deploy to production - automated deployment script

set -e

echo "================================"
echo "ARROW LIMOUSINE CLOUD DEPLOYMENT"
echo "================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Validate GitHub
echo -e "\n${YELLOW}Step 1: Checking Git status...${NC}"
if [ -z "$(git status -s)" ]; then
    echo -e "${GREEN}✓ Working directory clean${NC}"
else
    echo -e "${RED}✗ Uncommitted changes detected!${NC}"
    echo "Run: git add . && git commit -m 'Deploy changes'"
    exit 1
fi

# Step 2: Check backends
echo -e "\n${YELLOW}Step 2: Verifying backend...${NC}"
if [ -f "modern_backend/requirements.txt" ]; then
    echo -e "${GREEN}✓ requirements.txt found${NC}"
else
    echo -e "${RED}✗ requirements.txt missing${NC}"
    echo "Run: pip freeze > modern_backend/requirements.txt"
    exit 1
fi

if [ -f "modern_backend/Procfile" ]; then
    echo -e "${GREEN}✓ Procfile found${NC}"
else
    echo -e "${RED}✗ Procfile missing${NC}"
    exit 1
fi

# Step 3: Check frontend
echo -e "\n${YELLOW}Step 3: Verifying frontend...${NC}"
if [ -f "frontend/package.json" ]; then
    echo -e "${GREEN}✓ package.json found${NC}"
else
    echo -e "${RED}✗ package.json missing${NC}"
    exit 1
fi

if [ -f "frontend/netlify.toml" ]; then
    echo -e "${GREEN}✓ netlify.toml found${NC}"
else
    echo -e "${RED}✗ netlify.toml missing${NC}"
    exit 1
fi

# Step 4: Push to GitHub
echo -e "\n${YELLOW}Step 4: Pushing to GitHub...${NC}"
git push origin main
echo -e "${GREEN}✓ Code pushed to GitHub${NC}"

# Step 5: Display next steps
echo -e "\n${YELLOW}Step 5: Deployment Instructions${NC}"
echo ""
echo "Backend (Render):"
echo "  1. Go to https://render.com/dashboard"
echo "  2. Create new Web Service"
echo "  3. Connect GitHub repo"
echo "  4. Base directory: modern_backend"
echo "  5. Start command: uvicorn app.main:app --host 0.0.0.0 --port \$PORT"
echo "  6. Set environment variables from Neon"
echo "  7. Deploy!"
echo ""
echo "Frontend (Netlify):"
echo "  1. Go to https://netlify.com/team/sites"
echo "  2. New site from Git"
echo "  3. Connect GitHub repo"
echo "  4. Base directory: frontend"
echo "  5. Build: npm run build"
echo "  6. Deploy!"
echo ""
echo "Database (Neon):"
echo "  1. Create project at https://neon.tech"
echo "  2. Get connection string"
echo "  3. Restore backup: pg_restore -h <neon> almsdata.dump"
echo ""
echo -e "${GREEN}✓ Deployment ready!${NC}"
