def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        blackduckreport_projects: [],
        blackduckreport_versions: [],
        sms_token: "",
        release_urf_user: "",
        blackduckreport_token_credential: "",
        blackduckreport_dst: "bd/report",

        scriptableParams: ["blackduckreport_projects", "blackduckreport_versions"]
    ]

    def mapConfig = utils.commonInit(stageName, defaultConfigs)
    if (mapConfig["blackduckreport_token_credential"] == "") {
        mapConfig["blackduckreport_token_credential"] = env.PF_BD_CREDENTIALS
    }
    utils.finalizeInit(stageName, mapConfig)

    return mapConfig
}

def func(stageName) {
    def plainStageName = stageName.replaceAll("@", "at")
    def pythonExec = utils.getPython()

    def stageConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def pyCmd = "${pythonExec} ${env.PF_ROOT}/pipeline_scripts/bdreport.py -f ${env.PF_ROOT}/settings/${stageName}_config.json -w .pf-${plainStageName} -j $WORKSPACE"
    def creds = []
    if (stageConfig["sms_token"] != "") {
        creds = [string(credentialsId: stageConfig["sms_token"], variable: 'SMS_TOKEN')]
    }
    else {
        creds = [string(credentialsId: stageConfig["blackduckreport_token_credential"], variable: 'BD_TOKEN')]
    }
    withCredentials(creds) {
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
