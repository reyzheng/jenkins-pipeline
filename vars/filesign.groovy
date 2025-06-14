def init(stageName) {
    def defaultConfigs = [
        display_name: "FileSign",
        enable: true,
        dashboard_credential: "",
        sign_algo: "20230619_MSSIGN_SHA256",
        // Regular expression pattern
        src_files: [],
        dst_files: [],

        // download file or wait approve
        download: true,
        hook_jenkins_job: "",
        hook_jenkins_token: ""
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    withCredentials([usernamePassword(credentialsId: configs["dashboard_credential"], usernameVariable: 'DASHBOARD_USER', passwordVariable: 'DASHBOARD_PASSWORD')]) {
        utils.pyExec(configs["actionName"], configs["stageName"], "", [])
        utils.archiveStageArtifacts(configs["stageName"])
    }
}

return this