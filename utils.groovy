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
        dir ("scripts") {
            def tokens = param.split()
            stash name: "stash-${plainStageName}-params-${nonce}", includes: tokens[1]
            print "${plainStageName}: stash scripted param ${nonce}, ${tokens[1]}"
        }
    }
}

def stashScriptedParamScripts(plainStageName, stageConfigs) {
    def scriptableParams = stageConfigs.scriptableParams

    for (def key in stageConfigs.keySet()) {
        if (scriptableParams.contains(key)) {
            //print "13 test ${key} scripted, class" + stageConfigs[key].getClass()
            // scripted params may be.
            if (stageConfigs[key] instanceof java.lang.String) {
                //print "String type"
                // like repo_path: "repo"
                stashScriptedParamScript(plainStageName, stageConfigs[key], key)
            }
            else if (stageConfigs[key] instanceof net.sf.json.JSONArray || stageConfigs[key] instanceof java.util.ArrayList) {
                //print "Array type"
                // like scm_branchs: ["master"]
                for (def i=0; i<stageConfigs[key].size(); i++) {
                    stashScriptedParamScript(plainStageName, stageConfigs[key][i], "${key}-${i}")
                }
            }
            else if (stageConfigs[key] instanceof java.util.LinkedHashMap) {
                //print "Map type"
                // like parallel_parameters: { "os": ["linux", "windows", "macos"] },
                for (def paramKey in stageConfigs[key].keySet()) {
                    for (def i=0; i<stageConfigs[key][paramKey].size(); i++) {
                        stashScriptedParamScript(plainStageName, stageConfigs[key][paramKey][i], "${key}-${paramKey}-${i}")
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

def commonInit(stageName, defaultConfigs) {
    def userScripts

    def hasJsonConfig = fileExists "settings/${stageName}_config.json"
    if (hasJsonConfig == true) {
        userScripts = readJSON file: "settings/${stageName}_config.json"
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
            userScripts = load "settings/${stageName}_config.groovy"
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
    config.settings = defaultConfigs
    config.preloads = [:]
    config.preloads.stageName = stageName
    config.preloads.plainStageName = stageName.replaceAll("@", "at")
    config.preloads.actionName = extractActionName(stageName)

    return config
}

def staticInit(stageName, defaultConfigs) {
    // check json config existence or create it
    dir ("settings") {
        def hasJsonConfig = fileExists "${stageName}_config.json"
        if (hasJsonConfig == true) {
            userScripts = readJSON file: "${stageName}_config.json"
            // retrieve config from userScripts
            for (def key in defaultConfigs.keySet()) {
                if (userScripts."${key}" != null) {
                    defaultConfigs."${key}" = userScripts."${key}"
                }
            }
            if (stageName == 'post') {
                print "userScripts " + userScripts
            }
        }
        else {
            try {
                userScripts = load "${stageName}_config.groovy"
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
            }
        }
        defaultConfigs.stageName = stageName
        defaultConfigs.plainStageName = stageName.replaceAll("@", "at")
        defaultConfigs.actionName = extractActionName(stageName)
        if (defaultConfigs.actionName == "composition") {
            defaultConfigs.parallel_parameters = extractParallelParameters(defaultConfigs.parallel_parameters)
            defaultConfigs.parallel_excludes = extractParameters(defaultConfigs.parallel_excludes)
        }
        else if (defaultConfigs.actionName == "source") {
            if (env.PF_MAIN_SOURCE_STAGE) {
                env.PF_MAIN_SOURCE_STAGE += ",${defaultConfigs.stageName}"
            }
            else {
                env.PF_MAIN_SOURCE_STAGE = defaultConfigs.stageName
            }
            // copy to arr to avoid 'Scripts not permitted to use method net.sf.json.JSONArray join java.lang.String'
            def arr = []
            for (def i=0; i<defaultConfigs.scm_dsts.size(); i++) {
                arr << defaultConfigs.scm_dsts[i]
            }
            env.PF_MAIN_SOURCE_DSTS = arr.join(',')
        }
        else if (defaultConfigs.actionName == "coverity") {
            if (defaultConfigs.coverity_stream instanceof java.lang.String) {
                // TODO: tell user deprecated
                convertToList(defaultConfigs)
            }
        }
        writeJSON file: "stage-config.json", json: defaultConfigs
        stash name: "stage-configs-${defaultConfigs.plainStageName}", includes: "stage-config.json"
    }
    if (defaultConfigs.scriptableParams) {
        // stash scripted params' script file
        stashScriptedParamScripts(defaultConfigs.plainStageName, defaultConfigs)
    }
    return defaultConfigs
}

/*
def unstashScriptedParams(stageConfigs) {
    if (stageConfigs.scriptableParams) {
        def scriptableParams = stageConfigs.scriptableParams
        // TODO: refactor
        def plainStageName = stageConfigs.plainStageName
        for (def key in stageConfigs.keySet()) {
            if (scriptableParams.contains(key)) {
                // scripted params may be.
                if (stageConfigs[key] instanceof net.sf.json.JSONArray || stageConfigs[key] instanceof java.util.ArrayList) {
                    // like scm_branchs: ["master"]
                    for (def i=0; i<stageConfigs[key].size(); i++) {
                        stageConfigs[key][i] = extractScriptedParameter(stageConfigs[key][i], "stash-${plainStageName}-params-${key}-${i}")
                    }
                }
                else if (stageConfigs[key] instanceof java.util.LinkedHashMap) {
                    // like parallel_parameters: { "os": ["linux", "windows", "macos"] },
                    for (def paramKey in stageConfigs[key].keySet()) {
                        for (def i=0; i<stageConfigs[key][paramKey].size(); i++) {
                            stageConfigs[key][paramKey][i] = extractScriptedParameter(stageConfigs[key][paramKey][i], "stash-${plainStageName}-params-${key}-${paramKey}-${i}")
                        }
                    }
                }
                else {
                    // scalar variables: like string, boolean
                    // ex. repo_path: "repo"
                    stageConfigs[key] = extractScriptedParameter(stageConfigs[key], "stash-${plainStageName}-params-${key}")
                }
            }
        }
    }
}
*/

def getPython() {
	if (isUnix()) {
		def statusPython = sh script: "python --version", returnStatus: true
		def statusPython3 = sh script: "python3 --version", returnStatus: true
		if (statusPython == 0) {
			return 'python'
		}
		else if (statusPython3 == 0) {
			return 'python3'
		}
		else {
			error("Please install python")
		}
	}
	else {
		def statusPython = bat script: "python --version", returnStatus: true
		def statusPython3 = bat script: "python3 --version", returnStatus: true
		if (statusPython == 0) {
			return 'python'
		}
		else if (statusPython3 == 0) {
			return 'python3'
		}
		else {
			error("Please install python")
		}
	}
}

def pyExec(actionName, stageName) {
    def plainStageName = stageName.replaceAll("@", "at")

	unstash name: "stash-python-${plainStageName}"
    dir (".pf-configs") {
        unstash name: "stage-configs-${plainStageName}"
        //stageConfigs = readJSON file: "stage-config.json"
    }
	
	def python = utils.getPython()
	if (isUnix()) {
        sh "${python} ${actionName}.py -c .pf-configs/stage-config.json"
	}
	else {
        bat "${python} ${actionName}.py -c .pf-configs\\stage-config.json"		
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

return this