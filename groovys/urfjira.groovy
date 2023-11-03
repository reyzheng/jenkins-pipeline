def init(stageName) {
    def defaultConfigs = [
        display_name: "URF-JIRA",
        enable: true,

        jira_site: 'jira.realtek.com',
        jira_credentials: '',
        jira_project: '',
        issue_assignee: '',
        sms_account: '',
        sms_token: '',
        release_jenkins_user: '',
        release_jenkins_token: '',
        // available options: 
        //     RSCAT -> software quality index
        //     COVREPORT -> coverity report
        //     BDREPORT -> blackduck report
        artifacts: [],
        // coverity/bd project name, necessary if
        //     "release" is not present at prior stages
        //     RSCAT, COVREPORT, BDREPORT is configured
        report_name: "",

        scriptableParams: []
    ]

    def stageConfig = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, stageConfig)

    return stageConfig
}

def func(stageName) {
    def stageConfig = readJSON file: ".pf-all/settings/${stageName}_config.json"
    def plainStageName = stageConfig["plainStageName"]

    creds = [string(credentialsId: stageConfig["sms_token"], variable: 'SMS_TOKEN'),
                string(credentialsId: stageConfig["jira_credentials"], variable: 'JIRA_TOKEN')]
    if (stageConfig["release_jenkins_token"] != "") {
        creds += [string(credentialsId: stageConfig["release_jenkins_token"], variable: 'RELEASE_JENKINS_TOKEN')]
    }
    withCredentials(creds) {
        utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], "", ["-j", WORKSPACE])
    }
}

return this