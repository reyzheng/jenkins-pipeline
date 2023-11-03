def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        enable: true,
        upstream_job: "",
        upstream_buildnumber: "",
        artifacts: "",
        dst: "",
        // copy remote jenkins artifacts
        remote_jenkins_url: "",
        remote_jenkins_user: "",
        remote_jenkins_credentials: ""
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    if (configs["enable"] == false) {
        print "Stage ${stageName} cancelled manually"
        return
    }

    if (configs["remote_jenkins_url"] != "") {
        withCredentials([string(credentialsId: config["remote_jenkins_credentials"], variable: "JENKINS_TOKEN")]) {
            utils.pyExec(configs["actionName"], configs["stageName"], "", [])
        }
    }
    else {
        dir (configs["dst"]) {
            copyArtifacts filter: configs.artifacts, projectName: configs.upstream_job, selector: specific(configs.upstream_buildnumber)
        }
    }
}

return this
