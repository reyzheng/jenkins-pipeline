def init(stageName) {
    def defaultConfigs = [
        display_name: "PureSign",
        enable: true,
        enablement_expression: "1",
        dashboard_credential: "",

        sign_algo: "",
        // Data encode, option: UTF-8, MS950, ISO-8859-1 | default: UTF-8
        encode: "UTF-8",
        // Hash algo, option: 1=MD5, 2=SHA1, 3=SHA256, 4=SHA384, 5=SHA512 | default: 3
        hash_algo: "SHA256",
        // Padding algo, option: 1=no padding, 2=p1, 3=p1 oaep, 4=p1 pss | default: 4
        padding_algo: "p1 pss",
        // accept: file containing data to be signed
        sign_datas: [],
        hook_jenkins_job: "",
        hook_jenkins_token: ""
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    if (configs["enablement_expression"]) {
        print "Check ${configs['enablement_expression']}"
        def expr = evaluate(configs["enablement_expression"])
        if (expr == false) {
            print "Skip ${stageName}"
            return
        }
    }

    withCredentials([usernamePassword(credentialsId: configs["dashboard_credential"], usernameVariable: 'DASHBOARD_USER', passwordVariable: 'DASHBOARD_PASSWORD')]) {
        utils.pyExec(configs["actionName"], configs["stageName"], "", [])
        utils.archiveStageArtifacts(configs["stageName"])
    }
}

return this