def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        enable: true,
        enablement_expression: "1",
        sshsign_credential: "",
        system_account: false,
        sign_user: "",
        sshsign_authcode: "",
        sshsign_sha: [],
        sshsign_hash_algo: [],
        sshsign_padding_algo: [],
        sshsign_hex: []
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def config = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    if (config["enablement_expression"]) {
        print "Check ${config['enablement_expression']}"
        def expr = evaluate(config["enablement_expression"])
        if (expr == false) {
            print "Skip ${stageName}"
            return
        }
    }

    withCredentials([string(credentialsId: config["sshsign_authcode"], variable: 'AUTH_CODE'),
                        usernamePassword(credentialsId: config["sshsign_credential"], usernameVariable: 'AD_USER', passwordVariable: 'AD_PASSWORD')]) {
        utils.pyExec(config["actionName"], config["stageName"], "PURE_SIGN", [])
        utils.archiveStageArtifacts(config["stageName"])
    }
}

return this