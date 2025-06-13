def init(stageName) {
    def defaultConfigs = [
        display_name: "gitam",
        dst: "",
        patch: "",
        push: true,

        scriptableParams: []
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    dir (configs.dst) {
        def pushCmd = ""
        if (configs.push == true) {
            def branch = utils.captureStdout('git rev-parse --abbrev-ref HEAD', isUnix())
            print "Get branch name: ${branch[0]}"
            pushCmd = "git push origin ${branch[0]}"
        }
        if (isUnix()) {
            sh """
                git am -3 < ${configs.patch}
                ${pushCmd}
            """
        }
        else {
            bat """
                git am -3 < ${configs.patch}
                ${pushCmd}
            """
        }
    }
}

return this