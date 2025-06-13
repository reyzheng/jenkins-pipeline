def init(stageName) {
    def defaultConfigs = [
        display_name: "Coverity-Setup",
        enabled: true,
        url: "http://172.21.15.146:8080",
        credentials: "",
        admin_account: "",
        user_account: "",
        triage_store: "Default Triage Store",
        project: "",
        stream: ""

        //scriptableParams: ["project", "stream"]
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    lock ("COVSETUP") {
        withCredentials([file(credentialsId: configs["credentials"], variable: 'COV_AUTH_KEY')]) {
            utils.pyExec(configs["actionName"], configs["stageName"], "", [])
        }
    }
}

return this