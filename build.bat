@echo off
echo y | plink -ssh -pw 248640 root@129.211.28.47 "cd /root/opsbrain/oobm-topology && docker compose build nginx 2>&1 | tail -30"
