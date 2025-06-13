
def init(stageName) {
    def defaultConfigs = [
        // script
        display_name: "",
        stage_lock: false,
        failfast: false,
        sshcredentials: "",
        types: [],
        contents: [],
        expressions: [],
        // mapping options: 
        //     manytoone: all scripts share one coverity config
        //     onetoone: one script map one coverity config
        //     onetomany: one script for all coverity configs
        buildmapping: "onetoone",
        // coverity
        coverity_scan_enabled: true,
        coverity_local_report: true,
        coverity_local_analysis: false,
        // none, accumulate, iterate
        coverity_codetek_training: "none",
        coverity_codetek_inference_only: false,
        coverity_codetek_sshagent: "",
        training_revision_start: "none",
        training_revision_end: "none",
        coverity_analyze_defects: false,
        coverity_report_path: '',
        coverity_analyze_defects_options: "",
        coverity_analyze_defects_excomponents: "",
        // author: assign defects to author
        // component: group defects by component (RSIPCam proprietary)
        coverity_defects_assign_policy: "author",
        // meaningless for coverity_defects_assign_policy 'component'
        coverity_analyze_rtkonly: false,
        coverity_host: '172.21.15.146',
        coverity_port: '8080',
        coverity_auth_key_credential: '',
        coverity_scan_path: '',
        coverity_scan_toolbox: '',
        coverity_scan_toolbox_args: '',
        coverity_secondary_toolbox: '',
        //coverity_xml: 'coverity_idir/coverity.xml',
        coverity_build_dir: '.pf-covbuild',
        coverity_project: [],
        coverity_stream: [],
        coverity_static_configuration: false,
        coverity_comptype_platform: [],
        coverity_comptype_prefix: [],
        coverity_comptype: [],
        coverity_comptype_gcc: [],
        //coverity_comptype_ld: [],
        coverity_build_option: [],
        coverity_clean_builddir: true,
        coverity_configure_option: [],
        coverity_analyze_parent: "none",
        coverity_analyze_option: [],
        allow_empty_analysis: false,
        coverity_analysis_operation: "ALL",
        // default 'default' at def init(stageName)
        coverity_checker_enablement: [],
        coverity_checker_extra: [],
        coverity_coding_standards: [],
        // coverity_pattern_specified, coverity_pattern_excluded conflicts with coverity_analyze_rtkonly
        coverity_pattern_specified: [],
        coverity_pattern_excluded: [],

        coverity_commit_excluded: [],
        coverity_commit_additional: [],

        coverity_snapshot_version: [],
        coverity_snapshot_description: [],

        staticParams: ["coverity_snapshot_version", "coverity_snapshot_description", "coverity_checker_enablement"]
    ]
    def mapConfig = utils.commonInit(stageName, defaultConfigs)
    if (mapConfig["coverity_analyze_defects_options"] == "") {
        mapConfig["coverity_analyze_defects_options"] = [:]
    }
    else {
        mapConfig["coverity_analyze_defects_options"] = readJSON text: mapConfig["coverity_analyze_defects_options"]
    }
    utils.finalizeInit(stageName, mapConfig)

    return mapConfig
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    def plainStageName = configs["plainStageName"]

    def branchSubDescription = ""
    if (env.BUILD_BRANCH) {
        branchSubDescription = env.BUILD_BRANCH
    }

    utils.pyExec(configs["actionName"], configs["stageName"], "TRANSLATE_CONFIG", [])
    configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    if (env.PF_COV_CREDENTIALS == "") {
        env.PF_COV_CREDENTIALS = configs["coverity_auth_key_credential"]
    }
    env.PF_COV_HOST = configs['coverity_host']
    env.PF_COV_PORT = configs['coverity_port']
    if (configs["coverity_codetek_training"] != "none") {
        dir (env.PF_ROOT) {
            dir ("pipeline_scripts") {
                dir ("covtek") {
                    checkout(scm: [$class: 'GitSCM',
                        extensions: [
                            [$class: 'CloneOption',
                                depth: 1,
                                timeout: 60]],
                        userRemoteConfigs: [[
                            url: "https://mirror.rtkbf.com/gerrit/sdlc/coverity-training"]],
                        branches: [[name: "develop"]]
                    ])
                }
            }
        }
    }

    try {
        utils.pyExec(configs["actionName"], configs["stageName"], "INIT_WORKDIR", [])
        for (def i=0; i<configs["types"].size(); i++) {
            if (configs["expressions"][i] && configs["expressions"][i] != "") {
                def expr = evaluate(configs["expressions"][i])
                if (expr == false) {
                    print "skip ${i}th script"
                    continue
                }
            }

            withCredentials([file(credentialsId: configs["coverity_auth_key_credential"], variable: 'COV_AUTH_KEY')]) {
                def args = ["-d", "${i}"]
                if (configs["coverity_codetek_sshagent"] == "") {
                    utils.pyExec(configs["actionName"], configs["stageName"], "ANALYZE", args, pyEnv="RAW")
                }
                else {
                    sshagent(credentials: [configs["coverity_codetek_sshagent"]]) {
                        utils.pyExec(configs["actionName"], configs["stageName"], "ANALYZE", args, pyEnv="RAW")
                    }
                }
            }

            utils.archiveStageArtifacts(configs["stageName"])
        }

        dir (".pf-${plainStageName}") {
            // export environment variables generated in py
            utils.exportEnv()
            // html report
            def stashName = "htmlreport-${plainStageName}"
            if (env.BUILD_BRANCH) {
                stashName = "htmlreport-${plainStageName}-${env.BUILD_BRANCH}"
            }
            stash name: stashName, includes: "pf-htmlreport.html", allowEmpty: true
            env.PF_HTMLREPORTS = env.PF_HTMLREPORTS + "${stashName},"
        }

        env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS += "Build $branchSubDescription SUCCESS;"
    }
    catch (e) {
        dir (".pf-${plainStageName}") {
            utils.exportEnv()
        }
        if (configs["failfast"] == true) {
            error(message: "${configs.stageName} " + e)
        }
        // Set the result and add to map as UNSTABLE on failure
        unstable(message: "Coverity build $branchSubDescription is unstable " + e)
        env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS += "Build $branchSubDescription UNSTABLE;"
    }
}

return this
