#!/usr/bin/env bash

zip -r company-brain-submission.zip cursor-hackathon-2026-company-brain-rag-and-knowledge-graph/ \
  --exclude "*/node_modules/*" \
  --exclude "*/.venv/*" \
  --exclude "*/.git/*" \
  --exclude "*/__pycache__/*" \
  --exclude "*/dist/*" \
  --exclude "*/build/*" \
  --exclude "*/.next/*" \
  --exclude "*/.env" \
  --exclude "*/.env.*"