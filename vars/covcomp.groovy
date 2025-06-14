// compare defects between two coverity snapshots
// store comparison result to env."${stageName}_NEW_DEFECTS"

def init(stageName) {
    def defaultConfigs = [
        enable: "true",
        display_name: "covcomp",
        host: "172.21.15.146",
        port: "8080",
        credentials: "",
        coverity_project: "",
        snaphots: [],
        html_report: true,
        gerrit_credentials: "",
        email_nofity: false,
        email_to: "",
        email_cc: "",
        customization: ""
    ]
    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    def creds = []
    creds.add(file(credentialsId: configs["credentials"], variable: 'COV_AUTH_KEY'))
    if (configs["gerrit_credentials"] != "") {
        creds.add(sshUserPrivateKey(credentialsId: configs["gerrit_credentials"], usernameVariable: 'GERRIT_USER', keyFileVariable: 'GERRIT_KEY'))
    }

    // to support cov-comp after composition
    if ((! env.BUILD_BRANCH) && (env.PF_GLOBAL_PARALLELINFO)) {
        def branches = utils.pfParallelInfo(true)
        configs['buildBranches'] = branches
        writeJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json", json: configs, pretty: 2
    }
    withCredentials(creds) {
        utils.pyExec(configs["actionName"], configs["stageName"], "", [])
    }
    configs = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    if (configs['enable'] == true || configs['enable'] == 'true') {
        dir (".pf-${configs.plainStageName}") {
            def reportName = "COVCOMP Reports"
            if (env.BUILD_BRANCH) {
                reportName = "COVCOMP Reports(${env.BUILD_BRANCH})"
            }
            // export environment variables generated in py
            utils.exportEnv()
            if (configs["html_report"] == true) {
                publishHTML (target : [allowMissing: true,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: 'covcomp-reports',
                    reportFiles: 'covcomp_report.html',
                    reportName: reportName,
                    reportTitles: "${configs.plainStageName} Report"])
            }
            if (configs["email_nofity"] == true && env.COVCOMP_NEW_DEFECTS != "PF_NONE") {
                def receiver = ""
                if (configs["email_to"] != "") {
                    receiver = configs["email_to"]
                }
                else if (env.GERRIT_PROJECT) {
                    receiver = GERRIT_PATCHSET_UPLOADER_EMAIL
                    def hasReviewers = fileExists "reviewers"
                    if (hasReviewers) {
                        def reviewers = readFile file: "reviewers"
                        receiver = receiver + "," + reviewers
                    }
                }
                if (configs["email_cc"] != "") {
                    def ccs = configs["email_cc"].split(",")
                    for (def cc in ccs) {
                        receiver = receiver + ",cc:" + cc
                    }
                }
                print "receiver: ${receiver}"
                def dateObj = new Date()
                def dateStr = dateObj.format("yyyy-MM-dd")
                def htmlText = readFile "covcomp-reports/covcomp_report.html"
                emailext subject: "Coverity analysis result(${JOB_BASE_NAME}) - ${dateStr}",
                            body: htmlText,
                            replyTo: '$DEFAULT_REPLYTO',
                            to: receiver,
                            mimeType: 'text/html'
            }
        }
    }
}

return this