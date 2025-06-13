// Code prompting is a novel technique that enhances reasoning abilities in text+code 
// Large Language Models (LLMs) by transforming natural language (NL) tasks into code representations

def init(stageName) {
    def defaultConfigs = [
        enable: true,
        display_name: "codetek",
        credentials: "",
        gerrit_credentials: "",
        // git-commit-message-review
        // git-commit-coverity-check
        // git-commit-coverity-check-indiv
        // codetek-correction
        // codetek-optimization
        // codetek-code-comment
        // codetek-coding-style
        // coverity-analysis-advise-full
        // coverity-analysis-advise-commit
        // codetek-jira-preparation -> prejira.py
        function: "",
        // CODING_STYLE_TAB_4SPACE: for git-commit-*, add coding style check for tab and space
        // SELF_RANKING: ask GPT to rank himself
        // FULL_GIT_PATCH: Full file with patch (git-commit-coverity-check)
        customization: "",
        
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)
    if (config["function"] == "coverity-analysis-advise-full" || config["function"] == "coverity-analysis-advise-commit") {
        env.PF_COV_DETAILED_HTML_REPORT = "1"
    }

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    def creds = []
    creds.add(string(credentialsId: configs["credentials"], variable: "REALGPT_KEY"))
    if (configs["gerrit_credentials"] != "") {
        print "Take stage gerrit credentials " + configs["gerrit_credentials"]
        creds.add(sshUserPrivateKey(credentialsId: configs["gerrit_credentials"], usernameVariable: 'GERRIT_USER', keyFileVariable: 'GERRIT_KEY'))
    }
    else if (env.PF_GERRIT_CREDENTIALS) {
        print "Take global gerrit credentials " + env.PF_GERRIT_CREDENTIALS
        creds.add(sshUserPrivateKey(credentialsId: env.PF_GERRIT_CREDENTIALS, usernameVariable: 'GERRIT_USER', keyFileVariable: 'GERRIT_KEY'))
    }
    else if (env.PF_GERRIT_CREDENTIALS_MAIN && env.PF_GERRIT_CREDENTIALS_MAIN != "PF_NONE") {
        print "Take source gerrit credentials " + env.PF_GERRIT_CREDENTIALS_MAIN
        creds.add(sshUserPrivateKey(credentialsId: env.PF_GERRIT_CREDENTIALS_MAIN, usernameVariable: 'GERRIT_USER', keyFileVariable: 'GERRIT_KEY'))
    }

    withCredentials(creds) {
        env.PF_REALGPT_KEY = "${REALGPT_KEY}"

        if (configs["function"] == "codetek-jira-preparation") {
            utils.pyExec("prejira", configs["stageName"], "", [])
        }
        else {
            def copyPreviewReport = false
            if (configs["function"] == "coverity-analysis-advise-full" || configs["function"] == "coverity-analysis-advise-commit") {
                copyPreviewReport = true
            }
            configs["buildBranches"] = utils.pfParallelInfo(copyPreviewReport)
            utils.updateStageConfig(configs)
            if (isUnix() && env.PF_BUILD_ENV == "none") {
                utils.pyExec(configs["actionName"], configs["stageName"], "CHECK_ENV", [])
                def singularityError = fileExists ".pf-${configs['plainStageName']}/singularity_error"
                print "singularityError: ${singularityError}"
                if (singularityError == true) {
                    // singularity not available
                    utils.pyExec(configs["actionName"], configs["stageName"], "", [])
                }
                else {
                    // enforce the use of 'openai/linux.sif'
                    // do not use 'openai/linux.sif' when PF_BUILD_ENV is set
                    utils.pyExec(configs["actionName"], configs["stageName"], "", [], pyEnv="openai")
                }
            }
            else {
                utils.pyExec(configs["actionName"], configs["stageName"], "", [])
            }
        }
    }
    dir (".pf-${configs['plainStageName']}") {
        utils.exportEnv()
    }
    utils.archiveStageArtifacts(configs["stageName"])
}

return this
