def init(stageName) {
    def defaultConfigs = [
        display_name: "HSM",
        enable: true,
        hsm_credential: "",
        hsm_authcode: "",
        hsm_src_files: [],
        hsm_dst_files: [],
        hsm_sha_types: [],

        scriptableParams: ["hsm_src_files", "hsm_dst_files", "hsm_sha_types"]
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def config = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    withCredentials([string(credentialsId: config["hsm_authcode"], variable: 'AUTH_CODE'),
                        usernamePassword(credentialsId: config["hsm_credential"], usernameVariable: 'AD_USER', passwordVariable: 'AD_PASSWORD')]) {
        lock ("hsmLock-${JOB_NAME}") {
            utils.pyExec("sshsign", config["stageName"], "FILE_SIGN", [])
            utils.archiveStageArtifacts(config["stageName"])
        }
    }
}

return this