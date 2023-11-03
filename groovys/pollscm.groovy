def init(stageName) {
    def defaultConfigs = [
        display_name: "pollscm",
        scm_url: "",
        scm_credentials: "",
        scm_branch: "master"
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    sh """
        cd .pf-all
        pwd && ls -al
    """
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    dir ()
    checkout scm: [$class: 'GitSCM',
                    userRemoteConfigs: [[url: configs["scm_url"],
                                                credentialsId: configs["scm_credentials"]]],
                                        branches: [[name: configs["scm_branch"]]]
    ], poll: true
    sh """
        cd .pf-all
        pwd && ls -al
    """
    sh """
        pwd && ls -al
    """
}

return this