#!/usr/bin/env python3
"""Deploy SchemaNav 2.0 static build to the Linux VM and serve it with Python http.server."""

from __future__ import annotations

import argparse
import io
import os
import sys
import tarfile
import textwrap
from pathlib import Path

import paramiko
from scp import SCPClient

PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
DEFAULT_HOST = "10.204.11.140"
DEFAULT_USER = "ss01"
DEFAULT_REMOTE_DIR = "/opt/schemanav2"
DEFAULT_SERVICE_NAME = "schemanav2"
DEFAULT_PORT = 5173


def create_dist_archive() -> bytes:
    if not DIST_DIR.is_dir() or not (DIST_DIR / "index.html").exists():
        raise SystemExit(
            f"Missing production build at {DIST_DIR}. Run `npm run build` first."
        )
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in DIST_DIR.rglob("*"):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(DIST_DIR).as_posix())
    buf.seek(0)
    return buf.read()


def run(client: paramiko.SSHClient, cmd: str, check: bool = True) -> tuple[int, str, str]:
    print(f"$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")
    if err.strip():
        sys.stderr.buffer.write(err.encode("utf-8", errors="replace"))
        sys.stderr.buffer.write(b"\n")
    if check and code != 0:
        raise RuntimeError(f"Command failed ({code}): {cmd}")
    return code, out, err


def put_text(sftp: paramiko.SFTPClient, remote_path: str, content: str) -> None:
    with sftp.file(remote_path, "w") as f:
        f.write(content)


def deploy(
    host: str,
    user: str,
    password: str,
    *,
    remote_dir: str = DEFAULT_REMOTE_DIR,
    service_name: str = DEFAULT_SERVICE_NAME,
    port: int = DEFAULT_PORT,
) -> None:
    print(f"Connecting to {user}@{host} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        username=user,
        password=password,
        timeout=30,
        banner_timeout=60,
        allow_agent=False,
        look_for_keys=True,
    )

    print("Packaging dist/ ...")
    archive = create_dist_archive()
    remote_tar = f"/tmp/{service_name}-dist.tar.gz"
    remote_unit = f"/tmp/{service_name}.service"
    remote_script = f"/tmp/deploy-{service_name}.sh"

    unit = textwrap.dedent(
        f"""\
        [Unit]
        Description=SchemaNav 2.0 static UI
        After=network.target

        [Service]
        Type=simple
        User={user}
        WorkingDirectory={remote_dir}
        ExecStart=/usr/bin/env python3 -m http.server {port} --bind 0.0.0.0
        Restart=on-failure
        RestartSec=3

        [Install]
        WantedBy=multi-user.target
        """
    )

    script = textwrap.dedent(
        f"""\
        #!/bin/bash
        set -euo pipefail
        REMOTE_DIR="{remote_dir}"
        SERVICE="{service_name}"
        PORT="{port}"
        TAR="{remote_tar}"
        UNIT_SRC="{remote_unit}"
        USER_NAME="{user}"

        if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
          SUDO="sudo"
        else
          SUDO=""
        fi

        if [ -n "$SUDO" ]; then
          $SUDO mkdir -p "$REMOTE_DIR"
          $SUDO chown -R "$USER_NAME":"$USER_NAME" "$REMOTE_DIR"
        else
          mkdir -p "$REMOTE_DIR" 2>/dev/null || mkdir -p "$HOME/schemanav2"
          if [ ! -w "$REMOTE_DIR" ]; then
            REMOTE_DIR="$HOME/schemanav2"
            mkdir -p "$REMOTE_DIR"
          fi
        fi

        find "$REMOTE_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {{}} +
        tar -xzf "$TAR" -C "$REMOTE_DIR"
        rm -f "$TAR"

        if [ -n "$SUDO" ]; then
          $SUDO cp "$UNIT_SRC" "/etc/systemd/system/${{SERVICE}}.service"
          $SUDO systemctl daemon-reload
          $SUDO systemctl enable --now "$SERVICE"
          $SUDO systemctl restart "$SERVICE"
          $SUDO systemctl --no-pager --full status "$SERVICE" || true
        else
          mkdir -p "$HOME/.config/schemanav2"
          if [ -f "$HOME/.config/schemanav2/server.pid" ]; then
            kill "$(cat "$HOME/.config/schemanav2/server.pid")" 2>/dev/null || true
          fi
          pkill -f "python3 -m http.server ${{PORT}} --bind 0.0.0.0" 2>/dev/null || true
          cd "$REMOTE_DIR"
          nohup python3 -m http.server "$PORT" --bind 0.0.0.0 \\
            > "$HOME/.config/schemanav2/server.log" 2>&1 &
          echo $! > "$HOME/.config/schemanav2/server.pid"
          sleep 1
          echo "Started PID $(cat "$HOME/.config/schemanav2/server.pid") from $REMOTE_DIR"
        fi

        echo "Files in $REMOTE_DIR:"
        ls -la "$REMOTE_DIR"
        echo "Listening on port $PORT:"
        (ss -tlnp 2>/dev/null || netstat -tln 2>/dev/null || true) | grep ":${{PORT}}" || true
        """
    )

    print(f"Uploading archive ({len(archive)} bytes) ...")
    with SCPClient(client.get_transport()) as scp:
        scp.putfo(io.BytesIO(archive), remote_tar)

    with client.open_sftp() as sftp:
        put_text(sftp, remote_unit, unit)
        put_text(sftp, remote_script, script)
        sftp.chmod(remote_script, 0o755)

    print("Running remote install ...")
    code, out, err = run(client, f"bash {remote_script}", check=False)
    client.close()
    if code != 0:
        raise RuntimeError(f"Remote setup failed with exit code {code}")

    print("\nDeployment complete!")
    print(f"Service: {service_name}")
    print(f"Path:    {remote_dir}")
    print(f"Open:    http://{host}:{port}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy SchemaNav 2.0 to VM")
    parser.add_argument("--host", default=os.environ.get("VM_HOST", DEFAULT_HOST))
    parser.add_argument("--user", default=os.environ.get("VM_USER", DEFAULT_USER))
    parser.add_argument(
        "--password", default=os.environ.get("VM_PASSWORD", "unix11")
    )
    parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR)
    parser.add_argument("--service-name", default=DEFAULT_SERVICE_NAME)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    deploy(
        args.host,
        args.user,
        args.password,
        remote_dir=args.remote_dir,
        service_name=args.service_name,
        port=args.port,
    )


if __name__ == "__main__":
    main()
