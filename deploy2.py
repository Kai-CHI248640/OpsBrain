"""Build and deploy (fast channel approach)."""
import paramiko, time, sys, os

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("129.211.28.47", 22, "root", "248640", allow_agent=False, look_for_keys=False)

# Upload files
sftp = client.open_sftp()
local_base = r"C:\Users\zhang\.openclaw\workspace\projects\opsbrain\web\frontend\src"
for local_rel in ["views/TopologyDetail.vue", "components/AgentPanel.vue"]:
    local = os.path.join(local_base, local_rel)
    remote_dir = f"/root/opsbrain/web/frontend/src/{os.path.dirname(local_rel)}"
    stdin, stdout, stderr = client.exec_command(f"mkdir -p {remote_dir}", timeout=5)
    stdout.channel.recv_exit_status()
    with open(local, "rb") as f:
        content = f.read()
    with sftp.open(f"/root/opsbrain/web/frontend/src/{local_rel}", "w") as f:
        f.write(content)
    print(f"[OK] {local_rel} ({len(content)}b)")
sftp.close()

# Build web backend with direct exec_command approach
print("\n=== Build web backend ===")
stdin, stdout, stderr = client.exec_command(
    "cd /root/opsbrain/oobm-topology && docker compose build web 2>&1",
    timeout=300
)
exit_code = stdout.channel.recv_exit_status()
out = stdout.read().decode()
print(out[-1500:])
print(f"exit: {exit_code}")

# Build nginx
print("\n=== Build nginx ===")
stdin, stdout, stderr = client.exec_command(
    "cd /root/opsbrain/oobm-topology && docker compose build nginx 2>&1",
    timeout=180
)
exit_code = stdout.channel.recv_exit_status()
out = stdout.read().decode()
print(out[-800:])
print(f"exit: {exit_code}")

# Restart
print("\n=== Restart ===")
stdin, stdout, stderr = client.exec_command(
    "cd /root/opsbrain/oobm-topology && docker compose down && docker compose up -d nginx web 2>&1",
    timeout=30
)
stdout.channel.recv_exit_status()
time.sleep(8)

# Status
stdin, stdout, stderr = client.exec_command(
    "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'NAMES|opsbrain'",
    timeout=10
)
print(stdout.read().decode())

client.close()
print("\nDone")
