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

    stages {
        stage('Inspect environment') {
            steps {
                sh 'whoami'
                sh 'pwd'
                sh 'python3 --version'
                sh 'git log -1 --oneline'
            }
        }

        stage('Create Python environment') {
            steps {
                sh '''
                    python3 -m venv .venv
                    .venv/bin/python -m pip install --upgrade pip
                    .venv/bin/pip install -r requirements.txt
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
                        .venv/bin/python ss12000_export.py \
                            --base-url "$BASE_URL" \
                            --org-id "$ORG_ID"
                    '''
                }
            }
        }

        stage('Inspect output') {
            steps {
                sh '''
                    echo "Generated files:"
                    ls -lh response_persons_*.json
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts(
                artifacts: 'response_persons_*.json',
                allowEmptyArchive: true,
                fingerprint: true
            )
        }

        success {
            echo 'SS12000 export completed successfully.'
        }

        failure {
            echo 'SS12000 export failed. Check Console Output.'
        }

        cleanup {
            sh '''
                rm -rf .venv
                rm -f response_persons_*.json
            '''
        }
    }
}
