def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        blackduck_enabled: true,
        blackduck_project_name: "",
        blackduck_project_version: "",
        blackduck_airgap_mode: true,
        blackduck_offline_mode: false,
        blackduck_snippet_scan: false,
        blackduck_url: "",
        blackduck_token_credential: "",
        blackduck_project_path: "",
        blackduck_project_excludes: "",
        scan_env: "",
        bdaas: false,

        scriptableParams: ["blackduck_project_path", "blackduck_project_name", "blackduck_project_excludes"]
    ]

    def utils = load "utils.groovy"
    def stageConfig = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, stageConfig)

    return stageConfig
}

def func(stageName) {
    def stageConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def plainStageName = stageConfig["plainStageName"]

    withCredentials([string(credentialsId: stageConfig["blackduck_token_credential"], variable: 'BD_TOKEN')]) {
        utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], "", [])
    }
    
    if (stageConfig['blackduck_offline_mode'] == true) {
        dir (".pf-${plainStageName}") {
            dir ("offline_output") {
                def fileSeparator = "\\"
                if (isUnix()) {
                    fileSeparator = "/"
                }
                def bdioFiles = findFiles(glob: "**${fileSeparator}*.bdio")
                for (def bdioFile in bdioFiles) {
                    def subDir = bdioFile.path.substring(0, bdioFile.path.lastIndexOf(fileSeparator))
                    dir(subDir) {
                        archiveArtifacts artifacts: bdioFile.name
                    }
                }
                deleteDir()
            }
        }
    }
}

return this