def init(stageName) {
    def defaultConfigs = [
        site_name: "",
        jira_credentials: "",
        decrypt_credentials: "",
        jira_credentials_extra: [],

        // coverity to jira
        defects_to_jira: false,
        defects_jira_project: '',
        defects_issue_type: 'Issue',
        defects_issue_epic: '',
        defects_extra_summary: '',
        defects_extra_labels: '',
        defects_extra_description: '',
        defects_default_assignee: '',
        defects_assignee_excluded: '',
        coverity_project_name: '',
        epic_link_filed_id: '',
        // new
        defects_assign_policy: 'author',
        defects_issue_reporter: '',
        defects_extra_watcher: '',
        defects_extra_fields: "",
        // CN3SD8, MORE_DESCRIPTION
        defects_customization: '',
        defects_summary_attachment: '',
        defects_number_limit: 0,
        defects_credentials_limit: 160,
        defects_hard_limit: 1000,
        notify_users: true,

        // build result to jira
        buildresult_to_jira: false,
        // CREATE, UPDATE
        jira_operation: "CREATE",
        jira_project: "",
        jira_issue_type: "Issue",
        jira_issue_key: "",
        jira_issue_summary: "",
        jira_issue_description: "",
        jira_issue_comment: "",
        // ADD, UPDATE:KEYWORD
        jira_issue_comment_mode: "ADD",
        jira_issue_assignee: ""
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    if (env.JENKINS_URL.indexOf("apiproxy") < 0) {
        if (config.containsKey("jira_credentials") == false || config["jira_credentials"] == "") {
            error("JIRA: jira_credentials not defined")
        }
    }
    utils.finalizeInit(stageName, config)

    return config
}

def publishJIRAIssue(jiraConfig) {
    def plainStageName = jiraConfig["plainStageName"]
    def openaiEnv = false

    if (env.PF_CODEPROMPT_RESULT && env.PF_CODETEK_COV_ANALYSIS_ADVISE) {
        if (isUnix() && env.PF_BUILD_ENV == "none") {
            utils.pyExec("covjira", jiraConfig["stageName"], "CHECK_ENV", [])
            def singularityError = fileExists ".pf-${plainStageName}/singularity_error"
            print "singularityError: ${singularityError}"
            if (singularityError == false) {
                openaiEnv = true
            }
        }
    }
    if (openaiEnv == true) {
        utils.pyExec("covjira", jiraConfig["stageName"], "PUBLISH", [], pyEnv="openai")
    }
    else {
        utils.pyExec("covjira", jiraConfig["stageName"], "PUBLISH", [])
    }
    dir (".pf-${plainStageName}") {
        utils.exportEnv()
    }
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
    def jiraConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def plainStageName = jiraConfig["plainStageName"]

    if (jiraConfig["defects_to_jira"] == true || jiraConfig["defects_to_jira"] == "true") {
        jiraConfig.buildBranches = []
        if (env.BUILD_BRANCH) {
            // deprecated: would raise concurrent problem
            // jira in parallel build
            error "JIRA under parallel build: ${env.BUILD_BRANCH}"
        }
        else {
            // check if env.PF_REMOTE_PARALLEL_BUILD defined
            // PF_REMOTE_PARALLEL_BUILD 0: remote standalone build
            // PF_REMOTE_PARALLEL_BUILD 1: remote parallel build
            if (env.PF_REMOTE_PARALLEL_BUILD) {
                def creds = []
                if (jiraConfig["decrypt_credentials"] != "") {
                    creds.add(sshUserPrivateKey(credentialsId: jiraConfig["decrypt_credentials"], keyFileVariable: 'DECRYPT_KEY'))
                }
                withCredentials(creds) {
                    if (env.JENKINS_URL.indexOf("apiproxy") >= 0) {
                        utils.pyExec("covjira", jiraConfig["stageName"], "COPY_REMOTE_ARTIFACTS", ["-d", WORKSPACE])
                    }
                    else {
                        utils.pyExec("covjira", jiraConfig["stageName"], "COPY_REMOTE_ARTIFACTS", ["-d", WORKSPACE], "python")
                    }
                    dir (".pf-${plainStageName}") {
                        utils.exportEnv()
                    }
                }

                if (env.PF_REMOTE_PARALLEL_BUILD == "1") {
                    // remoteParallelInfo.json
                    def parallelInfo = readJSON file: ".pf-${plainStageName}/remoteParallelInfo.json"
                    for (def i=0; i<parallelInfo.branches.size(); i++) {
                        jiraConfig.buildBranches << parallelInfo.branches[i]
                    }
                }
                else if (env.PF_REMOTE_PARALLEL_BUILD != "0") {
                    jiraConfig.buildBranches << env.PF_REMOTE_PARALLEL_BUILD
                }
            }
            else {
                jiraConfig.buildBranches = utils.pfParallelInfo(true)
            }
        }
        utils.updateStageConfig(jiraConfig)
    }
    if (jiraConfig["buildresult_to_jira"] == true) {
        if (env.PF_CODEPROMPT_RESULT) {
            def creds = []
            if (jiraConfig["decrypt_credentials"] != "") {
                creds.add(sshUserPrivateKey(credentialsId: jiraConfig["decrypt_credentials"], keyFileVariable: 'DECRYPT_KEY'))
            }
            withCredentials(creds) {
                if (env.JENKINS_URL.indexOf("apiproxy") >= 0) {
                    utils.pyExec("jira", jiraConfig["stageName"], "COPY_REMOTE_ARTIFACTS", ["-d", WORKSPACE])
                }
                else {
                    utils.pyExec("jira", jiraConfig["stageName"], "COPY_REMOTE_ARTIFACTS", ["-d", WORKSPACE], "python")
                }
                dir (".pf-${plainStageName}") {
                    utils.exportEnv()
                }
            }
        }
    }

    def creds = []
    if (jiraConfig["jira_credentials"] != "") {
        try {
            withCredentials([string(credentialsId: jiraConfig["jira_credentials"], variable: "JIRA_TOKEN")]) {
                print "Token credentials"
                creds = [string(credentialsId: jiraConfig["jira_credentials"], variable: "JIRA_TOKEN")]
                for (def i=0; i<jiraConfig["jira_credentials_extra"].size(); i++) {
                    creds.add(string(credentialsId: jiraConfig["jira_credentials_extra"][i], variable: "JIRA_TOKEN_${i + 1}"))
                }
            }
        }
        catch (e) {
            print "Username/password credentials"
            creds = [usernamePassword(credentialsId: jiraConfig["jira_credentials"], usernameVariable: "JIRA_USER", passwordVariable: "JIRA_PASSWORD")]
            for (def i=0; i<jiraConfig["jira_credentials_extra"].size(); i++) {
                creds.add(usernamePassword(credentialsId: jiraConfig["jira_credentials_extra"][i], usernameVariable: "JIRA_USER_${i + 1}", passwordVariable: "JIRA_PASSWORD_${i + 1}"))
            }
        }
    }

    withCredentials(creds) {
        utils.pyExec("covjira", jiraConfig["stageName"], "VAL_PROJECT_KEY", [])
        utils.pyExec("covjira", jiraConfig["stageName"], "INIT_CREDENTIALS", [])
        dir (".pf-${plainStageName}") {
            utils.exportEnv()
        }
        utils.pyExec("covjira", jiraConfig["stageName"], "FLUSH_LOG", [])
        utils.pyExec("covjira", jiraConfig["stageName"], "GET_JIRA_INFO", [])
        if (jiraConfig["defects_to_jira"] == true || jiraConfig["defects_to_jira"] == "true") {
            utils.pyExec("covjira", jiraConfig["stageName"], "GET_JIRA_EPIC", [])
            utils.pyExec("covjira", jiraConfig["stageName"], "UPDATE_EXCLUDES", [])
            utils.pyExec("covjira", jiraConfig["stageName"], "GET_JIRA_ISSUES", [])
            utils.pyExec("covjira", jiraConfig["stageName"], "GET_JIRA_COMPONENT", [])
            if (env.PF_COV_CREDENTIALS == "") {
                utils.pyExec("covjira", jiraConfig["stageName"], "DEFECTS_TO_JIRA", ["-d", WORKSPACE])
            }
            else {
                withCredentials([file(credentialsId: env.PF_COV_CREDENTIALS, variable: 'COV_AUTH_KEY')]) {
                    utils.pyExec("covjira", jiraConfig["stageName"], "DEFECTS_TO_JIRA", ["-d", WORKSPACE])
                }
            }
            utils.pyExec("covjira", jiraConfig["stageName"], "UPDATE_UNDECTED", [])
            dir (".pf-${plainStageName}") {
                utils.exportEnv()
            }
            publishJIRAIssue(jiraConfig)

            dir (".pf-${plainStageName}") {
                def publishResult = readJSON file: "publishResult.json"
                print "Update/publish status: " + publishResult
                def subTotal = 0
                def unpublishedKeys = ['unpublished_close', 'unpublished_update', 'unupdated_issue', 'unpublished_new']
                for (def key in publishResult.keySet()) {
                    if (unpublishedKeys.contains(key)) {
                        subTotal += publishResult[key].size()
                    }
                }
                if (subTotal > 0) {
                    unstable message: "${plainStageName}: incomplete publish"
                }
            }
        }
        else {
            print "defects_to_jira disabled"
        }

        if (jiraConfig["buildresult_to_jira"] == true) {
            env.JIRA_SITE = jiraConfig["site_name"]
            utils.pyExec("jira", jiraConfig["stageName"], "BUILD_TO_JIRA", [])
        }
    }
}

return this
