def init(stageName) {
    def defaultConfigs = [
        display_name: "Wiki",
        wiki_site: "wiki.realtek.com",
        enable: true,
        credentials: "",
        operation: "DOWNLOAD_ATTACHMENT",
        space: "",
        title: "",
        attachments: "",
        dst: ""
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def stageConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    withCredentials([string(credentialsId: stageConfig["credentials"], variable: 'WIKI_TOKEN')]) {
        utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], stageConfig["operation"], [])
        //utils.archiveStageArtifacts(config["stageName"])
    }
}

return this