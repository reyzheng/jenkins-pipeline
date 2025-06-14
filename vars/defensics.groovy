def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        defensics_path: "CTCDOCKER",
        test_suite: "",
        set_file: "",
        fuzzbox_ip: "",

        // screen tty
        screen_enabled: false,
        screen_tty: "",
        screen_baud: 115200,

        // parameters deprecated
        //node: "",
        test_parameters: "",
        scriptableParams: ["test_suite", "set_file"]
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def plainStageName = configs["plainStageName"]

    utils.pyExec(configs["actionName"], configs["stageName"], "TRANSLATE_CONFIG", [])
    utils.pyExec(configs["actionName"], configs["stageName"], "START", [])
    dir (".pf-${configs['stageName']}") {
        dir ('tmp/report') {
            archiveArtifacts artifacts: "report.html"
            archiveArtifacts artifacts: "remediation.zip"
        }
    }
    utils.pyExec(configs["actionName"], configs["stageName"], "CLEAN", [])
}

return this