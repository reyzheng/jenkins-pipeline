def init(stageName) {
    def utils = load "utils.groovy"
    def defaultConfigs = [
        display_name: "PollSMS",
        expected_cicdstatus: [0],
        polling_timeout: 60,
        polling_interval: 60,
        sms_account: "",
        sms_credentials: "",
        sms_urf_id: ""
    ]
    def config = utils.commonInit(stageName, defaultConfigs)

    return config
}

def func(pipelineAsCode, actionConfig, actionPreloads) {
    unstash name: "stash-script-utils"
    def utils = load "utils.groovy"

    def smsAccount
    def smsToken
    def smsURFId
    def pollingTimeout = actionConfig.polling_timeout
    def pollingInterval = actionConfig.polling_interval
    def pollingCount = (pollingTimeout * 60) / pollingInterval

    if (actionConfig.sms_account != "") {
        smsAccount = actionConfig.sms_account
        withCredentials([string(credentialsId: actionConfig.sms_credentials, variable: 'TOKEN')]) {
            smsToken = TOKEN
        }
    }
    else {
        // try release config
        def releaseConfig = pipelineAsCode.configs["release"].settings
        smsAccount = releaseConfig.release_urf_user
        withCredentials([string(credentialsId: releaseConfig.release_urf_token, variable: 'TOKEN')]) {
            smsToken = TOKEN
        }
        if (smsToken == "") {
            // try global config
            def globalConfig = pipelineAsCode.global_vars
            try {
                smsAccount = globalConfig.sms_account
                withCredentials([string(credentialsId: globalConfig.sms_credentials, variable: 'TOKEN')]) {
                    smsToken = TOKEN
                }
            }
            catch(e) {
            }
        }
    }
    if (smsToken == "") {
        error("Invalid sms token credentials")
    }
    print "Query SMS CICDStatus by release configuration: ${smsAccount}"
    if (actionConfig.sms_urf_id != "") {
        smsURFId = actionConfig.sms_urf_id
    }
    else {
        smsURFId = env.PIPELINE_AS_CODE_URF_ID
    }
    print "Query SMS CICDStatus by SMSURF_ID: ${smsURFId}"

    for (def i=0; i<pollingCount; i++) {
        def ret = utils.queryURFCICDStatus(smsAccount, smsToken, smsURFId)
        if (actionConfig.expected_cicdstatus.contains(ret)) {
            // got
            env.PIPELINE_AS_CODE_SMS_CICD_STATUS = ret
            print "Got SMS CICDStatus: ${ret}"

            return
        }
        else {
            print "Wait ${pollingInterval} seconds"
            sleep pollingInterval
        }
    }
}

return this
