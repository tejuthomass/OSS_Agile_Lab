#!/bin/bash
# Comments on an issue automatically once a scheduled job completes
gh issue comment 1 --repo tejuthomass/OSS_Agile_Lab \
    --body "Automated run confirmed: monitor.sh executed successfully at $(date)."