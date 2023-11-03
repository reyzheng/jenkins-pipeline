def init(stageName) {
    def defaultConfigs = [
        display_name: "URF-SFTP",
        dst: "",
        credentials: "",
        archive: false,
        files: []
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    withCredentials([sshUserPrivateKey(credentialsId: configs["credentials"], usernameVariable: 'MFT_USER', keyFileVariable: 'MFT_KEY')]) {
        utils.pyExec(configs["actionName"], configs["stageName"], "", [])
    }

    dir (configs["dst"]) {
        if (configs["archive"]) {
            archiveArtifacts artifacts: "**"
        }
    }
}

return this