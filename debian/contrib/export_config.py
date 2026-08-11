#!/opt/edgestream-api/bin/python3
import sys
import json
import os
import httpx
import pwd
import grp
import click
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

# -------------------------- Config --------------------------
DEFAULT_BASE_URL = os.environ.get("EDGESTREAM_BASE_URL", "http://127.0.0.1:3001/api/v1")
DEFAULT_SECRETS = "/etc/edgestream/edgestream-api.secrets"
EXPORT_PATH = "/backup_restore/export"
DEFAULT_FILE_MODE = "0640"

PLAIN_HELP = f"""\
EdgeStream Config Exporter
Export system configuration via the API using System-to-System authentication.

Usage: export_config.py [OPTIONS]

Options:
  -o, --outfile PATH          Write output to file
      --base-url TEXT         API base (default: {DEFAULT_BASE_URL})
      --secrets PATH          Secrets file path (default: {DEFAULT_SECRETS})
      --token TEXT            Manual Bearer token (overrides secrets file)
      --owner TEXT            File owner (name or uid)
      --group TEXT            File group (name or gid)
      --mode TEXT             File mode (octal), e.g. 640
      --no-verify             Disable SSL certificate verification
  -h, --help                  Show this help and exit
"""

def read_system_token(secrets_path: str) -> Optional[str]:
    """Reads the EDGESTREAM_QUEUE_TOKEN from env or the secrets file."""
    token = os.environ.get("EDGESTREAM_QUEUE_TOKEN")
    if token:
        return token.strip()

    try:
        if os.path.exists(secrets_path):
            with open(secrets_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "EDGESTREAM_QUEUE_TOKEN=" in line:
                        return line.split("=", 1)[1].strip().strip("'").strip('"')
    except Exception:
        pass
    return None

def apply_fs_perms(path: str, owner: str = None, group: str = None, mode: str = None):
    """Sets ownership and permissions on the exported file."""
    try:
        uid = int(owner) if owner and owner.isdigit() else (pwd.getpwnam(owner).pw_uid if owner else -1)
        gid = int(group) if group and group.isdigit() else (grp.getgrnam(group).gr_gid if group else -1)
        if uid != -1 or gid != -1:
            os.chown(path, uid, gid)
        if mode:
            os.chmod(path, int(mode, 8))
    except Exception as e:
        click.secho(f"Warning: Could not set permissions on {path}: {e}", fg="yellow")

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-o", "--outfile", type=click.Path(), help="Destination file path")
@click.option("--base-url", default=DEFAULT_BASE_URL, help="API Base URL")
@click.option("--secrets", "secrets_path", default=DEFAULT_SECRETS, help="Path to secrets file")
@click.option("--token", help="Manual Bearer token override")
@click.option("--owner", help="Set file owner")
@click.option("--group", help="Set file group")
@click.option("--mode", default=DEFAULT_FILE_MODE, help="Set file mode (octal)")
@click.option("--no-verify", is_flag=True, help="Disable SSL verification for self-signed certs")
def main(outfile, base_url, secrets_path, token, owner, group, mode, no_verify):
    """Export EdgeStream Configuration to YAML/JSON."""

    auth_token = token or read_system_token(secrets_path)
    if not auth_token:
        click.secho("Error: No EDGESTREAM_QUEUE_TOKEN found. Run as root or provide --token.", fg="red")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "User-Agent": "EdgeStream-Exporter/2.0"
    }

    try:
        with httpx.Client(base_url=base_url, headers=headers, timeout=30.0, verify=not no_verify) as client:
            r = client.get(EXPORT_PATH)
            r.raise_for_status()
            data = data = r.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            click.secho("Error: Authentication Failed. System token is invalid.", fg="red")
        else:
            click.secho(f"Error: API returned {e.response.status_code}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error connecting to API: {e}", fg="red")
        sys.exit(1)

    if yaml:
        try:
            parsed_data = yaml.safe_load(data)
            output_str = yaml.dump(parsed_data, sort_keys=False, indent=2, default_flow_style=False)
        except yaml.YAMLError:
            output_str = data
    else:
        output_str = data

    if outfile:
        try:
            if os.path.exists(outfile):
                os.remove(outfile)

            with open(outfile, "w", encoding="utf-8") as f:
                f.write(output_str)

            apply_fs_perms(outfile, owner, group, mode)
            click.secho(f"Successfully exported config to {outfile}", fg="green")
        except Exception as e:
            click.secho(f"Error writing to file: {e}", fg="red")
            sys.exit(1)
    else:
        click.echo(output_str)

if __name__ == "__main__":
    if any(arg in sys.argv for arg in ["-h", "--help"]):
        print(PLAIN_HELP)
    else:
        main()
