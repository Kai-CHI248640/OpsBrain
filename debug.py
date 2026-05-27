"""Debug nginx and verify deployment."""
import paramiko, time, sys

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("129.211.28.47", 22, "root", "248640", allow_agent=False, look_for_keys=False)

def run(cmd, wait=5):
    chan = client.get_transport().open_session()
    chan.exec_command(cmd)
    time.sleep(wait)
    out = chan.recv(65536).decode(errors="replace")
    err = chan.recv_stderr(4096).decode(errors="replace") if chan.recv_stderr_ready() else ""
    sys.stdout.write(out)
    if err: sys.stdout.write(err)
    sys.stdout.flush()

print("=== Nginx logs ===\n")
run("docker logs opsbrain-nginx --tail 30 2>&1", wait=3)

print("\n=== Web logs ===\n")
run("docker logs opsbrain-web --tail 20 2>&1", wait=3)

print("\n=== Direct backend test ===\n")
run("curl -s http://localhost:8000/api/v1/auth/setup-required", wait=3)

print("\n=== Check DNS resolution inside nginx ===\n")
run("docker exec opsbrain-nginx sh -c 'getent hosts web' 2>&1 || echo 'getent failed'", wait=3)
run("docker exec opsbrain-nginx sh -c 'nslookup web' 2>&1 || echo 'nslookup failed'", wait=3)

client.close()
