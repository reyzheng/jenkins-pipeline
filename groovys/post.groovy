def init() {
    def defaultConfigs = [
        post_scripts_condition: [],
        post_scripts_type: [],
        post_scripts: [],
        mail_enabled: false,
        mail_conditions: ["always"],
        mail_subject: "",
        mail_body: "",
        mail_attachment: "",
        mail_recipient: ""
    ]

    def config
    def hasPostGroovy = fileExists env.PF_PATH + "settings/post_config.groovy"
    def hasPostJson = fileExists env.PF_PATH + "settings/post_config.json"
    if (hasPostGroovy || hasPostJson) {
        config = utils.commonInit("post", defaultConfigs)
    }
    else {
        config = utils.commonInit("global", defaultConfigs)
    }
    utils.finalizeInit("post", config)

    return config
}

def sendEmail(postConfig) {
    if (postConfig.mail_enabled == true) {
        def emailbody = """${currentBuild.result}: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':
                        Check console output at ${env.BUILD_URL}"""
        if (postConfig["mail_body"] != "") {
            if (postConfig["mail_body"].endsWith('.html')) {
                emailbody = readFile postConfig["mail_body"]
            }
            else {
                def isGroovyScript = fileExists "${env.PF_ROOT}/scripts/${postConfig['mail_body']}"
                if (isGroovyScript == true) {
                    def externalMailMethod = load("${env.PF_ROOT}/scripts/${postConfig['mail_body']}")
                    emailbody = externalMailMethod.func()
                }
                else {
                    emailbody = postConfig["mail_body"]
                }
            }
        }

        def mailSubject = postConfig.mail_subject
        if (postConfig.mail_subject == "") {
            mailSubject = "${currentBuild.result}: Job '${env.JOB_NAME} [Build ${env.BUILD_NUMBER}]'"
        }
        if (postConfig["mail_body"].endsWith('.html')) {
            print "sendEmail: HTML email ${postConfig['mail_body']}"
            emailext (
                subject: mailSubject,
                attachmentsPattern: postConfig["mail_attachment"],
                body: emailbody,
                to: "${postConfig.mail_recipient}",
                mimeType: 'text/html'
            )
        }
        else {
            emailext (
                subject: mailSubject,
                attachmentsPattern: postConfig["mail_attachment"],
                body: emailbody,
                to: "${postConfig.mail_recipient}"
                //recipientProviders: [[$class: 'DevelopersRecipientProvider']]
            )
        }
    }
}

def execute(pipelineAsCode, postStatus) {
    // export .pf_build_info
    def hasBuildInfo = fileExists ".pf_build_info"
    if (hasBuildInfo == true) {
        def fpBuildIndo = readFile ".pf_build_info"
        def buildInfoLines = fpBuildIndo.readLines()
        for (buildInfoLine in buildInfoLines) {
            if (buildInfoLine != "") {
                def tokens = buildInfoLine.split("=")
                if (tokens[0] == "BUILD_NAME") {
                    currentBuild.displayName = tokens[1]
                    print "set currentBuild.displayName ${tokens[1]}"
                }
                else if (tokens[0] == "BUILD_DESCRIPTION") {
                    currentBuild.description = tokens[1]
                    print "set currentBuild.description ${tokens[1]}"
                }
            }
        }
    }

    env.PF_POST_STAGE = "1"
    def underUnix = isUnix()
    def pythonExec = utils.getPython()
    def translateCmd = "${pythonExec} ${env.PF_ROOT}/pipeline_scripts/utils.py -f ${env.PF_ROOT}/settings/post_config.json -c TRANSLATE_CONFIG"
    if (underUnix) {
        sh translateCmd
    }
    else {
        bat translateCmd
    }

    def postConfig = readJSON file: "${env.PF_ROOT}/settings/post_config.json"
    //print "post execute: ${postStatus}"
    for (def i=0; i<postConfig["post_scripts_condition"].size(); i++) {
        if (postConfig["post_scripts_condition"][i].indexOf(postStatus) < 0) {
            print "skip post condition ${postStatus}"
            continue
        }
        if (postConfig.post_scripts_type[i] == "inline") {
            utils.inlineScript(postConfig.post_scripts[i], underUnix, "")
        }
        else if (postConfig.post_scripts_type[i] == "action") {
            def coreAction = true
            def stageName = postConfig["post_scripts"][i]
            def actionName = utils.extractActionName(stageName)
            def action
            try {
                print "post: load core action ${actionName}"
                action = utils.loadCoreAction(env.PF_ROOT, actionName)
            }
            catch (e) {
                print "post: load user action ${actionName}"
                coreAction = false
                action = utils.loadUserAction(env.PF_ROOT, actionName)
            }
            // TODO:
            // coreAction: action.func(stageName)
            // userAction: action.func() or action.func(modules, stageConfig, stagePreloads)
            if (coreAction == true) {
                action.func(stageName)
            }
            else {
                try {
                    action.func(pipelineAsCode, pipelineAsCode.configs[actionName])
                }
                catch (e) {
                    action.func()
                }
            }
        }
        else {
            utils.fileScript(underUnix, postConfig.post_scripts_type[i], postConfig.post_scripts[i], "", "", ".pf-post")
        }
    }

    if (postConfig["mail_conditions"].contains(postStatus)) {
        sendEmail(postConfig)
    }
}

return this
