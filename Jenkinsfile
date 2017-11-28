pipeline {
    agent any
    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr:'60'))
        timeout(time: 60, unit: 'MINUTES')

    }
    stages {
        stage('cleanup') { 
            steps {
                sh('rm -rf *')
            }
        }
        stage('checkout'){
            steps {
                checkout(scm)
            }
        }
        stage('test'){
            steps {
                sh('./tools/jin job list')
            }
        }
    }
}