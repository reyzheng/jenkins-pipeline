import groovy.transform.Field

def init(stageName) {
    def utils = load "utils.groovy"
    def actionName = utils.extractActionName(stageName)

    def defaultConfigs = [
        display_name: "",
        "${actionName}_enabled": true,
        "${actionName}_scripts_type": [],
        "${actionName}_scripts": []
    ]
    def config = utils.commonInit(stageName, defaultConfigs)

    if (config.settings."${actionName}_enabled" == true) {
        // load script content
        config.preloads.scriptTypes = config.settings."${actionName}_scripts_type"
        config.preloads.scripts = config.settings."${actionName}_scripts"    
        for (def ite=0; ite<config.preloads.scriptTypes.size(); ite++) {
            if (config.preloads.scriptTypes[ite] == "inline") {
            }
            else if (config.preloads.scriptTypes[ite].trim() != "") {
                //print "load $stageName script, " + config.preloads.scripts[ite]
                config.preloads.scripts[ite] = readFile(file: "scripts/" + config.preloads.scripts[ite])
            }
        }
    }

    return config
}

def func(pipelineAsCode, configs, actionConfig) {
    def underUnix = isUnix()
    def validScriptTypes = ["inline", "file", "source", "groovy"]

    if (configs."${actionConfig.actionName}_enabled" == false) {
        print "Stage ${actionConfig.stageName} cancelld manually"
        return
    }

    def reportStageName = actionConfig.stageName
    if (env.BUILD_BRANCH) {
        reportStageName = reportStageName + " ${env.BUILD_BRANCH}"
    }

    try {
        for (def i=0; i<actionConfig.scriptTypes.size(); i++) {
            if (validScriptTypes.contains(actionConfig.scriptTypes[i]) == false) {
                continue
            }
            def scmDir
            if (env.PF_MAIN_SOURCE_NAME) {
                def sourceNames = env.PF_MAIN_SOURCE_NAME.split(',')
                scmDir = pipelineAsCode.configs[sourceNames[0]].settings.scm_dsts[i]
            }
            else {
                // invalid pipelineAsCode.scm_dsts
                scmDir = ""
            }

            print "Working directory: " + scmDir
            dir(scmDir) {
                if (actionConfig.scriptTypes[i] == "inline") {
                    if (underUnix == true) {
                        sh actionConfig.scripts[i]
                    }
                    else {
                        bat actionConfig.scripts[i]
                    }
                }
                else {
                    // write to a temp file in workspace
                    def dstFileName = "script-" + actionConfig.actionName + "-" + currentBuild.startTimeInMillis + ".bat"
                    def dstFile
                    if (underUnix == true) {
                        dstFile = env.WORKSPACE + "/" + dstFileName
                    }
                    else {
                        dstFile = env.WORKSPACE + "\\" + dstFileName
                    }

                    writeFile(file: dstFile , text: actionConfig.scripts[i])
                    if (actionConfig.scriptTypes[i] == "source") {
                        sh ". " + dstFile
                    }
                    else if (actionConfig.scriptTypes[i] == "groovy") {
                        def externalMethod = load(dstFile)
                        externalMethod.func()
                    }
                    else if (actionConfig.scriptTypes[i] == "file") {
                        if (underUnix == true) {
                            def statusCode = sh script: "bash", returnStatus: true
                            if (statusCode == 0) {
                                sh "bash -xe '${dstFile}'"
                            }
                            else {
                                sh "sh -xe '${dstFile}'"
                            }
                        }
                        else {
                            bat "\"${dstFile}\""
                        }
                    }

                    if (underUnix == true) {
                        sh "rm -f ${dstFile}"
                    }
                    else {
                        bat "del ${dstFile} /f"
                    }
                }
            }
        }
        if (actionConfig.actionName == "build") {
            env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS += "$reportStageName SUCCESS;"
        }
        else if (actionConfig.actionName == "test") {
            env.PIPELINE_AS_CODE_STAGE_TEST_RESULTS += "$reportStageName SUCCESS;"
        }
    }
    catch (e) {
        unstable(message: "${actionConfig.stageName} is unstable " + e)
        if (actionConfig.actionName == "build") {
            // Set the result and add to map as UNSTABLE on failure
            env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS += "$reportStageName UNSTABLE;"
        }
        else if (actionConfig.actionName == "test") {
            // Set the result and add to map as UNSTABLE on failure
            env.PIPELINE_AS_CODE_STAGE_TEST_RESULTS += "$reportStageName UNSTABLE;"
        }
    }
}

return this
