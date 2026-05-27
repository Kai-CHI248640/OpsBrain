"""Build web backend and start services."""
import paramiko, time, sys

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("129.211.28.47", 22, "root", "248640", allow_agent=False, look_for_keys=False)


def run(cmd, timeout=120):
    sys.stdout.write(f">>> {cmd[:80]}...\n")
    sys.stdout.flush()
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    start = time.time()
    buf = ""
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode(errors="replace")
            buf += data
            sys.stdout.write(data)
            sys.stdout.flush()
        elif chan.exit_status_ready():
            break
        elif time.time() - start > timeout:
            break
        time.sleep(0.5)
    exit_code = chan.recv_exit_status()
    sys.stdout.write(f"[exit: {exit_code}]\n")
    sys.stdout.flush()
    return buf, exit_code


# Build web backend
print("\n=== BUILDING WEB BACKEND ===\n")
run("cd /root/opsbrain/oobm-topology && docker compose build web 2>&1", timeout=600)

# Start services
print("\n=== STARTING SERVICES ===\n")
run("cd /root/opsbrain/oobm-topology && docker compose up -d nginx web 2>&1", timeout=30)

time.sleep(3)

# Verify
print("\n=== VERIFICATION ===\n")
run('docker ps --format "table {{.Names}}\t{{.Status}}"', timeout=10)
run("curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://localhost/opsbrain/", timeout=10)
run("curl -s http://localhost/opsbrain/api/v1/auth/setup-required", timeout=10)

client.close()
print("\nDONE")
