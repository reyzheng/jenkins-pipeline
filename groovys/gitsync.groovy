def init(stageName) {
    def defaultConfigs = [
        display_name: "GitSync",
        enable: true,
        sync_mode: "pure",
        dst_remote: "",
        dst_project: "",
        branches: [],
        squash_commits: false,
        include_tags: true,
        credentails: ""
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def config = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def credentialId = config["credentails"]
    if (credentialId == "") {
        credentialId = env.PF_GERRIT_CREDENTIALS
    }
    print "Adopt credentials: ${credentialId}"
    def creds = []
    if (credentialId != "") {
        creds = [credentialId]
    }
    sshagent(credentials: creds) {
        utils.pyExec(config["actionName"], config["stageName"], "", [])
    }

    /*
    if (isUnix() == false) {
        error("Available on unix agent only")
    }

    def SQUASH = 0
    def HOST = config.dst_remote
    def PROJECT = config.dst_project
    def credentialId = config.credentails
    if (credentialId == "") {
        credentialId = env.PF_GERRIT_CREDENTIALS
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
                print "pure mode: branches, " + config.branches
                print "pure mode: include tags, " + config["include_tags"]
                def tagParam = "on"
                if (config["include_tags"] == false) {
                    tagParam = "off"
                }
                if (config.branches.size() == 0 || config["branches"][0] == "") {
                    sh "bash ${WORKSPACE}/${env.PF_ROOT}/pipeline_scripts/gitsync.sh -m pure -h ${HOST} -p ${PROJECT} -t ${tagParam}"
                }
                else {
                    def BRANCHES = []
                    for (def i=0; i<config.branches.size(); i++) {
                        BRANCHES.add(config["branches"][i])
                    }
                    sh "bash ${WORKSPACE}/${env.PF_ROOT}/pipeline_scripts/gitsync.sh -m pure -h ${HOST} -p ${PROJECT}  -t ${tagParam} -b " + BRANCHES.join(",")
                }
            }
            else {
                print "branch mode: " + config.branches
                if (config.branches.size() == 0 || config["branches"][0] == "") {
                    sh "bash ${WORKSPACE}/${env.PF_ROOT}/pipeline_scripts/gitsync.sh -m branch -h ${HOST} -s ${SQUASH}"
                }
                else {
                    def BRANCHES = []
                    for (def i=0; i<config.branches.size(); i++) {
                        BRANCHES.add(config["branches"][i])
                    }
                    sh "bash ${WORKSPACE}/${env.PF_ROOT}/pipeline_scripts/gitsync.sh -m branch -h ${HOST} -s ${SQUASH} -b " + BRANCHES.join(",")
                }
            }
        }
    }
    */
}

return this
