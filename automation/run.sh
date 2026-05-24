#!/bin/bash
# MIMO 100T Form Automation - Cron wrapper
cd /root/mimo-devflow
/usr/local/bin/python3 automation/cron_runner.py 2>&1
echo "---EXIT CODE: $?---"
