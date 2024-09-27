#!/bin/bash

# Check if a commit message is provided
if [ -z "$1" ]; then
  echo "Please provide a commit message."
  exit 1
fi

# Add all changes to staging
git add .

# Commit with the provided message
git commit -m "$1"

# Push the changes
git push
