"""Build and start OpsBrain services with China-optimized sources."""
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
            buf += "\n[TIMEOUT]"
            break
        time.sleep(0.3)
    exit_code = chan.recv_exit_status()
    sys.stdout.write(f"[exit: {exit_code}]\n")
    sys.stdout.flush()
    return buf, exit_code

# 1. Add PyPI mirror to web backend Dockerfile
print("=== UPDATING DOCKERFILE WITH CHINA MIRRORS ===\n")
sftp = client.open_sftp()
backend_df = (
    "FROM python:3.12-slim\n\n"
    # Use Tencent apt mirror for faster apt in China
    'RUN sed -i "s@deb.debian.org@mirrors.tencent.com@g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || true\n'
    'RUN sed -i "s@security.debian.org@mirrors.tencent.com@g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || true\n'
    'RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends tini curl && rm -rf /var/lib/apt/lists/*\n\n'
    "WORKDIR /app\n"
    "COPY backend/requirements.txt .\n"
    # Use Tencent PyPI mirror
    'RUN pip install --no-cache-dir -i https://mirrors.tencent.com/pypi/simple/ -r requirements.txt\n\n'
    "COPY backend/app/ ./app/\n\n"
    'ENV OPSBRAIN_HOME=/var/lib/opsbrain\n\n'
    'RUN groupadd --gid 1001 opsbrain && useradd --uid 1001 --gid 1001 --create-home --shell /sbin/nologin opsbrain && mkdir -p ${OPSBRAIN_HOME} && chown -R opsbrain:opsbrain /app ${OPSBRAIN_HOME}\n\n'
    "USER opsbrain\n"
    "EXPOSE 8000\n"
    'ENTRYPOINT ["/usr/bin/tini", "--"]\n'
    'CMD ["uvicorn", "app.__init__:app", "--host", "0.0.0.0", "--port", "8000"]\n'
)
with sftp.open("/root/opsbrain/web/backend/Dockerfile", "w") as f:
    f.write(backend_df.encode())
sftp.close()
print("  Dockerfile updated with China mirrors\n")

# 2. Build web backend
print("=== BUILDING WEB BACKEND ===\n")
run("cd /root/opsbrain/oobm-topology && docker compose build web 2>&1", timeout=600)

# 3. Start services
print("\n=== STARTING SERVICES ===\n")
run("cd /root/opsbrain/oobm-topology && docker compose up -d nginx web 2>&1", timeout=30)

time.sleep(3)

# 4. Verify
print("\n=== VERIFICATION ===\n")
run('docker ps --format "table {{.Names}}\t{{.Status}}"', timeout=10)
run("curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://localhost/opsbrain/", timeout=10)

client.close()
print("\n=== DONE ===")
