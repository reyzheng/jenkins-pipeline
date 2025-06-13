def init(stageName) {
    def defaultConfigs = [
        display_name: "Gerrit-Submit",
        // COV_INFO: SUBMIT-COMMENT, COMMENT-TO-JIRA
        coverity_credentials: "",
        enable: true,
        // COV_INFO: fill coverity info. to patchset comment
        // GPT_REVIEW: generative AI reviewed comments
        comment: "",
        expression: "",
        pass_expr: ""
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    if (configs["expression"] && configs["expression"] != "") {
        def expr = evaluate(configs["expression"])
        if (expr == false) {
            print "skip ${stageName}"
            return
        }
    }

    creds = []
    if (configs["coverity_credentials"] != "") {
        creds = [file(credentialsId: configs["coverity_credentials"], variable: 'COV_AUTH_KEY')]
    }
    if (env.PF_GERRIT_CREDENTIALS) {
        print "Take global gerrit credentials " + env.PF_GERRIT_CREDENTIALS
        creds.add(sshUserPrivateKey(credentialsId: env.PF_GERRIT_CREDENTIALS, usernameVariable: 'GERRIT_USER', keyFileVariable: 'GERRIT_KEY'))
    }
    else if (env.PF_GERRIT_CREDENTIALS_MAIN && env.PF_GERRIT_CREDENTIALS_MAIN != "PF_NONE") {
        print "Take source gerrit credentials " + env.PF_GERRIT_CREDENTIALS_MAIN
        creds.add(sshUserPrivateKey(credentialsId: env.PF_GERRIT_CREDENTIALS_MAIN, usernameVariable: 'GERRIT_USER', keyFileVariable: 'GERRIT_KEY'))
    }
    withCredentials(creds) {
        utils.pyExec(configs["actionName"], configs["stageName"], "", [])
    }
    if (configs["enable"] == true && configs["pass_expr"] != "") {
        def expr = evaluate(configs["pass_expr"])
        if (expr == false) {
            extraMessage = ""
            dir (".pf-${configs['plainStageName']}") {
                def hasCovInfo = fileExists ".covinfo"
                if (hasCovInfo == true) {
                    def covInfo = readJSON file: ".covinfo"
                    if (covInfo["message"] != "Pass") {
                        extraMessage = covInfo
                    }
                }
            }
            error("Failure ${extraMessage}")
        }
    }
}

return this