def init(stageName) {
    def defaultConfigs = [
        display_name: "gitpatch",
        source_dir: "",
        patch_file: "",
        scriptableParams: []
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    if (env.GERRIT_EVENT_TYPE == "ref-updated") {
        dir (configs.source_dir) {
            def patchfile
            if (configs.patch_file == "") {
                def now = new Date()
                def timestamp = now.format("yyyyMMddHHmmss")
                patchfile = "${timestamp}-${env.GERRIT_NEWREV}.patch"
            }
            else {
                patchfile = configs.patch_file
            }

            if (isUnix()) {
                // --ignore-cr-at-eol
                sh """
                    git format-patch --stdout ${env.GERRIT_OLDREV}..${env.GERRIT_NEWREV} > ${patchfile}
                """
            }
            else {
                bat """
                    git format-patch --stdout ${env.GERRIT_OLDREV}..${env.GERRIT_NEWREV} > ${patchfile}
                """
            }
            archiveArtifacts artifacts: patchfile

            // do not delete dir for later URF SBOM generation
            //deleteDir()
        }
    }
    else {
        unstable("Unsupported GERRIT_EVENT_TYPE ${env.GERRIT_EVENT_TYPE}")
    }
}

return this