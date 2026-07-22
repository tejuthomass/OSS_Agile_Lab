#!/bin/bash

# Navigate to the root of the workspace
cd /home/ubuntu/OSS_Agile_Lab

# Add the scheduling folder to staging (captures logs, backups, and scripts)
git add exp_1_scheduling/

# Commit the changes with a dynamic timestamp
git commit -m "Automated log update: $(date)"