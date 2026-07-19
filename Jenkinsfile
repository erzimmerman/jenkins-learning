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
            defaultValue: 'Lärande',
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
                sh '''
                    set -eu
                    whoami
                    pwd
                    python3 --version
                    git log -1 --oneline
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

                        CSV_FILES="users_filtered.csv user_observers.csv sections.csv enrollments.csv courses.csv"

                        for file in $CSV_FILES; do
                            test -s "output/$file"
                        done

                        test -s known_hosts

                        case "$SFTP_PORT" in
                            *[!0-9]*|'')
                                echo "SFTP_PORT must contain only digits." >&2
                                exit 1
                                ;;
                        esac

                        SFTP_BATCH_FILE="$(mktemp)"
                        trap 'rm -f "$SFTP_BATCH_FILE"' EXIT

                        printf 'cd "%s"\n' "$SFTP_REMOTE_DIR" > "$SFTP_BATCH_FILE"

                        for file in $CSV_FILES; do
                            printf 'put "output/%s" "%s"\n' "$file" "$file" >> "$SFTP_BATCH_FILE"
                        done

                        printf 'bye\n' >> "$SFTP_BATCH_FILE"

                        echo "Uploading five CSV files to $SFTP_HOST:$SFTP_REMOTE_DIR"

                        sftp \
                            -b "$SFTP_BATCH_FILE" \
                            -P "$SFTP_PORT" \
                            -o BatchMode=yes \
                            -o StrictHostKeyChecking=yes \
                            -o UserKnownHostsFile="$WORKSPACE/known_hosts" \
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
