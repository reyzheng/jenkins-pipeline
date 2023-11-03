def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        // coverity_report_toolbox deprecated
        coverity_report_toolbox: "",
        coverity_report_toolpath: "",
        coverity_report_config: "",
        coverity_report_projects: [],
        coverity_report_key_credential: "",
        coverity_report_dst: "cov/report",
        coverity_report_ignored: false,

        scriptableParams: ["coverity_report_projects"]
    ]

    def mapConfig = utils.commonInit(stageName, defaultConfigs)
    if (mapConfig["settings"]["coverity_report_key_credential"] == "") {
        mapConfig["settings"]["coverity_report_key_credential"] = env.PF_COV_CREDENTIALS
    }
    utils.finalizeInit(stageName, mapConfig)

    return mapConfig
}

def postProcessCoverityReport(workDir, dst) {
    def projects = []
    dir (workDir) {
        projects = readJSON file: 'projects'
    }
    // archive artifacts
    dir (dst) {
        for (def coverityProject in projects) {
            archiveArtifacts artifacts: "coverity_${coverityProject}_*.pdf"
            archiveArtifacts artifacts: "coverity_${coverityProject}_*.xml"
        }
    }
}

def func(stageName) {
    def plainStageName = stageName.replaceAll("@", "at")
    def pythonExec = utils.getPython()

    // TODO: postProcessCoverityReport
    def pyCmd = "${pythonExec} ${env.PF_ROOT}/pipeline_scripts/covreport.py -f ${env.PF_ROOT}/settings/${stageName}_config.json -w .pf-${plainStageName} -j $WORKSPACE"

    def stageConfig = readJSON file: ".pf-all/settings/${stageName}_config.json"
    withCredentials([file(credentialsId: stageConfig["coverity_report_key_credential"], variable: 'COV_AUTH_KEY')]) {
        if (isUnix()) {
            sh pyCmd
        }
        else {
            bat pyCmd
        }
    }

    postProcessCoverityReport(".pf-${plainStageName}", stageConfig["coverity_report_dst"])
}

return this