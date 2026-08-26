#!/bin/bash
# Rule-based threshold detection. Exits 1 if any critical threshold is breached,
# which allows CI to treat it as a failure condition.

CSV="/home/ubuntu/OSS_Agile_Lab/exp_5_miniproject/metrics.csv"
DISK_LIMIT=80
MEM_LIMIT=90
BREACH=0

if [ ! -f "$CSV" ]; then
    echo "ERROR: metrics.csv not found."
    exit 1
fi

# Read the most recent data row
LAST=$(tail -n 1 "$CSV")
DISK=$(echo "$LAST" | cut -d',' -f2)
MEM=$(echo "$LAST" | cut -d',' -f3)

echo "Latest reading -> disk: ${DISK}%, memory: ${MEM}%"

if [ "$DISK" -ge "$DISK_LIMIT" ]; then
    echo "CRITICAL: Disk usage ${DISK}% has reached the ${DISK_LIMIT}% threshold."
    BREACH=1
fi

# Compare memory as a float using awk
if awk -v m="$MEM" -v l="$MEM_LIMIT" 'BEGIN{exit !(m>=l)}'; then
    echo "CRITICAL: Memory usage ${MEM}% has reached the ${MEM_LIMIT}% threshold."
    BREACH=1
fi

if [ "$BREACH" -eq 0 ]; then
    echo "OK: All metrics within acceptable thresholds."
fi

exit $BREACH