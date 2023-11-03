def parseUrl(url) {
    def ret = []

    // separate url and path, ssh://psp.sdlc.rd.realtek.com:29418/test/test ->
    // ret[0] ssh://psp.sdlc.rd.realtek.com:29418
    // ret[1] test/test
    def tokens = url.split("//")
    if (tokens.size() == 1) {
        // git@github.com:reyzheng/test.git
        tokens = url.split(":")
        ret << tokens[0]
        ret << tokens[1]
    }
    else {
        def protocol = tokens[0] // https: or ssh:
        def addr = tokens[1].substring(0, tokens[1].indexOf('/')) // psp.sdlc.rd.realtek.com:29418
        def path = tokens[1].substring(tokens[1].indexOf('/') + 1 , tokens[1].length()) // test/test
        ret << "${protocol}//${addr}"
        ret << path
    }

    return ret
}

def stashScriptedParamScript(plainStageName, param, nonce) {
    if (isDynamicParameter(param) == true) {
        dir (env.PF_PATH + 'scripts') {
            def tokens = param.split()
            stash name: "stash-${plainStageName}-params-${nonce}", includes: tokens[1]
            print "${plainStageName}: stash scripted param ${nonce}, ${tokens[1]}"
            return "stash-${plainStageName}-params-${nonce}"
        }
    }
}

def stashScriptedParamScripts(stageConfigs) {
    def scriptableParams = stageConfigs["scriptableParams"]
    def plainStageName = stageConfigs["plainStageName"]

    stageConfigs["stashes"] = []
    for (def key in stageConfigs.keySet()) {
        if (scriptableParams.contains(key)) {
            //print "13 test ${key} scripted, class" + stageConfigs[key].getClass()
            // scripted params may be.
            if (stageConfigs[key] instanceof java.lang.String) {
                //print "String type"
                // like repo_path: "repo"
                def stashed = stashScriptedParamScript(plainStageName, stageConfigs[key], key)
                if (stashed) {
                    stageConfigs["stashes"] << stashed
                }
            }
            else if (stageConfigs[key] instanceof net.sf.json.JSONArray || stageConfigs[key] instanceof java.util.ArrayList) {
                //print "Array type"
                // like scm_branchs: ["master"]
                for (def i=0; i<stageConfigs[key].size(); i++) {
                    def stashed = stashScriptedParamScript(plainStageName, stageConfigs[key][i], "${key}-${i}")
                    if (stashed) {
                        stageConfigs["stashes"] << stashed
                    }
                }
            }
            else if (stageConfigs[key] instanceof java.util.LinkedHashMap) {
                //print "Map type"
                // like parallel_parameters: { "os": ["linux", "windows", "macos"] },
                for (def paramKey in stageConfigs[key].keySet()) {
                    for (def i=0; i<stageConfigs[key][paramKey].size(); i++) {
                        def stashed = stashScriptedParamScript(plainStageName, stageConfigs[key][paramKey][i], "${key}-${paramKey}-${i}")
                        if (stashed) {
                            stageConfigs["stashes"] << stashed
                        }
                    }
                }
            }
        }
    }
}

def extractScriptedParameter(param, stashName) {
    def extractedParam = ""

    if (param == null) {
        extractedParam = ""
    }
    else if (isDynamicParameter(param) == true) {
        extractedParam = extractDynamicParameter(param, stashName)
    }
    else if (param instanceof java.lang.String && 
                (param.indexOf("%") >= 0 || param.indexOf("\$") >= 0)) {
        extractedParam = captureStdout("echo ${param}", isUnix())
        extractedParam = extractedParam[0]
    }
    else {
        extractedParam = param
    }

    return extractedParam
}

def unstashParameterScripts(stageConfigs) {
    if (stageConfigs.containsKey("stashes") == true) {
        for (def i=0; i<stageConfigs["stashes"].size(); i++) {
            dir ('.pf-parameters') {
                unstash name: stageConfigs["stashes"][i]
            }
        }
    }
}

