#!/bin/bash

# Define paths explicitly
WORKSPACE="/home/ubuntu/OSS_Agile_Lab/exp_1_scheduling"
LOGFILE="$WORKSPACE/system_monitor.log"
BACKUP_FILE="$WORKSPACE/log_backup_$(date +%s).tar.gz"

# 1. Compress the log file
tar -czf "$BACKUP_FILE" "$LOGFILE"

# 2. Empty the original log file so it starts fresh
> "$LOGFILE"

# 3. Delete backups older than 1 day (1440 minutes) to save space
find "$WORKSPACE" -name "log_backup_*.tar.gz" -type f -mmin +1440 -exec rm {} \;

echo "Backup created and old files cleaned up."