// compare defects between two coverity snapshots
// store comparison result to env."${stageName}_NEW_DEFECTS"

def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        host: "172.21.15.146",
        port: "8080",
        credentials: "",
        project: "",
        snaphots: [],
        html_report: true,

        scriptableParams: ["project", "snaphots"]
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    withCredentials([file(credentialsId: configs["credentials"], variable: 'COV_AUTH_KEY')]) {
        utils.pyExec(configs["actionName"], configs["stageName"], "", [])
    }

    dir (".pf-${configs.plainStageName}") {
        // export environment variables generated in py
        utils.exportEnv()
        if (configs.html_report == true) {
            publishHTML (target : [allowMissing: false,
                alwaysLinkToLastBuild: true,
                keepAll: true,
                reportDir: 'covcomp-reports',
                reportFiles: 'myreport.html',
                reportName: 'COVCOMP Reports',
                reportTitles: "${configs.plainStageName} Report"])
        }
    }
}

return this