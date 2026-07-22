#!/bin/bash

# Define log file path
LOGFILE="/home/ubuntu/OSS_Agile_Lab/exp_1_scheduling/system_monitor.log"

echo "--- System Status: $(date) ---" >> "$LOGFILE"
echo "Disk Usage: " >> "$LOGFILE"
df -h / >> "$LOGFILE"
echo "Memory Usage: " >> "$LOGFILE"
free -h >> "$LOGFILE"
echo "---------------------------------" >> "$LOGFILE"
echo "" >> "$LOGFILE"