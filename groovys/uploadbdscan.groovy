def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        enable: true,
        blackduck_url: "https://blackduck.rtkbf.com",
        blackduck_token_credential: "",
        scanfiles: []
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def vars = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    if (vas["enable"] == false) {
        print "Skip stage ${stageName}"
        return
    }

    dir (".pf-${plainStageName}") {
        def morefiles = []
        for (def i=0; i<vars["scanfiles"].size(); i++) {
            def scanFile = vars["scanfiles"][i]
            if (scanFile.startsWith("artifacts:")) {
                scanFile = scanFile.split(":")
                scanFile = scanFile[1].trim()
                copyArtifacts filter: scanFile, projectName: env.JOB_NAME, selector: specific(env.BUILD_NUMBER)
                def bdioFiles = findFiles(glob: '**.bdio')
                for (def bdioFile in bdioFiles) {
                    morefiles.add(bdioFile)
                }
            }
        }
        vars["morefiles"] = morefiles
    }
    writeJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json", json: vars
    withCredentials([string(credentialsId: vars["blackduck_token_credential"], variable: "BD_TOKEN")]) {
        utils.pyExec(vars["actionName"], vars["stageName"], "", [])
    }
}

return this