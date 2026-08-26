#!/bin/bash
# Collects system metrics in CSV format for trend analysis.
# Columns: timestamp,disk_used_pct,mem_used_pct,load_1min,proc_count

WORKSPACE="/home/ubuntu/OSS_Agile_Lab/exp_5_miniproject"
CSV="$WORKSPACE/metrics.csv"

# Write header only if the file does not yet exist
if [ ! -f "$CSV" ]; then
    echo "timestamp,disk_used_pct,mem_used_pct,load_1min,proc_count" > "$CSV"
fi

TIMESTAMP=$(date +%Y-%m-%dT%H:%M:%S)
DISK_PCT=$(df / | awk 'NR==2 {gsub("%",""); print $5}')
MEM_PCT=$(free | awk '/Mem:/ {printf "%.1f", $3/$2 * 100}')
LOAD_1=$(awk '{print $1}' /proc/loadavg)
PROC_COUNT=$(ps -e --no-headers | wc -l)

echo "$TIMESTAMP,$DISK_PCT,$MEM_PCT,$LOAD_1,$PROC_COUNT" >> "$CSV"
echo "Metrics collected at $TIMESTAMP"