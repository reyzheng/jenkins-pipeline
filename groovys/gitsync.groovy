def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        sync_mode: "pure",
        dst_remote: "",
        dst_project: "",
        branches: [],
        squash_commits: false,
        credentails: ""
    ]
    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)

    return config
}

def func(pipelineAsCode, config, preloads) {
    if (isUnix() == false) {
        error("Available on unix agent only")
    }

    def SQUASH = 0
    def HOST = config.dst_remote
    def PROJECT = config.dst_project
    def sourceConfig = pipelineAsCode.configs["source"].settings
    def credentialId = config.credentails
    if (credentialId == "") {
        try {
            credentialId = pipelineAsCode.global_vars.gerrit_credentials
        }
        catch(e) {
        }
    }

    print "Adopt credentials: ${credentialId}"
    if (config.squash_commits == true) {
        SQUASH = 1
    }
    print "Change to directory ${env.PF_SOURCE_DST_0}"
    dir (env.PF_SOURCE_DST_0) {
        def creds = []
        if (credentialId != "") {
            creds = [credentialId]
        }
        print "sshagent: ${creds}"
        sshagent(credentials: creds) {
            if (config.sync_mode == "pure") {
                print "pure mode"
                if (config.branches.size() == 0 || config["branches"][0] == "") {
                    sh "bash ${WORKSPACE}/${env.PF_ROOT}/pipeline_scripts/gitsync.sh -m pure -h ${HOST} -p ${PROJECT}"
                }
                else {
                    def BRANCHES = config.branches.join(",")
                    sh "bash ${WORKSPACE}/${env.PF_ROOT}/pipeline_scripts/gitsync.sh -m pure -h ${HOST} -p ${PROJECT} -b ${BRANCHES}"
                }
            }
            else {
                print "branch mode"
                if (config.branches.size() == 0) {
                    sh "bash ${WORKSPACE}/${env.PF_ROOT}/pipeline_scripts/gitsync.sh -m branch -h ${HOST} -s ${SQUASH}"
                }
                else {
                    def BRANCHES = config.branches.join(",")
                    sh "bash ${WORKSPACE}/${env.PF_ROOT}/pipeline_scripts/gitsync.sh -m branch -h ${HOST} -s ${SQUASH} -b ${BRANCHES}"
                }
            }
        }
    }
}

return this
