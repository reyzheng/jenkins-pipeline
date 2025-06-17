def init(stageName) {
    def defaultConfigs = [
        display_name: "builderror",
        enable: true,
        // multiple log files separated by comma
        log_files: "",
        mode: "first",
        // multiple source bases separated by comma
        source_bases: "",
        carbon_copy: "",
        unknowns: "",
        operations: "BLAME_AND_EMAIL"
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def func(stageName) {
    def stageConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"

    utils.pyExec(stageConfig["actionName"], stageConfig["stageName"], "PARSE_ERROR", [])
    if (stageConfig["enable"] == false) {
        print("builderror: skip")
        return
    }
    if (stageConfig["operations"].contains("BLAME_AND_EMAIL")) {
        dir (".pf-${stageConfig['plainStageName']}") {
            def ccs = []
            if (stageConfig["carbon_copy"] != "") {
                ccs = stageConfig["carbon_copy"].split(",")
            }
            def authorErrors = readJSON file: "authorErrors.json"
            for (def key in authorErrors.keySet()) {
                def email = authorErrors[key]["email"]
                def content = ""
                for (def error in authorErrors[key]["errors"]) {
                    content += "build log: ${error['build_log']}\n"
                    content += "build dir: ${error['buildRootDir']}\n"
                    content += "file: ${error['file']}(${error['filefull']})\n"
                    content += "revision: ${error['revision']}\n"
                    content += "line: ${error['line']}\n"
                    content += "error: ${error['error']}\n"
                    content += "\n"
                }

                def ccsPruned = []
                // skip CC for UNKNOWN errors
                if (authorErrors[key]["author"] != "UNKNOWN") {
                    for (def i=0; i<ccs.size(); i++) {
                        if (email.contains(ccs[i]) == false) {
                            ccsPruned.add("cc:" + ccs[i])
                        }
                    }
                }
                print "recipients : " + email + "," + ccsPruned.join(",")
                emailext subject: '$JOB_BASE_NAME - build error summary',
                            body: content,
                            replyTo: '$DEFAULT_REPLYTO',
                            to: email + "," + ccsPruned.join(",")
            }
        }
    }
}

return this