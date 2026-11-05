pipeline {
    agent any

    environment {
        PYTHON_VENV = "venv"
        FLASK_ENV = "testing"
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source repository...'
                checkout scm
            }
        }

        stage('Build & Setup') {
            steps {
                echo 'Setting up Python virtual environment and dependencies...'
                sh '''
                    python3 -m venv ${PYTHON_VENV}
                    . ${PYTHON_VENV}/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    pip install flake8
                '''
            }
        }

        stage('Quality Gates') {
            parallel {
                stage('Unit Tests') {
                    steps {
                        echo 'Executing automated test suite with pytest...'
                        sh '''
                            . ${PYTHON_VENV}/bin/activate
                            pytest -v --junitxml=test-reports/results.xml
                        '''
                    }
                }
                stage('Linting') {
                    steps {
                        echo 'Running static code analysis and lint checks...'
                        sh '''
                            . ${PYTHON_VENV}/bin/activate
                            flake8 app tests --max-line-length=120 --exclude=__pycache__,.venv,venv
                        '''
                    }
                }
            }
        }

        stage('Package') {
            steps {
                echo 'Packaging application artifact for deployment...'
                sh '''
                    tar -czf railway-reservation-system.tar.gz app docs tests run.py requirements.txt Dockerfile docker-compose.yml
                '''
                archiveArtifacts artifacts: 'railway-reservation-system.tar.gz', fingerprint: true
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'test-reports/*.xml'
            cleanWs()
        }
        success {
            echo 'Pipeline completed successfully: All quality gates passed.'
        }
        failure {
            echo 'Pipeline failed! Release aborted due to test or lint failure.'
        }
    }
}
