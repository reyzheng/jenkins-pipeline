def init(stageName) {
    def defaultConfigs = [
        display_name: "",
        jira_site_name: "",
        jira_credentials: "",
        defensics_jira_project: "",
        issue_epic: "",
        issue_label: [],
        defensics_report_path: "",
        // failure_mode
        //     duration: passed if 72hr finished, failed otherwise
        //     failcases: parse report to extract fail cases
        failure_mode: "duration",
        specified_defect: -1,
        max_defects: 10
    ]

    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)
    /*
    dir ('pipeline_scripts') {
        stash name: "stash-script-${stageName}", includes: "defensicsParser.py"
    }
    */

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    if (configs["defensics_report_path"] == "") {
        if (env.UPSTREAM_JOB) {
            print "Copy from another job ${env.UPSTREAM_JOB}/${env.UPSTREAM_BUILDNUMBER}"
            copyArtifacts filter: 'remediation.zip', projectName: env.UPSTREAM_JOB, selector: specific(env.UPSTREAM_BUILDNUMBER)
        }
        else {
            print "Copy current build ${env.JOB_NAME}/${env.BUILD_NUMBER}"
            copyArtifacts filter: 'remediation.zip', projectName: env.JOB_NAME, selector: specific(env.BUILD_NUMBER)
        }
        sh """
            unzip remediation.zip
        """
        def reportFiles = findFiles glob: "*-issues-report.html"
        configs["defensics_report_path"] = reportFiles[0].path
        writeJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json", json: configs
    }

    withCredentials([string(credentialsId: configs["jira_credentials"], variable: 'JIRA_TOKEN')]) {
        utils.pyExec(configs["actionName"], configs["stageName"], "", [])
    }
}

return this