def init(stageName) {
    def defaultConfigs = [
        display_name: "PollSMS",
        enable: true,
        expected_cicdstatus: [0],
        polling_timeout: 60,
        polling_interval: 60,
        sms_account: "",
        sms_credentials: "",
        sms_urf_id: ""
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    if (config["sms_account"] == "") {
        config["sms_account"] = env.PF_SMS_ACCOUNT
        config["sms_credentials"] = env.PF_SMS_CREDENTIALS
    }
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def config = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def plainStageName = config["plainStageName"]

    def creds = []
    if (config["sms_credentials"] == "") {
        error("Invalid SMS token")
    }
    else {
        creds = [string(credentialsId: config["sms_credentials"], variable: 'SMS_TOKEN')]
    }
    withCredentials(creds) {
        utils.pyExec(config["actionName"], config["stageName"], "", [])
    }
    dir (".pf-${plainStageName}") {
        // export environment variables generated in py
        utils.exportEnv()
    }
}

return this
