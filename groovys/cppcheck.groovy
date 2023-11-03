def init(stageName) {
    def defaultConfigs = [
        display_name: "cppcheck",
        enabled: true,
        cppcheck_install_path: "",
        cppcheck_scan_path: "",

        gerrit_diff: false,
        graphics_output: false
    ]
    def mapConfig = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, mapConfig)

    return mapConfig
}

def func(stageName) {
    def stageConfig = readJSON file: ".pf-all/settings/${stageName}_config.json"
    def plainStageName = stageConfig["plainStageName"]

    def pythonExec = utils.getPython()
    def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/cppcheck.py -f .pf-all/settings/${stageName}_config.json -w .pf-${plainStageName}"
    if (isUnix()) {
        sh pyCmd
    }
    else {
        bat pyCmd
    }

    
    if (stageConfig["graphics_output"] == true) {
        //recordIssues(tools: [cppCheck(id: 'patch', pattern: "**/.pf-${plainStageName}/pf-cppcheck.xml")])
        //recordIssues(tools: [cppCheck(id: 'base', pattern: "**/.pf-${plainStageName}/pf-cppcheck-parent.xml")])
        if (env.GERRIT_BRANCH) {
            recordIssues aggregatingResults: true,
                    tools: [cppCheck(id: 'patch', name: 'cppCheck-patch', pattern: "**/.pf-${plainStageName}/pf-cppcheck.xml"),
                        cppCheck(id: 'base', name: 'cppCheck-base', pattern: "**/.pf-${plainStageName}/pf-cppcheck-parent.xml")]
        }
        else {
            recordIssues aggregatingResults: true,
                    tools: [cppCheck(pattern: "**/.pf-${plainStageName}/pf-cppcheck.xml")]
        }
    }
}

return this