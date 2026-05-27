#!/usr/bin/env python3
"""Build and start OpsBrain services on remote server."""
import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("129.211.28.47", 22, "root", "248640", allow_agent=False, look_for_keys=False)


def run(cmd, timeout=120):
    """Run command and print output."""
    print(f"$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out[-1500:])
    if err:
        print(f"[STDERR] {err[-500:]}")
    if exit_code != 0:
        print(f"[EXIT] {exit_code}")
    print()
    return out, err, exit_code


# Step 1: Build nginx (includes Vue frontend build)
print("=" * 60)
print("STEP 1: Building nginx with frontend")
print("=" * 60)
run(
    "cd /root/opsbrain/oobm-topology && docker compose build --no-cache nginx 2>&1",
    timeout=600
)

# Step 2: Build web backend
print("=" * 60)
print("STEP 2: Building web backend")
print("=" * 60)
run(
    "cd /root/opsbrain/oobm-topology && docker compose build --no-cache web 2>&1",
    timeout=600
)

# Step 3: Start services
print("=" * 60)
print("STEP 3: Starting services")
print("=" * 60)
run("cd /root/opsbrain/oobm-topology && docker compose up -d nginx web 2>&1", timeout=30)

# Step 4: Verify
print("=" * 60)
print("STEP 4: Verification")
print("=" * 60)
time.sleep(3)
run('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"')

run("curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://localhost/opsbrain/")

run("curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://localhost/opsbrain/api/v1/auth/setup-required")

print("=" * 60)
print("DONE - Access at: http://129.211.28.47/opsbrain/")
print("=" * 60)

client.close()
