def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        enable: true,
        // "inline", "file", "source", "groovy"
        types: [],
        failfast: false,
        contents: [],
        expressions: [],
        toolbox: "",

        sshcredentials: ""
    ]
    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def buildEnv(toolbox) {
    def utils = load "${PF_ROOT}/utils.groovy"
    if (toolbox != "") {
        return "singularity exec ${toolbox}"
    }
    else if (env.PF_BUILD_ENV != "none") {
        return utils.buildEnvPrefix(env.PF_BUILD_ENV, env.PF_BUILD_ENV_PARAMS)
    }
    else {
        return ""
    }
}

// actionConfig
def call(stageName, env) {
    def utils = load "${env.PF_ROOT}/utils.groovy"
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def underUnix = isUnix()
    def validScriptTypes = ["inline", "file", "source", "groovy"]
    def toolbox = buildEnv(configs["toolbox"])
    print "toolbox: ${toolbox}"

    if (configs.enable == false) {
        print "Stage ${stageName} cancelld manually"
        return
    }

    def displayName = configs["display_name"]
    if (displayName == "") {
        displayName = stageName
    }

    def reportStageName = displayName
    if (env.BUILD_BRANCH) {
        reportStageName = reportStageName + " ${env.BUILD_BRANCH}"
    }

    try {
        for (def i=0; i<configs.types.size(); i++) {
            if (validScriptTypes.contains(configs.types[i]) == false) {
                return
            }

            if (configs.expressions[i] && configs.expressions[i] != "") {
                def expr = evaluate(configs.expressions[i])
                if (expr == false) {
                    print "skip ${i}th script"
                    continue
                }
            }

            dir (".pf-${configs.plainStageName}") {
                deleteDir()
                writeFile file: "DUMMY", text: ""
            }
            if (configs.types[i] == "inline") {
                if (configs.sshcredentials == "") {
                    utils.inlineScript(configs.contents[i], underUnix, toolbox)
                }
                else {
                    sshagent(credentials: [configs.sshcredentials]) {
                        utils.inlineScript(configs.contents[i], underUnix, toolbox)
                    }
                }
            }
            else {
                if (configs.sshcredentials == "") {
                    utils.fileScript(underUnix, configs.types[i], configs.contents[i], toolbox, configs["sshcredentials"], ".pf-${configs.plainStageName}")
                }
                else {
                    sshagent(credentials: [configs.sshcredentials]) {
                        utils.fileScript(underUnix, configs.types[i], configs.contents[i], toolbox, configs["sshcredentials"], ".pf-${configs.plainStageName}")
                    }
                }
            }
            utils.archiveStageArtifacts(configs["stageName"])
            dir (".pf-${configs.plainStageName}") {
                // export environment variables generated in py
                utils.exportEnv()
            }
        }

        if (env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS") {
            env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS" += "$reportStageName SUCCESS;"
        }
        else {
            env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS" = "$reportStageName SUCCESS;"
        }
    }
    catch (e) {
        if (configs["failfast"] == true) {
            error(message: "${stageName} " + e)
        }
        unstable(message: "${stageName} is unstable " + e)
        if (env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS") {
            env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS" += "$reportStageName UNSTABLE;"
        }
        else {
            env."PIPELINE_AS_CODE_STAGE_${displayName}_RESULTS" = "$reportStageName UNSTABLE;"
        }
    }
}

return this
