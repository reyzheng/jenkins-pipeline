def init(stageName) {
    def defaultConfigs = [
        display_name: "MemoryMap",
        enabled: true,

        title: 'Memory Map',
        map_file_path: '',
        graphs: [],
        builds: 2,

        scriptableParams: []
    ]

    def stageConfig = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, stageConfig)

    return stageConfig
}

def func(stageName) {
    def stageConfig = readJSON file: ".pf-all/settings/${stageName}_config.json"
    def plainStageName = stageConfig["plainStageName"]

    def underUnix = isUnix()
    dir (".pf-${plainStageName}") {
        deleteDir()
        for (def i=1; i<stageConfig['builds']; i++) {
            def currentBuild = env.BUILD_NUMBER.toInteger() - i
            try {
                copyArtifacts filter: 'memorymap-*.svg', projectName: env.JOB_NAME, selector: specific(currentBuild.toString())
                /*
                if (underUnix) {
                    sh """
                        mv memorymap.svg memorymap-${currentBuild}.svg
                    """
                }
                else {
                    bat """
                        move memorymap.svg memorymap-${currentBuild}.svg
                    """
                }
                */
            }
            catch (e) {
                print "Cannot copy ${currentBuild} build artifacts, " + e
            }
        }
    }

    utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], "INIT", [])
    utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], "CONVERT_YAML", [])
    utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], "OUTPUT_SVG", [])
    utils.archiveStageArtifacts(stageConfig["stageName"])

    dir (".pf-${plainStageName}") {
        // html report
        def stashName = "htmlreport-${plainStageName}"
        if (env.BUILD_BRANCH) {
            stashName = "htmlreport-${plainStageName}-${env.BUILD_BRANCH}"
        }
        stash name: stashName, includes: "pf-htmlreport.html,memorymap*.svg", allowEmpty: true
        env.PF_HTMLREPORTS = env.PF_HTMLREPORTS + "${stashName},"
    }
}

return this