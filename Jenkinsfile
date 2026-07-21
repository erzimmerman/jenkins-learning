pipeline {
    agent any

    parameters {
        string(
            name: 'BASE_URL',
            defaultValue: 'https://sms.schoolsoft.se/larande/ss12000/v2',
            description: 'Base URL for the SS12000 API'
        )
        string(
            name: 'ORG_ID',
            defaultValue: '0',
            description: 'Organization ID used when requesting the token'
        )
        string(
            name: 'SFTP_HOST',
            defaultValue: 'sms-int1.schoolsoft.se',
            description: 'SchoolSoft SFTP hostname'
        )
        string(
            name: 'SFTP_USER',
            defaultValue: 'root',
            description: 'SchoolSoft SFTP username'
        )
        string(
            name: 'SFTP_REMOTE_DIR',
            defaultValue: 'larande_test',
            description: 'Remote directory for the CSV files'
        )
        string(
            name: 'SFTP_PORT',
            defaultValue: '2222',
            description: 'SchoolSoft SFTP port'
        )
    }

    options {
        disableConcurrentBuilds()
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
    }

    stages {
        stage('Inspect environment') {
    steps {
        deleteDir()
        checkout scm

        sh '''
            set -eu
            whoami
            pwd
            python3 --version
            git log -1 --oneline

            echo "Known hosts fingerprint:"
            ssh-keygen -lf known_hosts

            echo "Checking SchoolSoft host entry:"
            ssh-keygen \
                -F "[$SFTP_HOST]:$SFTP_PORT" \
                -f known_hosts
        '''
    }
}

        stage('Create python environment') {
            steps {
                sh '''
                    set -eu
                    rm -rf .venv output
                    python3 -m venv .venv
                    .venv/bin/python -m pip install --upgrade pip
                    .venv/bin/pip install -r requirements.txt
                    mkdir -p output
                '''
            }
        }

        stage('Run SS12000 export') {
            steps {
                withCredentials([
                    string(
                        credentialsId: 'ss12000-secret',
                        variable: 'SS12000_SECRET'
                    )
                ]) {
                    sh '''
                        set -eu
                        .venv/bin/python ss12000_export.py \
                            --base-url "$BASE_URL" \
                            --org-id "$ORG_ID" \
                            --output-dir output
                    '''
                }
            }
        }

        stage('Create users CSV') {
            steps {
                sh '''
                    set -eu
                    .venv/bin/python create_users_filtered.py \
                        --persons output/persons.json \
                        --output output/users_filtered.csv
                '''
            }
        }

        stage('Create user_observers CSV') {
            steps {
                sh '''
                    set -eu
                    .venv/bin/python create_user_observers.py \
                        --persons output/persons.json \
                        --output output/user_observers.csv
                '''
            }
        }

        stage('Create sections CSV') {
            steps {
                sh '''
                    set -eu
                    .venv/bin/python create_sections.py \
                        --activities output/activities.json \
                        --output output/sections.csv
                '''
            }
        }

        stage('Create enrollments CSV') {
            steps {
                sh '''
                    set -eu
                    .venv/bin/python create_enrollments.py \
                        --persons output/persons.json \
                        --activities output/activities.json \
                        --output output/enrollments.csv
                '''
            }
        }

        stage('Create courses CSV') {
            steps {
                sh '''
                    set -eu
                    .venv/bin/python create_courses.py \
                        --activities output/activities.json \
                        --output output/courses.csv
                '''
            }
        }

        stage('Inspect output') {
            steps {
                sh '''
                    set -eu
                    echo "Generated files:"
                    ls -lh output/*.json output/*.csv

                    echo "CSV row counts (including header):"
                    wc -l output/*.csv

                    echo "CSV headers:"
                    for file in output/*.csv; do
                        echo "--- $file"
                        head -n 1 "$file"
                    done

                    .venv/bin/python validate_outputs.py --output-dir output
                '''
            }
        }

        stage('Upload CSV files to SchoolSoft SFTP') {
            steps {
                sshagent(credentials: ['sftp-private-key']) {
                    sh '''
                        set -eu

                        SFTP_HOST="${SFTP_HOST:-sms-int1.schoolsoft.se}"
                        SFTP_USER="${SFTP_USER:-root}"
                        SFTP_REMOTE_DIR="${SFTP_REMOTE_DIR:-larande_test}"
                        SFTP_PORT="${SFTP_PORT:-2222}"

                        CSV_FILES="users_filtered.csv user_observers.csv sections.csv enrollments.csv courses.csv"

                        for file in $CSV_FILES; do
                            test -s "output/$file"
                        done

                        KNOWN_HOSTS_SOURCE="$WORKSPACE/known_hosts"
                        EXPECTED_HOST="[$SFTP_HOST]:$SFTP_PORT"

                        test -s "$KNOWN_HOSTS_SOURCE"

                        case "$SFTP_PORT" in
                            *[!0-9]*|'')
                                echo "SFTP_PORT must contain only digits." >&2
                                exit 1
                                ;;
                        esac

                        SFTP_KNOWN_HOSTS_FILE="$(mktemp)"
                        SFTP_BATCH_FILE="$(mktemp)"
                        trap 'rm -f "$SFTP_KNOWN_HOSTS_FILE" "$SFTP_BATCH_FILE"' EXIT

                        # OpenSSH treats spaces in UserKnownHostsFile as file
                        # separators. Jenkins workspaces can contain spaces, so
                        # use a temporary path without spaces for the SFTP call.
                        cp "$KNOWN_HOSTS_SOURCE" "$SFTP_KNOWN_HOSTS_FILE"
                        chmod 600 "$SFTP_KNOWN_HOSTS_FILE"

                        echo "Verifying host entry $EXPECTED_HOST in temporary known_hosts"

                        if ! ssh-keygen \
                            -F "$EXPECTED_HOST" \
                            -f "$SFTP_KNOWN_HOSTS_FILE" \
                            > /dev/null; then
                            echo "No matching host/port entry exists in known_hosts." >&2
                            echo "Available fingerprints:" >&2
                            ssh-keygen -lf "$SFTP_KNOWN_HOSTS_FILE" >&2
                            exit 1
                        fi

                        ssh-keygen -lf "$SFTP_KNOWN_HOSTS_FILE"

                        printf 'cd "%s"\n' "$SFTP_REMOTE_DIR" > "$SFTP_BATCH_FILE"

                        for file in $CSV_FILES; do
                            printf 'put "output/%s" "%s"\n' "$file" "$file" >> "$SFTP_BATCH_FILE"
                        done

                        printf 'bye\n' >> "$SFTP_BATCH_FILE"

                        echo "Uploading five CSV files to $SFTP_HOST:$SFTP_REMOTE_DIR"

                        sftp \
                            -F /dev/null \
                            -vv \
                            -b "$SFTP_BATCH_FILE" \
                            -P "$SFTP_PORT" \
                            -o "BatchMode=yes" \
                            -o "StrictHostKeyChecking=yes" \
                            -o "CheckHostIP=no" \
                            -o "HostKeyAlgorithms=ssh-ed25519" \
                            -o "GlobalKnownHostsFile=/dev/null" \
                            -o "UserKnownHostsFile=$SFTP_KNOWN_HOSTS_FILE" \
                            "$SFTP_USER@$SFTP_HOST"

                        echo "SchoolSoft SFTP upload completed successfully."
                    '''
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts(
                artifacts: 'output/*.json, output/*.csv',
                allowEmptyArchive: true,
                fingerprint: true
            )
        }
        success {
            echo 'SS12000 export and all CSV transformations completed successfully.'
        }
        failure {
            echo 'Pipeline failed. Check Console Output and the archived source JSON files.'
        }
        cleanup {
            sh '''
                rm -rf .venv
                rm -rf output
            '''
        }
    }
}
