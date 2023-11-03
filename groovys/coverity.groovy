def init(stageName) {
    def defaultConfigs = [
        // script
        display_name: "",
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
        coverity_analyze_defects: false,
        coverity_report_path: '',
        coverity_analyze_defects_options: "",
        coverity_analyze_defects_excomponents: "",
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
        coverity_build_dir: '.pf-covconfig/build',
        coverity_project: [],
        coverity_stream: [],
        coverity_comptype_platform: [],
        coverity_comptype_prefix: [],
        coverity_comptype: [],
        coverity_comptype_gcc: [],
        //coverity_comptype_ld: [],
        coverity_build_option: [],
        coverity_clean_builddir: true,
        coverity_analyze_parent: "none",
        coverity_analyze_option: [],
        // default 'default' at def init(stageName)
        coverity_checker_enablement: [],
        coverity_coding_standards: [],
        // coverity_pattern_specified, coverity_pattern_excluded conflicts with coverity_analyze_rtkonly
        coverity_pattern_specified: [],
        coverity_pattern_excluded: [],

        coverity_snapshot_version: [],
        coverity_snapshot_description: [],

        scriptableParams: ["coverity_host", "coverity_port", "coverity_analyze_defects", "coverity_scan_enabled", "coverity_analyze_parent", "coverity_project", "coverity_stream", "coverity_build_dir", "coverity_comptype", "coverity_comptype_gcc", "coverity_snapshot_version", "coverity_snapshot_description"]
    ]
    def mapConfig = utils.commonInit(stageName, defaultConfigs)
    if (mapConfig["settings"]["coverity_analyze_defects_options"] == "") {
        mapConfig["settings"]["coverity_analyze_defects_options"] = [:]
    }
    else {
        mapConfig["settings"]["coverity_analyze_defects_options"] = readJSON text: mapConfig["settings"]["coverity_analyze_defects_options"]
    }
    // check credentials
    /*
    // TODO: 
    def underUnix = isUnix()
    if (mapConfig.settings.coverity_auth_key_credential != "" && underUnix == true) {
        withCredentials([file(credentialsId: mapConfig.settings.coverity_auth_key_credential, variable: 'KEY_PATH')]) {
            def keyObj = readJSON file: KEY_PATH
            def checkHealth = utils.captureStdout("set +x && curl --header 'Accept: application/json' --user ${keyObj.username}:${keyObj.key} http://${mapConfig.settings.coverity_host}:${mapConfig.settings.coverity_port}/api/v2/serverInfo/version", underUnix)
            if (checkHealth[0] == "Authentication failed.") {
                error("${stageName}: invalid coverity credentials")
            }
        }
    }
    */
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
                utils.pyExec(configs["actionName"], configs["stageName"], "ANALYZE", args)
            }
            if (configs["coverity_local_report"] == true) {
                dir (".pf-${plainStageName}") {
                    archiveArtifacts artifacts: "coverityReport*.zip", allowEmptyArchive: true
                }
            }
            if (configs["coverity_analyze_defects"] == true || configs["coverity_analyze_defects"] == "true") {
                if (env.BUILD_BRANCH != null) {
                    archiveArtifacts artifacts: "preview-report-committer-${env.BUILD_BRANCH}.json"
                }
                else {
                    archiveArtifacts artifacts: 'preview-report-committer.json'
                }
            }
        }

        dir (".pf-${plainStageName}") {
            // export environment variables generated in py
            utils.exportEnv()
            // html report
            def stashName = "htmlreport-${plainStageName}"
            if (env.BUILD_BRANCH) {
                stashName = "htmlreport-${plainStageName}-${env.BUILD_BRANCH}"
            }
            stash name: stashName, includes: ".pf-htmlreport", allowEmpty: true
            env.PF_HTMLREPORTS = env.PF_HTMLREPORTS + "${stashName},"
        }

        env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS += "Build $branchSubDescription SUCCESS;"
    }
    catch (e) {
        if (configs["failfast"] == true) {
            error(message: "${configs.stageName} " + e)
        }
        // Set the result and add to map as UNSTABLE on failure
        unstable(message: "Coverity build $branchSubDescription is unstable " + e)
        env.PIPELINE_AS_CODE_STAGE_BUILD_RESULTS += "Build $branchSubDescription UNSTABLE;"
    }
}

return this