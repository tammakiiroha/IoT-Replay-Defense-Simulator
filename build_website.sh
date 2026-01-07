#!/bin/bash

# Stop on error
set -e

echo "🚀 Building Static Website for Deployment..."

cd web

# 1. Install dependencies
echo "📦 Installing dependencies..."
npm install

# 2. Build static export
echo "🏗️  Building project..."
npm run build

echo ""
echo "✅ Build Successful!"
echo "📂 The website files are in: $(pwd)/out"
echo ""
echo "👉 How to publish:"
echo "   Option 1: Drag the 'web/out' folder to https://app.netlify.com/drop"
echo "   Option 2: Push this code to GitHub and enable GitHub Pages."
echo ""

# Open the folder in Finder
open out
