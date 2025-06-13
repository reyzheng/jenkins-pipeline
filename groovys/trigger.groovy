def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        enabled: true,
        // trigger local jenkins job
        job: "",
        parameters: "{}",
        // trigger remote jenkins job
        remote_url: "",
        remote_job: "",
        remote_job_token: ""
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    utils.pyExec(configs["actionName"], configs["stageName"], "NORMALIZE_CONFIG", [])
    configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    utils.pyExec(configs["actionName"], configs["stageName"], "TRANSLATE_CONFIG", [])
    configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    if (configs["enabled"] == false) {
        print "Stage ${stageName} cancelled manually"
        return
    }

    if (configs["job"] != "") {
        def params = []
        params.add(string(name: 'UPSTREAM_JOB_NAME', value: env.JOB_NAME))
        params.add(string(name: 'UPSTREAM_BUILD_NUMBER', value: String.valueOf(env.BUILD_NUMBER)))
        for (def key in configs["parameters"].keySet()) {
            if (configs["parameters"][key].startsWith("TEXT_")) {
                def value = configs["parameters"][key].substring(5)
                value = value.replaceAll(",", "\n")
                params.add(text(name: key, value: value))
            }
            else {
                params.add(string(name: key, value: configs["parameters"][key]))
            }
        }
        print "Trigger params ${params}"
        build job: configs["job"], parameters: params
    }

    if (configs["remote_url"] != "" && configs["remote_job"] != "") {
        utils.pyExec(configs["actionName"], configs["stageName"], "TRIGGER_REMOTE", [])
    }
}

return this
