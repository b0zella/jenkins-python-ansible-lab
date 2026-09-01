# jenkins-python-ansible-lab

A deliberately small starting point for a Jenkins home lab. One Python script
runs some bash commands, then calls an Ansible playbook. Jenkins runs the
Python script. That's the whole thing.

The point is to get the *chain* working — Git push → Jenkins → Python → bash →
Ansible → build artifact — before any of the individual links get interesting.

```
Jenkinsfile          the pipeline: what Jenkins does on each run
requirements.txt     Python deps (just ansible-core)
scripts/run.py       the driver: bash commands, then ansible-playbook
ansible/playbook.yml four harmless tasks against localhost
ansible/inventory.ini which hosts Ansible may touch (localhost for now)
output/              report.txt lands here; gitignored, archived by Jenkins
```

## Run it on your laptop first

Do not start with Jenkins. Get the script working by hand, then hand it to
Jenkins. Debugging two unfamiliar things at once is how people give up on this.

```bash
git clone <your-repo-url>
cd jenkins-python-ansible-lab

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 scripts/run.py
echo "exit code: $?"          # 0 = everything worked
cat output/report.txt
```

Run it a second time and watch the `PLAY RECAP` line. It goes from
`changed=2` to `changed=1`: the directory already exists so Ansible leaves it
alone, but the marker file still changes because its contents include a
timestamp. That's idempotence — a task only reports `changed` when it actually
had to do something — and it's the property that makes it safe to run a
playbook on a schedule instead of once by hand.

## Then wire up Jenkins

1. Install Jenkins (on your OCI instance, or in Docker on any machine):
   ```bash
   docker run -d --name jenkins -p 8080:8080 -v jenkins_home:/var/jenkins_home jenkins/jenkins:lts
   docker logs jenkins        # the initial admin password is printed here
   ```
   Make sure `python3` and `python3-venv` exist wherever Jenkins runs. In the
   official image: `docker exec -u root jenkins apt-get update && docker exec -u root jenkins apt-get install -y python3 python3-venv`

2. Push this repo to GitHub.

3. In Jenkins: **New Item → Pipeline**. Under *Pipeline*, choose
   **Pipeline script from SCM**, set SCM to Git, paste your repo URL, and set
   *Script Path* to `Jenkinsfile`. For a private repo, add a GitHub personal
   access token under **Manage Jenkins → Credentials** and select it here.

4. **Build Now.** Watch *Console Output*. When it goes green, `report.txt`
   shows up on the build page as an archived artifact.

5. Only then turn on a trigger. Uncomment `pollSCM('H/5 * * * *')` in the
   Jenkinsfile — Jenkins checks GitHub every five minutes and builds on new
   commits. This needs no inbound firewall rule, which makes it the right
   first choice. Webhooks are faster but require exposing Jenkins to the
   internet; save that for after you've put a cert and a locked-down NSG in
   front of it.

## Things worth understanding before you move on

**Exit codes are the contract.** `run.py` returns 0 or 1. Jenkins reads that
and nothing else to decide pass/fail. Every tool in this space works this way.

**Lists, not strings, in `subprocess`.** `["df", "-h"]` goes straight to the OS
with no shell involved, so quoting and stray characters can't break it or be
abused. `shell=True` exists for when you need a pipe — use it deliberately, and
never on a string you built from input you don't control.

**The inventory is the seam.** Switching from localhost to a real remote host
is a change to `inventory.ini` alone. The playbook and the Python script don't
know or care. Keep it that way.

**Secrets live in Jenkins, not the repo.** SSH keys, API tokens, OCI private
keys — all of it goes in **Manage Jenkins → Credentials**, and gets pulled into
a build with `withCredentials()` or `sshagent()`. The `.gitignore` here blocks
the common accidents, but the habit matters more than the file.

## Where to take it next

Roughly in order of difficulty:

- Point the inventory at a second VM over SSH. Add the key as a Jenkins
  credential and wrap the run stage in `sshagent(['your-cred-id'])`.
- Swap the toy playbook tasks for a real patch run (`ansible.builtin.dnf` /
  `apt` with `state: latest`), capture the package list before and after, and
  diff them in the report.
- Add a nightly `cron` trigger so patching happens on a schedule.
- Add a second stage that runs `terraform plan` and fails the build on drift.
- Add an approval gate (`input message: 'Apply?'`) between plan and apply.
