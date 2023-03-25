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
        def scriptTypes = config.settings."${actionName}_scripts_type"
        def scripts = config.settings."${actionName}_scripts"
        def filesToStash = []
        for (def ite=0; ite<scriptTypes.size(); ite++) {
            if (scriptTypes[ite] != "inline") {
                filesToStash << scripts[ite]
            }
        }
        if (filesToStash.size() > 0) {
            config.settings.has_stashes = true
            dir("scripts") {
                stash name: "stash-script-${config.preloads.plainStageName}", includes: filesToStash.join(",")
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
        if (configs.has_stashes == true) {
            dir(".script") {
                unstash "stash-script-${actionConfig.plainStageName}"
            }
        }

        def scriptTypes = configs.settings."${actionConfig.actionName}_scripts_type"
        def scripts = configs.settings."${actionConfig.actionName}_scripts"    
        for (def i=0; i<scriptTypes.size(); i++) {
            if (validScriptTypes.contains(scriptTypes[i]) == false) {
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
                if (scriptTypes[i] == "inline") {
                    if (underUnix == true) {
                        sh scripts[i]
                    }
                    else {
                        bat scripts[i]
                    }
                }
                else {
                    def dstFile = scripts[i]
                    writeFile(file: dstFile , text: scripts[i])
                    if (scriptTypes[i] == "source") {
                        sh ". " + dstFile
                    }
                    else if (scriptTypes[i] == "groovy") {
                        def externalMethod = load(dstFile)
                        externalMethod.func()
                    }
                    else if (scriptTypes[i] == "file") {
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