def unstashPipelineFramework() {
    print "Unstash PF under "
    if (isUnix()) {
        sh "pwd"
    }
    else {
        bat "dir"
    }
    // unstash to PF_ROOT
    env.PF_ROOT = ".pf-all"
    print "env.PF_ROOT ${env.PF_ROOT}"
    dir (env.PF_ROOT) {
        deleteDir()
        unstash name: 'stash-pf-main'
        unstash name: 'stash-pf-settings'
        unstash name: 'stash-pf-user-scripts'
        unstash name: 'stash-pf-scripts'
        unstash name: 'stash-pf-coverity'
    }
}

def getStageConfig(plainStageName) {
    dir (".pf-${plainStageName}") {
        def config = readJSON file: 'stageConfig.json'
        return config
    }
}

def unstashScriptedParamScripts(plainStageName, stageConfigs, stageConfigsRet) {
    def scriptableParams = stageConfigs.scriptableParams

    for (def key in stageConfigs.keySet()) {
        if (scriptableParams.contains(key)) {
            // scripted params may be.
            if (stageConfigs[key] instanceof net.sf.json.JSONArray || stageConfigs[key] instanceof java.util.ArrayList) {
                stageConfigsRet."${key}" = []
                // like scm_branchs: ["master"]
                for (def i=0; i<stageConfigs[key].size(); i++) {
                    stageConfigsRet[key][i] = extractScriptedParameter(stageConfigs[key][i], "stash-${plainStageName}-params-${key}-${i}")
                }
            }
            else if (stageConfigs[key] instanceof java.util.LinkedHashMap) {
                stageConfigsRet."${key}" = [:]
                // like parallel_parameters: { "os": ["linux", "windows", "macos"] },
                for (def paramKey in stageConfigs[key].keySet()) {
                    for (def i=0; i<stageConfigs[key][paramKey].size(); i++) {
                        stageConfigsRet[key][paramKey][i] = extractScriptedParameter(stageConfigs[key][paramKey][i], "stash-${plainStageName}-params-${key}-${paramKey}-${i}")
                    }
                }
            }
            else {
                // scalar variables: like string, boolean
                // ex. repo_path: "repo"
                stageConfigsRet[key] = extractScriptedParameter(stageConfigs[key], "stash-${plainStageName}-params-${key}")
            }
        }
        else {
            stageConfigsRet[key] = stageConfigs[key]
        }
    }
}

def isDynamicParameter(parameter) {
    if (parameter == null || parameter == "") {
        return false
    }

    if (parameter instanceof java.lang.String) {
        def dynamicPrefixes = ["sh", "bat", "bash"]
        def tokens = parameter.split()
        if (dynamicPrefixes.contains(tokens[0])) {
            return true
        }
        else {
            return false
        }
    }

    return false
}

def extractDynamicParameter(parameter, stashName) {
    def ret = [""]
    def tokens = parameter.split()
    dir (".parameter") {
        unstash stashName
        if (parameter.startsWith("sh") || parameter.startsWith("bash")) {
            ret = captureStdout(parameter, true)
        }
        else {
            ret = captureStdout(tokens[1], false)
        }
    }
    print "utils: extracted parameter '${parameter}': '${ret[0]}'"
    return ret[0].trim()
}

// for general commands, like echo "test"
def captureStdout(command, underUnix) {
    def stdout = ""
    try {
        if (underUnix == true) {
            stdout = sh(script: command, returnStdout: true).trim()
            stdout = stdout.readLines()
        }
        else {
            //command = command.replaceAll("%", "%%")
            stdout = bat(script: command, returnStdout: true).trim()
            stdout = stdout.readLines().drop(1)
        }
    }
    catch (e) {
    }

    return stdout
}

