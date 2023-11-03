def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        enabled: true,
        group: "",
        files: [],
        bdba_credentials: ""
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    withCredentials([string(credentialsId: config["bdba_credentials"], variable: 'BDBA_TOKEN')]) {
        utils.pyExec(configs["actionName"], configs["stageName"], "", [])
    }
}

return this