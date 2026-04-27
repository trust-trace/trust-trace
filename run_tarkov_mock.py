import os
import subprocess
import sys

env = os.environ.copy()
env["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
env["LOG_LEVEL"] = "DEBUG"
env["LLM_PROVIDER"] = "none"
env["ENABLE_STAGE3_DISPATCH"] = "false"
env["NEO4J_URI"] = "bolt://localhost:7687" # dummy
env["NEO4J_USER"] = "neo4j"
env["NEO4J_PASSWORD"] = "password"

# Run the server
cmd = [sys.executable, "-m", "tarkov.main", "serve"]
subprocess.run(cmd, env=env, cwd="backend")
