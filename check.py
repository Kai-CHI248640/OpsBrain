"""Check/users."""
import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('129.211.28.47', 22, 'root', '248640', allow_agent=False, look_for_keys=False)
s = c.open_sftp()
s.open('/tmp/q.py', 'w').write(b"""import sqlite3, os, json
db = os.environ["OPSBRAIN_HOME"] + "/opsbrain.db"
cur = sqlite3.connect(db).cursor()
cur.execute("SELECT username, password_hash FROM users")
rows = cur.fetchall()
print(json.dumps([[r[0], r[1][:20]] for r in rows]))
cur.execute("SELECT COUNT(*) FROM topology_saves")
print("topos:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM subagents")
print("subagents:", cur.fetchone()[0])
""")
s.close()
def r(cmd): 
    stdin,o,e = c.exec_command(cmd, timeout=10)
    return o.read().decode(errors='replace')
r('docker cp /tmp/q.py opsbrain-web:/tmp/q.py')
print(r('docker exec opsbrain-web python3 /tmp/q.py'))
c.close()
