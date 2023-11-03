def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        blackduckreport_projects: [],
        blackduckreport_versions: [],
        blackduckreport_token_credential: "",
        blackduckreport_dst: "bd/report",

        scriptableParams: ["blackduckreport_projects", "blackduckreport_versions"]
    ]

    def mapConfig = utils.commonInit(stageName, defaultConfigs)
    if (mapConfig["settings"]["blackduckreport_token_credential"] == "") {
        mapConfig["settings"]["blackduckreport_token_credential"] = env.PF_BD_CREDENTIALS
    }
    utils.finalizeInit(stageName, mapConfig)

    return mapConfig
}

def func(stageName) {
    def plainStageName = stageName.replaceAll("@", "at")
    def pythonExec = utils.getPython()

    def stageConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def pyCmd = "${pythonExec} ${env.PF_ROOT}/pipeline_scripts/bdreport.py -f ${env.PF_ROOT}/settings/${stageName}_config.json -w .pf-${plainStageName} -j $WORKSPACE"
    withCredentials([string(credentialsId: stageConfig["blackduckreport_token_credential"], variable: 'BD_TOKEN')]) {
        if (isUnix()) {
            sh pyCmd
        }
        else {
            bat pyCmd
        }
    }
    dir (stageConfig["blackduckreport_dst"]) {
        archiveArtifacts artifacts: "blackduck_*_components.csv"
        archiveArtifacts artifacts: "blackduck_*_security.csv"
    }
}

return this
