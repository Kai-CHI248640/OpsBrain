import paramiko, sys, time

HOST = "129.211.28.47"
USER = "root"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting...")
client.connect(HOST, 22, USER, "248640", timeout=20, allow_agent=False, look_for_keys=False)
print("Building nginx...")

ch = client.get_transport().open_session(timeout=600)
ch.exec_command("cd /root/opsbrain/oobm-topology && docker compose build nginx --no-cache 2>&1")
ch.settimeout(600)
while True:
    if ch.recv_ready():
        sys.stdout.write(ch.recv(4096).decode(errors="replace"))
        sys.stdout.flush()
    if ch.exit_status_ready():
        break
    time.sleep(0.3)
while ch.recv_ready():
    sys.stdout.write(ch.recv(4096).decode(errors="replace"))
ec = ch.recv_exit_status()
print(f"\n-> exit: {ec}")

if ec == 0:
    print("Restarting nginx...")
    client.exec_command("cd /root/opsbrain/oobm-topology && docker compose up -d nginx 2>&1", timeout=60)
    time.sleep(5)

import http.client
conn = http.client.HTTPConnection("129.211.28.47", 80, timeout=15)
conn.request("GET", "/opsbrain/")
r = conn.getresponse()
data = r.read().decode()[:200]
print(f"\nFrontend: {r.status}")
print(f"Body: {data[:100]}...")
conn.close()
client.close()
print("Done!")
