def init(stageName) {
    def defaultConfigs = [
        display_name: "RJIRAProxy",
        enable: true,
        // trigger apiproxy jenkins job
        remote_host: "rjiraproxy",
        remote_job: "JIRA/coverity-to-JIRA",
        remote_job_token: "triggerme",
        remote_job_parameters: "{}",

        // coverity to JIRA
        // {'JIRA_PROJECT':'$YOUR_JIRA_PROJECT_KEY','DEFAULT_ASSIGNEE':'raypeng','COV_PROJECT':'$YOUR_COV_PROJECT_NAME','ASSIGN_POLICY':'default'}
        jira_project: "",
        // Username/password, token is not valid in RJIRA
        jira_credentials: "",
        default_assignee: "",
        cov_project: "",
        assign_policy: "author",
        // parallel_mode
        // general: non-parallel or all parallel builds with same coverity project
        // separate: parallel builds with different coverity project
        parallel_mode: "general",
        customizations: "",

        sd_jenkins_token: "rey-sdjenkins-token",
        scriptableParams: []
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def pythonExec = utils.getPython()
    def translateCmd = "${pythonExec} ${env.PF_ROOT}/pipeline_scripts/utils.py -f ${env.PF_ROOT}/settings/${stageName}_config.json -c TRANSLATE_CONFIG"
    if (isUnix()) {
        sh translateCmd
    }
    else {
        bat translateCmd
    }
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def plainStageName = configs["plainStageName"]

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

    def extraParams
    try {
        extraParams = readJSON text: configs["remote_job_parameters"]
    }
    catch (e) {
        extraParams = [:]
    }
    if (configs.containsKey("jira_project") == true) {
        if (configs["jira_project"] == "") {
            error("Invalid JIRA project")
        }
        else {
            extraParams["JIRA_PROJECT"] = configs["jira_project"]
        }
    }
    if (configs.containsKey("assign_policy") == true) {
        if (configs["assign_policy"] == "") {
            extraParams["ASSIGN_POLICY"] = "author"
        }
        else {
            extraParams["ASSIGN_POLICY"] = configs["assign_policy"]
        }
    }
    if (configs.containsKey("default_assignee") == true) {
        extraParams["DEFAULT_ASSIGNEE"] = configs["default_assignee"]
    }
    if (configs.containsKey("cov_project") == true) {
        extraParams["COV_PROJECT"] = configs["cov_project"]
    }
    if (configs.containsKey("customizations") == true) {
        extraParams["CUSTOMIZATIONS"] = configs["customizations"]
    }
    print "RJIRAProxy: extraParams " + extraParams


    withCredentials([string(credentialsId: configs["jira_credentials"], variable: 'JIRA_TOKEN')]) {
        // RAW python on build agent has no crypto module, and download CTC's sif
        utils.pyExec(configs["actionName"], configs["stageName"], "ENCRYPT_JIRA_CREDENTIALS", [], "python")
    }
    utils.pyExec(configs["actionName"], configs["stageName"], "ENCRYPT_GERRIT_ENV", [], "python")
    print "RJIRAProxy: RJIRA token used"
    dir (".pf-${plainStageName}") {
        archiveArtifacts artifacts: "encryptToken"
        archiveArtifacts artifacts: "gerritENV"
    }

    // note:
    // 1. triggerRemoteJob does not support build token root
    // 2. curl (buildByToken) runs on agent that causes firewall issue
    // 3. to deal with firewall issue, apiproxy should be triggered by "Parameterized Remote Trigger" plugin
    //    and global read permission is necessary for anonymous user (on apiproxy)
    if (tokenCredentials) {
        // account 'devops_jenkins' with its jenkins token, not recommended
        withCredentials([string(credentialsId: configs["sd_jenkins_token"], variable: 'JENKINS_TOKEN')]) {
            utils.pyExec(configs["actionName"], configs["stageName"], "CHECK_JENKINS_TOKEN", [])

            def paramters = "\nSDJENKINS_URL=${env.BUILD_URL}\nSDJENKINS_TOKEN=${JENKINS_TOKEN}"
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
        // user account with his/her jenkins token
        withCredentials([usernamePassword(credentialsId: configs["sd_jenkins_token"], usernameVariable: 'JENKINS_USER', passwordVariable: 'JENKINS_TOKEN')]) {
            utils.pyExec(configs["actionName"], configs["stageName"], "CHECK_JENKINS_TOKEN", [])

            def paramters = "\nSDJENKINS_URL=${env.BUILD_URL}\nSDJENKINS_USER=${JENKINS_USER}\nSDJENKINS_TOKEN=${JENKINS_TOKEN}"
            for (def key in extraParams.keySet()) {
                paramters += "\n${key}=${extraParams[key]}"
            }
            print "paramters, " + paramters
            if (env.PF_GLOBAL_PARALLELINFO) {
                unstash name: "pf-global-parallelinfo"
                archiveArtifacts artifacts: "parallelInfo.json"
                if (configs["parallel_mode"] == "separate") {
                    def parallelInfo = readJSON file: "parallelInfo.json"
                    for (def branch in parallelInfo["branches"]) {
                        def brancheParamters = paramters + "\nPF_REMOTE_PARALLEL_BUILD=${branch}"
                        triggerRemoteJob job: configs["remote_job"], parameters: "${brancheParamters}", remoteJenkinsUrl: "https://apiproxy.rtkbf.com", token: configs['remote_job_token']
                    }
                }
                else {
                    paramters += "\nPF_REMOTE_PARALLEL_BUILD=1"
                    triggerRemoteJob job: configs["remote_job"], parameters: "${paramters}", remoteJenkinsUrl: "https://apiproxy.rtkbf.com", token: configs['remote_job_token']
                }
            }
            else {
                triggerRemoteJob job: configs["remote_job"], parameters: "${paramters}", remoteJenkinsUrl: "https://apiproxy.rtkbf.com", token: configs['remote_job_token']
            }
        }
    }
}

return this
