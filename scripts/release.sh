#!/bin/bash
set -e

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting manual release for wash-alpha ===${NC}"

# 1. Fetch tags and identify latest
echo -e "${BLUE}Fetching latest tags from origin...${NC}"
git fetch --tags origin master

LATEST_TAG=$(git tag --sort=-v:refname | head -n 1)

if [ -z "$LATEST_TAG" ]; then
    echo -e "${RED}Error: No tags found in the repository.${NC}"
    exit 1
fi

echo -e "${GREEN}Latest tag found: ${LATEST_TAG}${NC}"

# 2. Confirm release
echo -e "${BLUE}Ready to release ${LATEST_TAG} to PyPI? (y/n)${NC}"
read -r response
if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo -e "${RED}Release cancelled.${NC}"
    exit 1
fi

# 3. Checkout the tag
echo -e "${BLUE}Checking out ${LATEST_TAG}...${NC}"
git checkout "$LATEST_TAG"

# 4. Ensure hatch is available
if ! command -v hatch &> /dev/null; then
    echo -e "${BLUE}hatch not found. Installing...${NC}"
    pip install hatch
fi

# 5. Build distributions
echo -e "${BLUE}Cleaning dist/ and building distributions...${NC}"
rm -rf dist/
hatch build

# 6. Publish to PyPI
echo -e "${BLUE}Publishing to PyPI...${NC}"
echo -e "${BLUE}Note: You will be prompted for your PyPI credentials unless configured in ~/.pypirc or via environment variables.${NC}"
hatch publish

echo -e "${GREEN}=== Release of ${LATEST_TAG} complete! ===${NC}"

# 7. Return to master
echo -e "${BLUE}Returning to master branch...${NC}"
git checkout master
