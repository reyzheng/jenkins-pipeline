import groovy.transform.Field

def init(stageName) {
    def utils = load "utils.groovy"
    def actionName = utils.extractActionName(stageName)

    def defaultConfigs = [
        display_name: "",
        enable: true,
        // trigger local jenkins job
        job: "",
        // trigger remote jenkins job
        remote_job: "",
        remote_job_token: "",
        remote_jenkins_user: "",
        remote_jenkins_credentials: "",
        remote_jenkins_parameters: ""
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    config.settings.has_stashes = false

    return config
}

def func(pipelineAsCode, configs, preloads) {
    def underUnix = isUnix()

    if (configs.enable == false) {
        print "Stage ${preloads.stageName} cancelled manually"
        return
    }
    def UPSTREAM_JOB = env.JOB_NAME
    def UPSTREAM_BUILDNUMBER = env.BUILD_NUMBER
    // trigger local job
    if (configs.job != "") {
        build job: configs.job, 
                parameters: [
                    string(name: 'UPSTREAM_JOB', value: UPSTREAM_JOB),
                    string(name: 'UPSTREAM_BUILDNUMBER', value: String.valueOf(UPSTREAM_BUILDNUMBER))
                ]
    }
    // trigger remote job
    if (configs.remote_job != "") {
        withCredentials([string(credentialsId: configs.remote_jenkins_credentials, variable: 'TOKEN')]) {
            def urlTokens = configs.remote_job.split("://")
            def parameters = readJSON text: configs["remote_jenkins_parameters"]
            def parametersText = ""
            for (def key in parameters.keySet()) {
                parametersText += "\\&${key}=" + parameters[key]
            }
            def curlCommand = "curl --insecure -X POST ${urlTokens[0]}://${configs.remote_jenkins_user}:\$TOKEN@${urlTokens[1]}/buildWithParameters?token=${configs.remote_job_token}\\&UPSTREAM_JOB=${UPSTREAM_JOB}\\&UPSTREAM_BUILDNUMBER=${UPSTREAM_BUILDNUMBER}"
            if (underUnix == true) {
                sh curlCommand
            }
            else {
                bat curlCommand
            }
        }
    }
}

return this
