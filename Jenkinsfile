pipeline {
    agent any

    stages {
        stage('Inspect workspace') {
            steps {
                sh 'whoami'
                sh 'pwd'
                sh 'ls -la'
                sh 'python3 --version'
            }
        }

        stage('Run Python') {
            steps {
                sh 'python3 hello.py'
            }
        }
    }

    post {
        success {
            echo 'The pipeline completed successfully.'
        }

        failure {
            echo 'The pipeline failed.'
        }
    }
}

