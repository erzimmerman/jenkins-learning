pipeline {
    agent any

    parameters {
        string(
            name: 'NAME',
            defaultValue: 'Erik',
            description: 'Namnet som Python-scriptet ska hälsa på'
        )
    }

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
                sh "python3 hello.py '${params.NAME}'"
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
