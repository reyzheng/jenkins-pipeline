def init(stageName) {
    def utils = load "utils.groovy"
    def defaultConfigs = [
        display_name: "ITSJIRA",
        events: [],
        // jira_token for sites support jira token, like OA JIRA
        jira_token: "",
        // jira_token for sites do not support jira token, like RJIRA
        jira_credentials: "",
        jira_site: "",

        scriptableParams: []
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

//def func(configsRaw) {
def func(stageName) {
    def configs = readJSON file: ".pf-all/settings/${stageName}_config.json"
    def plainStageName = configs["plainStageName"]

    def pythonExec = utils.getPython()
    def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/itsjira.py -w .pf-${plainStageName} -f .pf-all/settings/${stageName}_config.json"
    if (configs['jira_token'] != "") {
        withCredentials([string(credentialsId: configs['jira_token'], variable: 'JIRA_TOKEN')]) {
            if (isUnix()) {
                sh pyCmd
            }
            else {
                bat pyCmd
            }
        }
    }
    else {
         withCredentials([usernamePassword(credentialsId: configs["jira_credentials"], usernameVariable: 'JIRA_USER', passwordVariable: 'JIRA_TOKEN')]) {
            if (isUnix()) {
                sh pyCmd
            }
            else {
                bat pyCmd
            }
        }
    }
}

return this