#!/usr/bin/env python3
"""
run.py - the driver script for the lab pipeline.

What it does, in order:
  1. Runs a handful of plain bash commands and captures their output.
  2. Runs an Ansible playbook.
  3. Writes everything it saw into output/report.txt so Jenkins can archive it.
  4. Exits 0 if everything worked, 1 if anything failed (this is what makes
     the Jenkins build go red).

Run it by hand first:   python3 scripts/run.py
Then let Jenkins run it: see the Jenkinsfile in the repo root.
"""

import datetime
import pathlib
import shutil
import subprocess
import sys

# ---------------------------------------------------------------------------
# Paths. We resolve everything relative to the repo root instead of assuming
# the current working directory, because Jenkins runs the script from its own
# workspace directory and you don't want to care where that is.
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ANSIBLE_DIR = REPO_ROOT / "ansible"
PLAYBOOK = ANSIBLE_DIR / "playbook.yml"
INVENTORY = ANSIBLE_DIR / "inventory.ini"
OUTPUT_DIR = REPO_ROOT / "output"
REPORT = OUTPUT_DIR / "report.txt"

# Collected as we go, then written to the report at the end.
transcript = []


def find_ansible_playbook():
    """
    Locate the ansible-playbook binary.

    Worth understanding, because it bites everyone once: pip installs
    ansible-playbook into the *virtualenv's* bin directory. That directory is
    only on your PATH while the venv is activated. If something runs this
    script as `.venv/bin/python3 scripts/run.py` -- without activating -- then
    PATH is untouched and the binary is invisible, even though it's sitting
    right next to the interpreter that's executing this line.

    So: look next to the running interpreter first, then fall back to PATH.
    """
    beside_interpreter = pathlib.Path(sys.executable).parent / "ansible-playbook"
    if beside_interpreter.exists():
        return str(beside_interpreter)

    on_path = shutil.which("ansible-playbook")
    if on_path:
        return on_path

    return None


def log(line=""):
    """Print to the console (Jenkins shows this live) and save for the report."""
    print(line, flush=True)
    transcript.append(line)


def run_command(label, command):
    """
    Run one command and return True if it succeeded.

    `command` is a LIST, not a string -- ["df", "-h"] rather than "df -h".
    Python hands that straight to the OS without a shell in between, so there
    is nothing for stray quotes or a semicolon in a variable to break. Use
    shell=True only when you genuinely need shell features like a | pipe, and
    never with a string you built out of untrusted input.
    """
    log(f"--- {label} ---")
    log(f"$ {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,   # grab stdout/stderr instead of letting them fly past (standard output/error)
            text=True,             # give us str, not bytes
            cwd=REPO_ROOT,
        )
    except FileNotFoundError:
        # The binary isn't installed or isn't on PATH. Report it as a failed
        # step instead of letting a traceback blow up the whole script -- a
        # clean "[FAILED]" line in the Jenkins log beats a stack trace.
        log(f"[FAILED] command not found: {command[0]}")
        log()
        return False

    if result.stdout.strip():
        log(result.stdout.rstrip())
    if result.stderr.strip():
        log("[stderr] " + result.stderr.rstrip())

    if result.returncode == 0:
        log(f"[ok] exit 0")
    else:
        log(f"[FAILED] exit {result.returncode}")
    log()

    return result.returncode == 0


def main():
    started = datetime.datetime.now()

    log("=" * 60)
    log(f"Lab pipeline run - {started:%Y-%m-%d %H:%M:%S}")
    log(f"Repo root: {REPO_ROOT}")
    log("=" * 60)
    log()

    # -----------------------------------------------------------------------
    # Step 1: a few ordinary bash commands.
    # Nothing clever -- the point is to see Python shelling out and to see the
    # output land in the Jenkins console log.
    # -----------------------------------------------------------------------
    results = []
    results.append(run_command("Who am I running as", ["whoami"]))
    results.append(run_command("Hostname", ["hostname"]))
    results.append(run_command("Uptime", ["uptime"]))
    results.append(run_command("Disk usage", ["df", "-h", "/"]))

    # -----------------------------------------------------------------------
    # Step 2: hand off to Ansible.
    # Same subprocess call as above -- ansible-playbook is just another binary.
    # -----------------------------------------------------------------------
    ansible_playbook = find_ansible_playbook()

    if ansible_playbook is None:
        log("--- Ansible playbook ---")
        log("[FAILED] ansible-playbook not found.")
        log("         Install it with: pip install -r requirements.txt")
        log()
        results.append(False)
    else:
        results.append(
            run_command(
                "Ansible playbook",
                [
                    ansible_playbook,
                    "-i", str(INVENTORY),
                    str(PLAYBOOK),
                ],
            )
        )

    # -----------------------------------------------------------------------
    # Step 3: write the report so Jenkins has an artifact to archive.
    # -----------------------------------------------------------------------
    OUTPUT_DIR.mkdir(exist_ok=True)
    elapsed = (datetime.datetime.now() - started).total_seconds()
    footer = f"Finished in {elapsed:.1f}s - {sum(results)}/{len(results)} steps succeeded"
    log(footer)

    REPORT.write_text("\n".join(transcript) + "\n")
    print(f"\nReport written to {REPORT}")

    # -----------------------------------------------------------------------
    # Step 4: exit code. This is the whole contract between your script and
    # Jenkins -- 0 means green build, anything else means red.
    # -----------------------------------------------------------------------
    if all(results):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
