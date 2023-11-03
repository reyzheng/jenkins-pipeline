def init(stageName) {
    def defaultConfigs = [
        dst: "",
        patch: "",
        push: true,

        scriptableParams: []
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.stashScriptedParamScripts(config.settings)

    return config
}

def func(configs) {
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