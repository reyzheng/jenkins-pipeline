def init(stageName) {
    def defaultConfigs = [
        display_name: "JIRAIssue",
        enable: true,
        key: "",
        issue: "",
        attachment: ""
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def vars = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    utils.pyExec(vars["actionName"], vars["stageName"], "", [])
}

return this