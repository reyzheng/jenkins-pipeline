def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        coverity_scan_path: "",
        coverity_command_prefix: "",
        coverity_host: "172.21.15.146",
        coverity_port: "8080",
        coverity_auth_key_credential: "",
        coverity_report_path: "",
        coverity_analyze_defects_options: "",
        coverity_analyze_defects_excomponents: "",
        coverity_defects_assign_policy: "author",
        coverity_analyze_rtkonly: false,
        coverity_project: "",
        coverity_stream: "",
        coverity_snapshot: 0,
        coverity_build_dir: ".pf-covconfig/build",
        coverity_build_root: "",

        scriptableParams: ["coverity_project", "coverity_stream"]
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)
    if (config["settings"]["coverity_analyze_defects_options"] == "") {
        config["settings"]["coverity_analyze_defects_options"] = [:]
    }
    else {
        config["settings"]["coverity_analyze_defects_options"] = readJSON text: config["settings"]["coverity_analyze_defects_options"]
    }
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: ".pf-all/settings/${stageName}_config.json"
    def plainStageName = configs["plainStageName"]

    utils.pyExec(configs["actionName"], configs["stageName"], "INIT_WORKDIR", [])
    withCredentials([file(credentialsId: configs.coverity_auth_key_credential, variable: 'COV_AUTH_KEY')]) {
        def args
        def userDefinedReportConfig = fileExists ".pf-all/scripts/coverity_report_config.yaml"
        if (userDefinedReportConfig == true) {
            args = ["-r", ".pf-all/scripts/coverity_report_config.yaml"]
        }
        else{
            args = ["-r", ".pf-all/rtk_coverity/coverity_report_config.yaml"]
        }
        utils.pyExec(configs["actionName"], configs["stageName"], "MAIN", args)
    }
    //utils.archiveArtifacts(".pf-${plainStageName}")
    if (env.BUILD_BRANCH != null) {
        archiveArtifacts artifacts: "preview-report-committer-${env.BUILD_BRANCH}.json"
    }
    else {
        archiveArtifacts artifacts: 'preview-report-committer.json'
    }
}

return this