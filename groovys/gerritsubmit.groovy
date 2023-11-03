def init(stageName) {
    def defaultConfigs = [
        display_name: "Gerrit-Submit",
        // SUBMIT-COMMENT, COMMENT-TO-JIRA
        coverity_credentials: "",
        enable: true,
        comment: "",
        pass_expr: "",

        scriptableParams: ["comment"]
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)
    if (! env.GERRIT_HOST) {
        error("Invalid GERRIT trigger")
    }

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    creds = []
    if (configs["coverity_credentials"] != "") {
        creds = [file(credentialsId: configs["coverity_credentials"], variable: 'COV_AUTH_KEY')]
    }
    withCredentials(creds) {
        utils.pyExec(configs["actionName"], configs["stageName"], "", [])
    }
    if (configs["pass_expr"] != "") {
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