def extractParameters(params) {
    def paramsExtracted = []

    for (def i=0; i<params.size(); i++) {
        def param = params[i]
        if (param.indexOf("\$") >= 0) {
            param = utils.captureStdout("echo ${param}", isUnix())
            if (param.size() > 0) {
                def valueSplits = param[0].split(" ")
                for (def j=0; j<valueSplits.size(); j++) {
                    paramsExtracted << valueSplits[j]
                }
            }
        }
        else {
            paramsExtracted << param
        }
    }

    return paramsExtracted
}

def extractParallelParameters(parallelParameters) {
    def parallelParametersExtracted = [:]

    if (parallelParameters.size() > 0) {
        for (def key in parallelParameters.keySet()) {
            def values = parallelParameters."${key}"
            parallelParametersExtracted."${key}" = extractParameters(values)
        }
    }
    
    return parallelParametersExtracted
}

def extractRealActionName(stageName) {
    def actionName
    def commonActions = ["config", "prebuild", "build", "postbuild", "test"]

    if (stageName.indexOf('@') < 0) {
        // build-dummy -> "build"
        actionName = stageName.split(/-/)
        actionName = actionName[0]
    }
    else {
        // composition@build-dummy -> "build"
        // composition-dummy@build-dummy -> "build"
        def stageNameTokens = stageName.split(/@/)
        actionName = stageNameTokens[1].toString().split(/-/)
        actionName = actionName[0]
    }

    if (commonActions.contains(actionName)) {
        actionName = "common_stage"
    }
    else if (actionName == "buildwithcoverity") {
        actionName = "coverity"
    }

    return actionName
}

def extractActionName(stageName) {
    def actionName

    if (stageName.indexOf('@') < 0) {
        // build-dummy -> "build"
        actionName = stageName.split(/-/)
        actionName = actionName[0]
    }
    else {
        // composition@build-dummy -> "build"
        // composition-dummy@build-dummy -> "build"
        def stageNameTokens = stageName.split(/@/)
        actionName = stageNameTokens[1].toString().split(/-/)
        actionName = actionName[0]
    }

    if (actionName == "buildwithcoverity") {
        actionName = "coverity"
    }

    return actionName
}

def finalizeInit(stageName, defaultConfigs) {
    // env.PF_PATH should have / suffix
    writeJSON file: "${env.PF_PATH}settings/${stageName}_config.json", json: defaultConfigs["settings"]
    print "PF: writeback ${env.PF_PATH}settings/${stageName}_config.json"
}

def commonInit(stageName, defaultConfigs) {
    def userScripts

    def hasJsonConfig = fileExists env.PF_PATH + "settings/${stageName}_config.json"
    if (hasJsonConfig == true) {
        userScripts = readJSON file: env.PF_PATH + "settings/${stageName}_config.json"
        // retrieve config from userScripts
        for (def key in defaultConfigs.keySet()) {
            if (userScripts."${key}" != null) {
                defaultConfigs."${key}" = userScripts."${key}"
            }
            else {
                // not defined in userScripts
            }
        }
    }
    else {
        try {
            userScripts = load env.PF_PATH + "settings/${stageName}_config.groovy"
            // retrieve config from userScripts
            for (def key in defaultConfigs.keySet()) {
                try {
                    defaultConfigs."${key}" = userScripts."${key}"
                }
                catch (e) {
                    // not defined in userScripts
                }
            }
        }
        catch (e) {
            print "$stageName not configured " + e
            return null
        }
    }

    def config = [:]
    config['settings'] = defaultConfigs
    config['settings']['stageName'] = stageName
    config['settings']['plainStageName'] = stageName.replaceAll("@", "at")
    config['settings']['actionName'] = extractActionName(stageName)
    config.preloads = [:]
    config.preloads.stageName = stageName
    config.preloads.plainStageName = stageName.replaceAll("@", "at")
    config.preloads.actionName = extractActionName(stageName)

    return config
}

