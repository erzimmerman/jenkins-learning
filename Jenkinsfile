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
