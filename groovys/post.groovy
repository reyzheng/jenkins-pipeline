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
    def hasPostJson = fileExists "settings/post_config.json"
    if (hasPostGroovy || hasPostJson) {
        config = utils.commonInit("post", defaultConfigs)
    }
    else {
        config = utils.commonInit("global", defaultConfigs)
    }
    config.preloads.actionName = "post"
    def ite
    for (ite=0; ite<config.settings.post_scripts_type.size(); ite++) {
        if (config.settings.post_scripts_type[ite].trim() == "") {
            continue
        }
        if (config.settings.post_scripts_type[ite] == "inline" || 
            config.settings.post_scripts_type[ite] == "action") {
        }
        else {
            dir ('scripts') {
                stash name: "pf-post-scripts-${ite}", includes: config.settings.post_scripts[ite]
            }
        }
    }
    // load email body
    if (config.settings.mail_body.trim() != "") {
        dir ('scripts') {
            stash name: "pf-post-mail-body", includes: config.settings.mail_body
            //config.preloads.mail_body = readFile(file: "scripts/" + )
        }
    }

    return config
}

def execute(pipelineAsCode, postConfig, i) {
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
        unstash name: "pf-post-scripts-${i}"
        def dstFile = postConfig.post_scripts[i]
        
        if (postConfig.post_scripts_type[i] == "source") {
            sh ". " + dstFile
        }
        else if (postConfig.post_scripts_type[i] == "groovy") {
            def externalMethod = load(dstFile)
            externalMethod.func()
        }
        else if (postConfig.post_scripts_type[i] == "file") {
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
