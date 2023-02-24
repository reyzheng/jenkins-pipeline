def init() {
    def utils = load "utils.groovy"

    def defaultConfigs = [
        post_scripts_condition: [],
        post_scripts_type: [],
        post_scripts: [],
        mail_enabled: false,
        mail_conditions: ["always"],
        mail_subject: "",
        mail_body: "",
        mail_recipient: ""
    ]

    def config
    def hasPostGroovy = fileExists "settings/post_config.groovy"
    def hasPostJson = fileExists "settings/post_config.groovy"
    if (hasPostGroovy || hasPostJson) {
        config = utils.commonInit("post", defaultConfigs)
    }
    else {
        config = utils.commonInit("global", defaultConfigs)
    }
    config.preloads.actionName = "post"
    config.preloads.scriptTypes = config.settings.post_scripts_type
    config.preloads.scripts = config.settings.post_scripts
    def ite
    for (ite=0; ite<config.preloads.scriptTypes.size(); ite++) {
        if (config.preloads.scriptTypes[ite].trim() == "") {
            continue
        }
        if (config.preloads.scriptTypes[ite] == "inline" || 
            config.preloads.scriptTypes[ite] == "action") {
        }
        else {
            config.preloads.scripts[ite] = readFile(file: "scripts/" + config.preloads.scripts[ite])
        }
    }

    // load email body
    if (config.settings.mail_body.trim() != "") {
        config.preloads.mail_body = readFile(file: "scripts/" + config.settings.mail_body)
    }

    return config
}

def execute(pipelineAsCode, postConfig, expandConfig, i) {
    if (postConfig.post_scripts_type[i] == "inline") {
        if (isUnix() == true) {
            sh postConfig.post_scripts[i]
        }
        else {
            bat postConfig.post_scripts[i]
        }
    }
    else if (postConfig.post_scripts_type[i] == "action") {
        unstash name: "stash-script-utils"
        def utils = load "utils.groovy"

        def actionName = postConfig.post_scripts[i]
        def action = utils.loadAction(actionName)
        action.func(pipelineAsCode, pipelineAsCode.configs[actionName].settings, pipelineAsCode.configs[actionName].preloads)
    }
    else {
        // write to a temp file in workspace
        def dstFileName = "script-" + expandConfig.actionName + "-" + currentBuild.startTimeInMillis
        def dstFile
        if (isUnix() == true) {
            dstFile = env.WORKSPACE + "/" + dstFileName
        }
        else {
            dstFile = env.WORKSPACE + "\\" + dstFileName
        }
        writeFile(file: dstFile , text: expandConfig.scripts[i])
        
        if (expandConfig.scriptTypes[i] == "source") {
            sh ". " + dstFile
        }
        else if (expandConfig.scriptTypes[i] == "groovy") {
            def externalMethod = load(dstFile)
            externalMethod.func()
        }
        else if (expandConfig.scriptTypes[i] == "file") {
            if (isUnix() == true) {
                sh "sh '${dstFile}'"
            }
            else {
                // rename to .bat for windows batch
                bat "move /y \"$dstFile\" \"${dstFile}.bat\""
                bat "\"${dstFile}.bat\""
            }
        }
    }
}

return this
