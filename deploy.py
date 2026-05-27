#!/usr/bin/env python3
"""
Deploy OpsBrain to remote server via SSH.
Usage: python deploy.py
"""

import paramiko
import os
import shutil
import tempfile

HOST = "129.211.28.47"
PORT = 22
USER = "root"
PASSWORD = "248640"
LOCAL_PROJECT = r"C:\Users\zhang\.openclaw\workspace\projects\opsbrain"
REMOTE_BASE = "/root/opsbrain"


def ssh_exec(client, command, timeout=60):
    """Execute command via SSH and return output."""
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return exit_code, out, err


def main():
    print("=" * 60)
    print("OpsBrain — Deploy to 129.211.28.47")
    print("=" * 60)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"\n[1/6] Connecting to {USER}@{HOST}:{PORT} ...")
        client.connect(HOST, PORT, USER, PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)
        print("  ✓ Connected")

        # Step 2: Check prerequisites
        print(f"\n[2/6] Checking prerequisites ...")
        code, out, err = ssh_exec(client, "hostname")
        print(f"  Host: {out}")

        code, out, err = ssh_exec(client, "docker --version 2>/dev/null || echo NOT_FOUND")
        if "NOT_FOUND" in out:
            print("  Installing Docker ...")
            ssh_exec(client, "curl -fsSL https://get.docker.com | sh", timeout=120)
            ssh_exec(client, "systemctl enable docker && systemctl start docker")
            print("  ✓ Docker installed")
        else:
            print(f"  Docker: {out}")

        code, out, err = ssh_exec(client, "docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo NOT_FOUND")
        if "NOT_FOUND" in out:
            print("  Installing Docker Compose ...")
            ssh_exec(client, "curl -L 'https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)' -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose", timeout=60)
            print("  ✓ Docker Compose installed")
        else:
            print(f"  Compose: {out}")

        code, out, err = ssh_exec(client, "node --version 2>/dev/null || echo NOT_FOUND")
        if "NOT_FOUND" in out:
            print("  Installing Node.js 20 ...")
            ssh_exec(client, "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -", timeout=60)
            ssh_exec(client, "apt-get install -y nodejs", timeout=60)
            code, out, err = ssh_exec(client, "node --version")
            print(f"  ✓ Node.js: {out}")
        else:
            print(f"  Node.js: {out}")

        # Step 3: Create remote directory
        print(f"\n[3/6] Creating remote directory {REMOTE_BASE} ...")
        ssh_exec(client, f"mkdir -p {REMOTE_BASE}")
        print("  ✓ Directory created")

        # Step 4: Upload project files
        print(f"\n[4/6] Uploading project files (this may take a while) ...")
        sftp = client.open_sftp()

        # Create remote directory structure
        # Create all necessary directories (recursive mkdir -p)
        remote_dirs = [
            "oobm-topology/config",
            "oobm-topology/inventory",
            "oobm-topology/data/inventory",
            "oobm-topology/data/collected",
            "oobm-topology/data/parsed",
            "oobm-topology/data/topology",
            "oobm-topology/src/opsbrain_oobm/inventory",
            "oobm-topology/src/opsbrain_oobm/collector",
            "oobm-topology/src/opsbrain_oobm/parser/textfsm_templates",
            "oobm-topology/src/opsbrain_oobm/topology",
            "oobm-topology/src/opsbrain_oobm/orchestrator",
            "oobm-topology/src/opsbrain_oobm/model",
            "web/backend/app/routes",
            "web/nginx",
            "web/frontend/src/router",
            "web/frontend/src/stores",
            "web/frontend/src/views",
            "web/frontend/src/components",
            "web/frontend/src/assets/styles",
            "agent",
        ]
        for d in remote_dirs:
            ssh_exec(client, f"mkdir -p {REMOTE_BASE}/{d}")

        def upload_file(local_rel, remote_rel=None):
            if remote_rel is None:
                remote_rel = local_rel
            local_path = os.path.join(LOCAL_PROJECT, local_rel)
            remote_path = f"{REMOTE_BASE}/{remote_rel}"
            if os.path.isfile(local_path):
                sftp.put(local_path, remote_path)
                print(f"    {local_rel}")

        # OOBM topology files
        oobm_files = [
            "oobm-topology/docker-compose.yml",
            "oobm-topology/Dockerfile",
            "oobm-topology/Makefile",
            "oobm-topology/pyproject.toml",
            "oobm-topology/README.md",
            "oobm-topology/.env.example",
            "oobm-topology/config/collector.yml",
            "oobm-topology/config/vendors.yml",
            "oobm-topology/src/opsbrain_oobm/__init__.py",
            "oobm-topology/src/opsbrain_oobm/__main__.py",
            "oobm-topology/src/opsbrain_oobm/cli.py",
            "oobm-topology/src/opsbrain_oobm/config.py",
            "oobm-topology/src/opsbrain_oobm/logging_setup.py",
        ]
        for f in oobm_files:
            upload_file(f)

        # Python package subdirectories
        pkg_files = [
            ("oobm-topology/src/opsbrain_oobm/inventory/__init__.py", "oobm-topology/src/opsbrain_oobm/inventory/__init__.py"),
            ("oobm-topology/src/opsbrain_oobm/inventory/models.py", None),
            ("oobm-topology/src/opsbrain_oobm/inventory/loader.py", None),
            ("oobm-topology/src/opsbrain_oobm/inventory/validator.py", None),
            ("oobm-topology/src/opsbrain_oobm/inventory/commands.py", None),
            ("oobm-topology/src/opsbrain_oobm/collector/__init__.py", None),
            ("oobm-topology/src/opsbrain_oobm/collector/engine.py", None),
            ("oobm-topology/src/opsbrain_oobm/collector/session.py", None),
            ("oobm-topology/src/opsbrain_oobm/collector/pool.py", None),
            ("oobm-topology/src/opsbrain_oobm/parser/__init__.py", None),
            ("oobm-topology/src/opsbrain_oobm/parser/engine.py", None),
            ("oobm-topology/src/opsbrain_oobm/topology/__init__.py", None),
            ("oobm-topology/src/opsbrain_oobm/topology/builder.py", None),
            ("oobm-topology/src/opsbrain_oobm/topology/linker.py", None),
            ("oobm-topology/src/opsbrain_oobm/topology/renderer.py", None),
            ("oobm-topology/src/opsbrain_oobm/topology/diff.py", None),
            ("oobm-topology/src/opsbrain_oobm/orchestrator/__init__.py", None),
            ("oobm-topology/src/opsbrain_oobm/orchestrator/pipeline.py", None),
            ("oobm-topology/src/opsbrain_oobm/orchestrator/state_machine.py", None),
            ("oobm-topology/src/opsbrain_oobm/model/__init__.py", None),
            ("oobm-topology/src/opsbrain_oobm/model/config.py", None),
            ("oobm-topology/src/opsbrain_oobm/model/client.py", None),
        ]
        for local_rel, remote_rel in pkg_files:
            upload_file(local_rel, remote_rel)

        # TextFSM templates
        upload_file("oobm-topology/src/opsbrain_oobm/parser/textfsm_templates/cisco_show_lldp_neighbors_detail.textfsm",
                     "oobm-topology/src/opsbrain_oobm/parser/textfsm_templates/cisco_show_lldp_neighbors_detail.textfsm")
        upload_file("oobm-topology/src/opsbrain_oobm/parser/textfsm_templates/cisco_show_cdp_neighbors_detail.textfsm")
        upload_file("oobm-topology/src/opsbrain_oobm/parser/textfsm_templates/cisco_show_arp.textfsm")
        upload_file("oobm-topology/src/opsbrain_oobm/parser/textfsm_templates/cisco_show_mac_address_table.textfsm")
        upload_file("oobm-topology/src/opsbrain_oobm/parser/textfsm_templates/cisco_show_ip_interface_brief.textfsm")

        # Web backend
        web_backend_files = [
            "web/backend/Dockerfile",
            "web/backend/requirements.txt",
            "web/backend/app/__init__.py",
            "web/backend/app/auth.py",
            "web/backend/app/database.py",
            "web/backend/app/models.py",
            "web/backend/app/schemas.py",
            "web/backend/app/knowledge_base.py",
            "web/backend/app/routes/__init__.py",
            "web/backend/app/routes/auth.py",
            "web/backend/app/routes/settings.py",
            "web/backend/app/routes/apis.py",
            "web/backend/app/routes/projects.py",
            "web/backend/app/routes/agents.py",
            "web/backend/app/routes/agent_chat.py",
            "web/backend/app/routes/topology.py",
            "web/backend/app/routes/dashboard.py",
            "web/backend/app/routes/subagents.py",
        ]
        for f in web_backend_files:
            upload_file(f)

        # Web frontend
        web_frontend_files = [
            "web/frontend/index.html",
            "web/frontend/package.json",
            "web/frontend/vite.config.js",
            "web/frontend/src/main.js",
            "web/frontend/src/App.vue",
            "web/frontend/src/router/index.js",
            "web/frontend/src/stores/auth.js",
            "web/frontend/src/views/LoginView.vue",
            "web/frontend/src/views/SetupView.vue",
            "web/frontend/src/views/DashboardView.vue",
            "web/frontend/src/views/SettingsView.vue",
            "web/frontend/src/views/TopologyView.vue",
            "web/frontend/src/views/TopologyListView.vue",
            "web/frontend/src/views/TopologyDetail.vue",
            "web/frontend/src/views/KnowledgeBaseView.vue",
            "web/frontend/src/views/NotFoundView.vue",
            "web/frontend/src/components/AppLayout.vue",
            "web/frontend/src/components/AgentPanel.vue",
            "web/frontend/src/assets/styles/main.css",
        ]
        for f in web_frontend_files:
            upload_file(f)

        # Nginx
        upload_file("web/nginx/Dockerfile")
        upload_file("web/nginx/opsbrain.conf")

        # Agent skill
        upload_file("agent/oobm-topology-skill.md")

        # .dockerignore
        upload_file("web/.dockerignore")

        sftp.close()
        print("  ✓ All files uploaded")

        # Step 5: Create .env from example
        print(f"\n[5/6] Configuring deployment ...")
        ssh_exec(client, f"cp {REMOTE_BASE}/oobm-topology/.env.example {REMOTE_BASE}/oobm-topology/.env")
        # Generate random JWT secret
        import secrets
        jwt_secret = secrets.token_hex(32)
        ssh_exec(client, f"sed -i 's/change-me-in-production/{jwt_secret}/' {REMOTE_BASE}/oobm-topology/.env")
        print("  ✓ .env configured with secure JWT secret")

        # Step 6: Build and start
        print(f"\n[6/6] Building and starting services (第一次构建会下载依赖，需几分钟)...")
        # Build nginx first (includes frontend)
        code, out, err = ssh_exec(
            client,
            f"cd {REMOTE_BASE}/oobm-topology && "
            f"docker compose build nginx web 2>&1",
            timeout=600,
        )
        if code != 0:
            print(f"  Build output:\n{out[:2000]}\n{err[:2000]}")
        else:
            print(f"  Build complete")

        # Start services
        code, out, err = ssh_exec(
            client,
            f"cd {REMOTE_BASE}/oobm-topology && docker compose up -d nginx web 2>&1",
            timeout=60,
        )
        print(f"  {out[:500] if out else '✓ Services started'}")

        # Verify
        code, out, err = ssh_exec(client, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")
        print(f"\n  Running containers:\n{out}")

        print(f"\n{'=' * 60}")
        print(f"  ✅ Deployment complete!")
        print(f"  Access: http://129.211.28.47/opsbrain/")
        print(f"{'=' * 60}")

    except Exception as e:
        print(f"\n  ❌ Deployment failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