def decorateCommand(command) {
    if (env.PF_BUILD_ENV) {
        def delimiter = env.PF_BUILD_ENV.indexOf(":")
        def buildEnv = env.PF_BUILD_ENV.substring(0, delimiter)
        def buildImage = env.PF_BUILD_ENV.substring(delimiter + 1)
        print("buildEnv ${buildEnv}")
        print("buildImage ${buildImage}")
        if (buildEnv == "docker") {
            // --user \$(id -u):\$(id -g) would cause non-existed user error
            command = "docker run --rm --env-file <(env) -v ${WORKSPACE}:${WORKSPACE} -w ${WORKSPACE} ${buildImage} ${command}"
        }
        else if (buildEnv == "singularity") {
            def buildImages = buildImage.split(",")
            def overlay = ""
            if (buildImages.size() > 1) {
                overlay = "--overlay ${buildImages[1]}"
            }
            command = "singularity exec ${overlay} -B ${WORKSPACE}:${WORKSPACE} -H ${WORKSPACE} ${buildImages[0]} ${command}"
        }
    }

    return command
}

def getPython() {
    def testPython = decorateCommand("python --version")
    def testPython3 = decorateCommand("python3 --version")
	if (isUnix()) {
		def statusPython = sh script: testPython, returnStatus: true
		def statusPython3 = sh script: testPython3, returnStatus: true
		if (statusPython3 == 0) {
			return 'python3'
		}
		else if (statusPython == 0) {
			return 'python'
		}
		else {
            error("Please install python or switch to stable-pyless branch")
		}
	}
	else {
		def statusPython = bat script: testPython, returnStatus: true
		def statusPython3 = bat script: testPython3, returnStatus: true
		if (statusPython == 0) {
			return 'python'
		}
		else if (statusPython3 == 0) {
			return 'python3'
		}
		else {
            error("Please install python or switch to stable-pyless branch")
		}
	}
}

def pyExec(actionName, stageName, command, args) {
    def plainStageName = stageName.replaceAll("@", "at")

    def pythonExec = getPython()
    def pyCmd = decorateCommand("${pythonExec} ${env.PF_ROOT}/pipeline_scripts/${actionName}.py -f ${env.PF_ROOT}/settings/${stageName}_config.json -w .pf-${plainStageName}")
    if (command != "") {
        pyCmd = "${pyCmd} -c ${command}"
    }
    for (def i=0; i<args.size(); ) {
        pyCmd = "${pyCmd} ${args[i]} ${args[i + 1]}"
        i += 2
    }
    if (isUnix()) {
        sh pyCmd
    }
    else {
        bat pyCmd
    }
}

def exportEnv() {
    def gitExists = fileExists 'env'
    if (gitExists == true) {
        def fp = readFile 'env'
        def lines = fp.readLines()
        for (def line in lines) {
            def tokens = line.split("=")
            if (tokens.size() > 1) {
                env."${tokens[0]}" = tokens[1]
                print("exportEnv ${tokens[0]} ${tokens[1]}")
            }
            else {
                env."${tokens[0]}" = ""
                print("exportEnv ${tokens[0]} ''")
            }
        }
    }
}

def loadAction(actionName) {
    def commonActions = ["config", "prebuild", "build", "postbuild", "test"]
    def action = null

    dir (".pipeline-actions") {
        unstash "stash-actions-${actionName}"
        if (commonActions.contains(actionName)) {
            action = load("common_stage.groovy")
        }
        else {
            action = load("${actionName}.groovy")
        }
    }

    return action
}

def queryURFCICDStatus(account, token, smsId) {
    def ret = -1
    def postParam = "Account=${account}&Token=${token}&Id=${smsId}"
    def cmd = "curl -d \"${postParam}\" -o .pf-queryurf.json https://sms.realtek.com/RestApi/ReleaseStatus"
    try {
        if (isUnix()) {
            sh cmd
        }
        else {
            bat cmd
        }
        def jsonObject = readJSON file: '.pf-queryurf.json'
        ret = jsonObject.CICDStatus.toInteger()
    }
    catch (e) {
        print e
    }

    print "Query SMS CICDStatus: ${ret}"
    return ret
}

return this
