def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        // coverity_report_toolbox deprecated
        coverity_report_toolbox: "",
        coverity_report_toolpath: "",
        coverity_report_config: "",
        coverity_report_latest_snapshot: false,
        coverity_report_projects: [],
        coverity_report_key_credential: "",
        coverity_report_dst: "cov/report",
        coverity_report_ignored: false,

        scriptableParams: ["coverity_report_projects"]
    ]

    def mapConfig = utils.commonInit(stageName, defaultConfigs)
    if (mapConfig["coverity_report_key_credential"] == "") {
        mapConfig["coverity_report_key_credential"] = env.PF_COV_CREDENTIALS
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
    def stageConfig = readJSON file: ".pf-all/settings/${stageName}_config.json"
    withCredentials([file(credentialsId: stageConfig["coverity_report_key_credential"], variable: 'COV_AUTH_KEY')]) {
        utils.pyExec("covreport", stageConfig["stageName"], "", ["-j", WORKSPACE])
    }

    postProcessCoverityReport(".pf-${plainStageName}", stageConfig["coverity_report_dst"])
}

return this
