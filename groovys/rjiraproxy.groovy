def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        enable: true,
        // trigger apiproxy jenkins job
        remote_host: "rjiraproxy",
        remote_job: "JIRA/coverity-to-JIRA",
        remote_job_token: "triggerme",
        remote_job_parameters: "{}",
        sd_jenkins_token: "rey-sdjenkins-token",
        scriptableParams: []
    ]
    def config = utils.commonInit(stageName, defaultConfigs)

    return config
}

def func(configs) {
    if (configs["enable"] == false) {
        print "skip"
        return
    }

    def tokenCredentials = false
    try {
        withCredentials([usernamePassword(credentialsId: configs["sd_jenkins_token"], usernameVariable: 'JENKINS_USER', passwordVariable: 'JENKINS_TOKEN')]) {
            print "Username/password credentials"
        }
    }
    catch (e) {
        print "Token credentials"
        tokenCredentials = true
    }

    if (configs["remote_job"] == "JIRA/blackduck-to-JIRA") {
        configs['remote_job_token'] = "triggerbdjira"
    }
    else if (configs["remote_job"] == "JIRA/coverity-to-JIRA") {
        configs['remote_job_token'] = "triggerme"
    }
    // for jenkins master firewall issue, apiproxy should be triggered by "Parameterized Remote Trigger" plugin
    if (tokenCredentials) {
        // account 'devops_jenkins' with its jenkins token
        withCredentials([string(credentialsId: configs["sd_jenkins_token"], variable: 'JENKINS_TOKEN')]) {
            def paramters = "\nSDJENKINS_URL=${env.BUILD_URL}\nSDJENKINS_TOKEN=${JENKINS_TOKEN}"
            def extraParams = readJSON text: configs["remote_job_parameters"]
            for (def key in extraParams.keySet()) {
                paramters += "\n${key}=${extraParams[key]}"
            }
            if (env.PF_GLOBAL_PARALLELINFO) {
                unstash name: 'pf-global-parallelinfo'
                archiveArtifacts artifacts: 'parallelInfo.json'
                paramters += "\nPF_REMOTE_PARALLEL_BUILD=1"
            }
            triggerRemoteJob job: configs["remote_job"], parameters: "${paramters}", remoteJenkinsUrl: "https://apiproxy.rtkbf.com", token: configs['remote_job_token']
        }
    }
    else {
        // DEPRECATED: user account with his/her jenkins token
        withCredentials([usernamePassword(credentialsId: configs["sd_jenkins_token"], usernameVariable: 'JENKINS_USER', passwordVariable: 'JENKINS_TOKEN')]) {
            def paramters = "\nSDJENKINS_URL=${env.BUILD_URL}\nSDJENKINS_USER=${JENKINS_USER}\nSDJENKINS_TOKEN=${JENKINS_TOKEN}"
            def extraParams = readJSON text: configs["remote_job_parameters"]
            for (def key in extraParams.keySet()) {
                paramters += "\n${key}=${extraParams[key]}"
            }
            if (env.PF_GLOBAL_PARALLELINFO) {
                unstash name: 'pf-global-parallelinfo'
                archiveArtifacts artifacts: 'parallelInfo.json'
                paramters += "\nPF_REMOTE_PARALLEL_BUILD=1"
            }
            triggerRemoteJob job: configs["remote_job"], parameters: "${paramters}", remoteJenkinsUrl: "https://apiproxy.rtkbf.com", token: configs['remote_job_token']
        }
    }
}

return this
