// Jenkinsfile - the pipeline definition. Jenkins reads this file out of the
// repo itself ("pipeline as code"), so the pipeline is versioned alongside the
// code it runs. Change a stage, commit, push -- the pipeline changes.
//
// This is the *declarative* syntax. There's an older scripted syntax you'll
// see in blog posts; ignore it, declarative is what you want.

pipeline {

    // Where to run. `any` means "whatever executor is free" -- fine when
    // Jenkins is a single box. Later this becomes a label like `agent { label 'oci-linux' }`.
    agent any

    options {
        timestamps()                                  // prefix console lines with a clock
        buildDiscarder(logRotator(numToKeepStr: '20'))  // don't fill the disk with old builds
        timeout(time: 10, unit: 'MINUTES')            // kill a hung run instead of blocking forever
    }

    // Uncomment ONE of these once the manual runs are working.
    // triggers {
    //     pollSCM('H/5 * * * *')   // check GitHub every ~5 min. No inbound firewall rule needed.
    //     cron('H 2 * * *')        // or: run at ~2am nightly regardless of commits.
    // }

    environment {
        VENV = "${WORKSPACE}/.venv"
    }

    stages {

        stage('Checkout') {
            steps {
                // `checkout scm` pulls the same repo/branch this Jenkinsfile came from.
                checkout scm
                sh 'git log -1 --oneline'
            }
        }

        stage('Set up Python environment') {
            steps {
                // A virtualenv per build keeps Jenkins' system Python clean and
                // makes the build reproducible. It lives in the workspace and
                // gets wiped with it.
                sh '''
                    set -eu
                    python3 -m venv "$VENV"
                    . "$VENV/bin/activate"
                    pip install --quiet --upgrade pip
                    pip install --quiet -r requirements.txt
                    ansible --version
                '''
            }
        }

        stage('Run pipeline script') {
            steps {
                // The actual work. run.py does the bash commands and then calls
                // ansible-playbook. If it exits nonzero, `sh` fails, and the
                // stage -- and the whole build -- goes red.
                sh '''
                    set -eu
                    . "$VENV/bin/activate"
                    python3 scripts/run.py
                '''
            }
        }
    }

    post {
        // `always` runs whether the build passed or failed -- which is exactly
        // when you most want the report saved.
        always {
            archiveArtifacts artifacts: 'output/*.txt',
                             allowEmptyArchive: true,
                             fingerprint: true
        }
        success {
            echo 'Build succeeded.'
        }
        failure {
            echo 'Build failed - open the "Console Output" link on the left to see which step died.'
        }
        cleanup {
            // Leave the workspace tidy for the next run.
            deleteDir()
        }
    }
}
