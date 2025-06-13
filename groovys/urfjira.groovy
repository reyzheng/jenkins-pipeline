def init(stageName) {
    def defaultConfigs = [
        display_name: "URF-JIRA",
        enable: true,

        jira_site: 'jira.realtek.com',
        jira_credentials: '',
        jira_project: '',
        issue_assignee: '',
        defects_extra_fields: "{}",
        sms_account: '',
        sms_token: '',
        sms_ftp_key: '',
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
        post_jira: true,
        waiting_issue_status: "",

        staticParams: ["defects_extra_fields"]
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
    if (stageConfig["sms_ftp_key"] != "") {
        creds += [sshUserPrivateKey(credentialsId: stageConfig["sms_ftp_key"], usernameVariable: 'MFT_USER', keyFileVariable: 'MFT_KEY')]
    }
    withCredentials(creds) {
        utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], "", ["-j", WORKSPACE])
        utils.archiveStageArtifacts(stageConfig["stageName"])
        dir (".pf-${plainStageName}") {
            // export environment variables generated in py
            utils.exportEnv()
        }
    }
}

return this