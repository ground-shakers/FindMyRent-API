pipeline {
    agent any

    options {
        ansiColor('xterm')
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    environment {
        PYTHON_VERSION  = '3.13'
        APP_NAME        = 'FindMyRent-API'
        APP_DIR         = '/home/ubuntu/FindMyRent-API'
        CONTAINER_NAME  = 'findmyrent-api'
        APP_URL         = 'https://ground-shakers.xyz'
    }

    stages {

        // ─────────────────────────────────────────────────
        // STAGE 1: Checkout
        // ─────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                cleanWs()
                checkout scm
                echo "Branch: ${env.BRANCH_NAME} | Commit: ${env.GIT_COMMIT[0..7]}"
            }
        }

        // ─────────────────────────────────────────────────
        // STAGE 2: Install Dependencies
        // ─────────────────────────────────────────────────
        stage('Install Dependencies') {
            steps {
                sh '''
                    python3.13 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    pip install pytest pytest-cov pytest-asyncio httpx flake8
                '''
            }
        }

        // ─────────────────────────────────────────────────
        // STAGE 3: Lint
        // ─────────────────────────────────────────────────
        stage('Lint') {
            steps {
                sh '''
                    . venv/bin/activate
                    echo "Running critical linting checks..."
                    flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

                    echo "Running style checks (non-blocking)..."
                    flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
                '''
            }
        }

        // ─────────────────────────────────────────────────
        // STAGE 4: Tests
        // ─────────────────────────────────────────────────
        stage('Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    pytest tests/ -v \
                        --cov=. \
                        --cov-report=xml \
                        --cov-report=html \
                        --cov-fail-under=0 \
                        --junit-xml=test-results.xml
                '''
            }
            post {
                always {
                    junit 'test-results.xml'
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'htmlcov',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report'
                    ])
                }
            }
        }

        // ─────────────────────────────────────────────────
        // STAGE 5: Deploy  (master branch only)
        // LOCAL deployment — no SSH needed
        // ─────────────────────────────────────────────────
        stage('Deploy') {
            when {
                branch 'master'
            }
            steps {
                sh 'chmod +x ./infrastructure/scripts/deploy.sh'
                sh './infrastructure/scripts/deploy.sh'
            }
        }

    } // end stages

    // ─────────────────────────────────────────────────
    // POST: Notifications
    // ─────────────────────────────────────────────────
    post {
        success {
            script {
                if (env.BRANCH_NAME == 'master') {
                    withCredentials([
                        string(credentialsId: 'mail-username',  variable: 'MAIL_USER'),
                        string(credentialsId: 'mail-password',  variable: 'MAIL_PASS'),
                        string(credentialsId: 'mail-to',        variable: 'MAIL_TO'),
                        string(credentialsId: 'mail-from',      variable: 'MAIL_FROM')
                    ]) {
                        emailext(
                            subject: "✅ Deployment Successful — ${env.APP_NAME} #${env.BUILD_NUMBER}",
                            to: "${MAIL_TO}",
                            from: "${MAIL_FROM}",
                            body: """
Deployment completed successfully!

Application : ${env.APP_NAME}
Branch      : ${env.BRANCH_NAME}
Commit      : ${env.GIT_COMMIT}
Build #     : ${env.BUILD_NUMBER}
App URL     : https://ground-shakers.xyz

Jenkins build: ${env.BUILD_URL}
                            """.stripIndent()
                        )
                    }
                }
            }
        }

        failure {
            withCredentials([
                string(credentialsId: 'mail-to',   variable: 'MAIL_TO'),
                string(credentialsId: 'mail-from', variable: 'MAIL_FROM')
            ]) {
                emailext(
                    subject: "❌ Build Failed — ${env.APP_NAME} #${env.BUILD_NUMBER}",
                    to: "${MAIL_TO}",
                    from: "${MAIL_FROM}",
                    body: """
Build or deployment FAILED.

Application : ${env.APP_NAME}
Branch      : ${env.BRANCH_NAME}
Commit      : ${env.GIT_COMMIT}
Build #     : ${env.BUILD_NUMBER}
Stage       : ${env.FAILED_STAGE ?: 'Unknown'}

Check console output: ${env.BUILD_URL}console
                    """.stripIndent()
                )
            }
        }

        always {
            cleanWs()
        }
    }
}