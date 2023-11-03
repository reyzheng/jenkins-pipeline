def init(stageName) {
    def defaultConfigs = [
        display_name: "BlackduckToJIRA",
        enable: true,

        jira_site: '',
        jira_credentials: '',
        jira_project: '',
        issue_assignee: '',
        // available options: snippets, components
        bdjira_rules: "snippets",
        
        // seperated by comma
        blackduck_url: "https://blackduck.rtkbf.com",
        blackduck_token: "",
        blackduck_project: "",
        blackduck_version: "",
        operation: "CREATE_ISSUES",

        scriptableParams: []
    ]

    def stageConfig = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, stageConfig)

    return stageConfig
}

def func(stageName) {
    def stageConfig = readJSON file: ".pf-all/settings/${stageName}_config.json"
    def plainStageName = stageConfig["plainStageName"]


    args = ['-j', WORKSPACE]
    if (stageConfig["operation"] == "PUBLISH_ISSUES") {
        def tokenCredentials = false
        try {
            withCredentials([usernamePassword(credentialsId: stageConfig["jira_credentials"], usernameVariable: 'JIRA_USER', passwordVariable: 'JIRA_PASSWORD')]) {
                print "Username/password jira credentials"
            }
        }
        catch (e) {
            print "Token jira credentials"
            tokenCredentials = true
        }

        if (tokenCredentials == true) {
            withCredentials([string(credentialsId: stageConfig["jira_credentials"], variable: 'JIRA_TOKEN')]) {
                utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], "COPY_REMOTE_ARTIFACTS", args)
                utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], stageConfig["operation"], args)
            }
        }
        else {
            withCredentials([usernamePassword(credentialsId: stageConfig["jira_credentials"], usernameVariable: 'JIRA_USER', passwordVariable: 'JIRA_PASSWORD')]) {
                utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], "COPY_REMOTE_ARTIFACTS", args)
                utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], stageConfig["operation"], args)
            }
        }
    }
    else if (stageConfig["operation"] == "CREATE_ISSUES") {
        withCredentials([string(credentialsId: stageConfig["blackduck_token"], variable: 'BD_TOKEN')]) {
            utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], stageConfig["operation"], args)
        }
        dir (".pf-${plainStageName}") {
            archiveArtifacts artifacts: "bdIssues.json", allowEmptyArchive: true
        }
    }
}

return this