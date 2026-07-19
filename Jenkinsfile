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

