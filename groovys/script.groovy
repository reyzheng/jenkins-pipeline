def init(stageName) {
    def utils = load "utils.groovy"
    //def actionName = utils.extractActionName(stageName)

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
    def config = utils.commonInit(stageName, defaultConfigs)
    config.settings.has_stashes = false

    if (config.settings.enable == true) {
        def filesToStash = []
        for (def i=0; i<config.settings.types.size(); i++) {
            if (config.settings.types[i] != "inline") {
                filesToStash << config.settings.contents[i]
            }
        }
        if (filesToStash.size() > 0) {
            config.settings.has_stashes = true
            dir (env.PF_PATH + 'scripts') {
                stash name: "stash-script-${config.preloads.plainStageName}", includes: filesToStash.join(",")
            }
        }
    }

    return config
}

def shellScript(underUnix, dstFile, toolbox) {
    if (dstFile.endsWith(".py")) {
        def pythonExec = utils.getPython()
        if (underUnix == true) {
            sh "${pythonExec} ${dstFile}"
        }
        else {
            bat "${pythonExec} ${dstFile}"
        }
        return
    }

    if (underUnix == true) {
        if (toolbox != "") {
            toolbox = "singularity exec ${toolbox} "
        }
        def statusCode = sh script: "${toolbox}bash", returnStatus: true
        if (statusCode == 0) {
            sh "${toolbox}bash -xe '${dstFile}'"
        }
        else {
            sh "${toolbox}sh -xe '${dstFile}'"
        }
    }
    else {
        bat "\"${dstFile}\""
    }
}

def shellCommand(command, underUnix, toolbox) {
    if (underUnix == true) {
        if (toolbox != "") {
            toolbox = "singularity exec ${toolbox} "
        }
        sh toolbox + command
    }
    else {
        bat command
    }
}

// actionConfig
def func(pipelineAsCode, configs, preloads) {
    def underUnix = isUnix()
    def validScriptTypes = ["inline", "file", "source", "groovy"]

    if (configs.enable == false) {
        print "Stage ${preloads.stageName} cancelld manually"
        return
    }

    def stageName = configs.display_name
    if (stageName == "") {
        stageName = preloads.stageName
    }

    def reportStageName = stageName
    if (env.BUILD_BRANCH) {
        reportStageName = reportStageName + " ${env.BUILD_BRANCH}"
    }

    try {
        if (configs.has_stashes == true) {
            dir ('.script') {
                unstash "stash-script-${preloads.plainStageName}"
            }
        }
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

            if (configs.types[i] == "inline") {
                if (configs.sshcredentials == "") {
                    shellCommand(configs.contents[i], underUnix, configs["toolbox"])
                }
                else {
                    sshagent(credentials: [configs.sshcredentials]) {
                        shellCommand(configs.contents[i], underUnix, configs["toolbox"])
                    }
                }
            }
            else {
                def dstFile
                if (underUnix == true) {
                    dstFile = ".script/${configs.contents[i]}"
                }
                else {
                    dstFile = ".script\\${configs.contents[i]}"
                }
                if (configs.types[i] == "source") {
                    // TODO: support configs.types[i] == "." for sh/dash
                    // notice: shebang should be written at first line
                    sh """#!/bin/bash
                        mypwd=\$PWD
                        printenv > .private-source-before
                        . ${dstFile}
                        cd \$mypwd
                        printenv > .private-source-after
                    """
                    def lines = sh(script: "diff -u .private-source-before .private-source-after | grep -E '^\\+'", returnStdout: true).trim()
                    lines = lines.readLines().drop(1) // drop first line
                    for (def line in lines) {
                        if (line.startsWith("+")) {
                            def tokens = line.split("=")
                            if (tokens[0] == "+_" || tokens[0] == "+OLDPWD") {
                                // skip self (printenv), OLDPWD
                            }
                            else {
                                def varname = tokens[0].substring(1, tokens[0].length())
                                def varvalue = tokens[1]

                                // Note: BUILD_BRANCH prefix should be add to variable name,
                                // or redundant variables will be declared
                                if (env.BUILD_BRANCH != null) {
                                    if (varname.startsWith("PIPELINEGLOBAL_")) {
                                        varname = varname.substring(15)
                                        print "Export general pipeline env. variables(aux.): ${varname} ${varvalue}"
                                        env."$varname" = varvalue
                                    }
                                    varname = "BR${env.BUILD_BRANCH}_${varname}"
                                    print "Export parallel-build pipeline env. variables: ${varname} ${varvalue}"
                                    env."$varname" = varvalue
                                }
                                else {
                                    print "Export general pipeline env. variables: ${varname} ${varvalue}"
                                    env."$varname" = varvalue
                                }
                            }
                        }
                    }
                }
                else if (configs.types[i] == "groovy") {
                    def externalMethod = load(dstFile)
                    externalMethod.func()
                }
                else if (configs.types[i] == "file") {
                    if (configs.sshcredentials == "") {
                        shellScript(underUnix, dstFile, configs["toolbox"])
                    }
                    else {
                        sshagent(credentials: [configs.sshcredentials]) {
                            shellScript(underUnix, dstFile, configs["toolbox"])
                        }
                    }
                }
            }
        }

        if (env."PIPELINE_AS_CODE_STAGE_${stageName}_RESULTS") {
            env."PIPELINE_AS_CODE_STAGE_${stageName}_RESULTS" += "$reportStageName SUCCESS;"
        }
        else {
            env."PIPELINE_AS_CODE_STAGE_${stageName}_RESULTS" = "$reportStageName SUCCESS;"
        }
    }
    catch (e) {
        if (configs["failfast"] == true) {
            error(message: "${configs.stageName} " + e)
        }
        unstable(message: "${preloads.stageName} is unstable " + e)
        if (env."PIPELINE_AS_CODE_STAGE_${stageName}_RESULTS") {
            env."PIPELINE_AS_CODE_STAGE_${stageName}_RESULTS" += "$reportStageName UNSTABLE;"
        }
        else {
            env."PIPELINE_AS_CODE_STAGE_${stageName}_RESULTS" = "$reportStageName UNSTABLE;"
        }
    }
}

return this
