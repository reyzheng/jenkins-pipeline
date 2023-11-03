def init(stageName) {
    def defaultConfigs = [
        site_name: '',
        jira_credentials: '',

        // coverity to jira
        defects_to_jira: false,
        defects_jira_project: '',
        defects_issue_type: 'Issue',
        defects_issue_epic: '',
        defects_extra_summary: '',
        defects_default_assignee: '',
        defects_assignee_excluded: '',
        coverity_project_name: '',
        epic_link_filed_id: '',
        // new
        defects_assign_policy: 'author',
        defects_extra_watcher: '',
        defects_extra_fields: "",
        // CN3SD8, MORE_DESCRIPTION
        defects_customization: '',
        defects_number_limit: 0,

        // build result to jira
        buildresult_to_jira: false,
        buildresult_jira_project: '',
        buildresult_default_assignee: '',

        scriptableParams: ["coverity_project_name", "defects_jira_project", "defects_default_assignee", "defects_assign_policy", "defects_issue_epic", "defects_to_jira", "defects_extra_fields", "defects_number_limit"]
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.finalizeInit(stageName, config)

    return config
}

def getEPICKey(jiraConfig, pythonExec) {
    def jiraProject = jiraConfig["defects_jira_project"]
    def project = jiraConfig["defects_issue_epic"]
    def plainStageName = jiraConfig["plainStageName"]
    if (jiraConfig["jira_credentials"] == "") {
        def jiraSite = jiraConfig.site_name
        // search epic(project)
        def ret = jiraJqlSearch jql: "project=${jiraProject} and issuetype='EPIC' and 'Epic Name'='${project}'", site: jiraSite, failOnError: true
        if (ret != null && ret.data.total != 0) {
            def issues = ret.data.issues
            dir (".pf-${plainStageName}") {
                writeJSON file: 'epicKey.json', json: issues[0]
            }
        }
        else {
            // epic not existed
            def epicNameFieldId
            dir (".pf-${plainStageName}") {
                epicNameFieldId = readJSON file: 'epicNameField.json'
                epicNameFieldId = epicNameFieldId["id"]
            }

            def jiraIssue = [fields: [
                                project: [key: jiraProject],
                                summary: project,
                                description: project,
                                "${epicNameFieldId}": project,
                                issuetype: [name: 'Epic']]]
            // fill user-defined fields
            def userDefinedFields
            dir (".pf-${plainStageName}") {
                userDefinedFields = readJSON file: 'extraFieldsMap.json'
            }
            for (def fieldsMapKey in userDefinedFields.keySet()) {
                def fieldId = userDefinedFields[fieldsMapKey].id
                def fieldValue = userDefinedFields[fieldsMapKey].value
                jiraIssue.fields."${fieldId}" = fieldValue
            }
            response = jiraNewIssue issue: jiraIssue, failOnError: false, auditLog: false, site: jiraSite
            if (response.code == 400) {
                // check if failure caused by fields cannot be set
                def unnecessaryFields = []
                // check fields cannot be set
                def errorObj = readJSON text: response.error
                for (def key in errorObj.errors.keySet()) {
                    if (errorObj.errors[key].endsWith("It is not on the appropriate screen, or unknown.")) {
                        unnecessaryFields << key
                        jiraIssue.fields.remove(key)
                    }
                }
                if (unnecessaryFields.size() > 0) {
                    print "Updated epic fields: ${jiraIssue.fields}"
                    // again
                    response = jiraNewIssue issue: jiraIssue, auditLog: false, site: jiraSite
                }
            }
            try {
                dir (".pf-${plainStageName}") {
                    writeJSON file: 'epicKey.json', json: response.data
                }
            }
            catch (e) {
            }
        }
    }
    else {
        def stageName = jiraConfig["stageName"]
        withCredentials([string(credentialsId: jiraConfig["jira_credentials"], variable: 'JIRA_TOKEN')]) {
            def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -w .pf-${plainStageName} -f .pf-all/settings/${stageName}_config.json -c GET_JIRA_EPIC"
            if (isUnix()) {
                sh pyCmd
            }
            else {
                bat pyCmd
            }
        }
    }
}

def getExistedJIRAIssues(defaultConfig, pythonExec) {
    def plainStageName = defaultConfig["plainStageName"]
    if (defaultConfig["jira_credentials"] == "") {
        def jiraSite = defaultConfig.site_name
        def jiraProject = defaultConfig.defects_jira_project
        def jiraIssueType = defaultConfig.defects_issue_type
        def epicKey
        dir (".pf-${plainStageName}") {
            epicKey = readJSON file: 'epicKey.json'
            epicKey = epicKey["key"]
        }

        def jqlCommand
        if (jiraIssueType == "Issue") {
            jqlCommand = "project=${jiraProject} and (issuetype='Task' or issuetype='Issue') and 'Epic Link'='${epicKey}'"
        }
        else{
            jqlCommand = "project=${jiraProject} and issuetype='Task' and 'Epic Link'='${epicKey}'"
        }

        def issues = []
        for (def i=0; i<100; i++) {
            // get all issues under project (via epic)
            def ret = jiraJqlSearch jql: jqlCommand, fields: ["labels", "components", "summary", "description", "status"], site: jiraSite, startAt: i*1000, maxResults: 1000, failOnError: true
            if (ret != null) {
                issues += ret.data.issues
                if (ret.data.issues.size() < 1000) {
                    break
                }
            }
            else {
                break
            }
        }

        dir (".pf-${plainStageName}") {
            writeJSON file: 'issues.json', json: issues
        }
    }
    else {
        withCredentials([string(credentialsId: defaultConfig["jira_credentials"], variable: 'JIRA_TOKEN')]) {
            def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -w .pf-${plainStageName} -c GET_JIRA_ISSUES"
            if (isUnix()) {
                sh pyCmd
            }
            else {
                bat pyCmd
            }
        }
    }
}

def getComponentsMap(jiraConfig, pythonExec) {
    def plainStageName = jiraConfig["plainStageName"]
    if (jiraConfig["jira_credentials"] == "") {
        def resultMap = [:]
        def components = jiraGetProjectComponents idOrKey: jiraConfig["defects_jira_project"], site: jiraConfig["site_name"]
        for (component in components.data) {
            resultMap."$component.name" = component
        }
        dir (".pf-${plainStageName}") {
            writeJSON file: 'componentsMap.json', json: resultMap
        }
    }
    else {
        withCredentials([string(credentialsId: jiraConfig["jira_credentials"], variable: 'JIRA_TOKEN')]) {
            def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -w .pf-${plainStageName} -c GET_JIRA_COMPONENT"
            if (isUnix()) {
                sh pyCmd
            }
            else {
                bat pyCmd
            }
        }
    }
}

def transitIssueStatus(issueIdOrKey, newStatus, jiraSiteName) {
    def ret
    ret = jiraGetIssue idOrKey: issueIdOrKey, site: jiraSiteName
    def jiraIssue = ret.data
    def jiraIssueStatus = jiraIssue.fields.status.name
    if (newStatus == "Close") {
        if (jiraIssueStatus.toLowerCase().startsWith("close")) {
            //print "DBG: skip transit ${issueIdOrKey} to Close"
            return
        }
    }
    else if (newStatus == "Reopen") {
        if (jiraIssueStatus.toLowerCase().startsWith("close") == false) {
            //print "DBG: skip transit ${issueIdOrKey} to Reopen"
            return
        }
    }

    ret = jiraGetIssueTransitions idOrKey: issueIdOrKey, site: jiraSiteName
    def transitions = ret.data.transitions
    def resolveStatusId = 0
    for (def j=0; j<transitions.size(); j++) {
        def transition = transitions[j]
        if (transition.name.startsWith(newStatus) || 
                (newStatus == "Close" && transition.name == "Won't fix")) {
            resolveStatusId = transition.id
            break;
        }
    }

    if (resolveStatusId == 0) {
        print "Cannot transit issue ${issueIdOrKey}(${jiraIssueStatus}) to ${newStatus}"
        return
    }
    def transitionInput = [transition: [id: "${resolveStatusId}"]]
    jiraTransitionIssue idOrKey: issueIdOrKey, input: transitionInput, site: jiraSiteName
}

def assignJIRAIssue(idOrKey, committer, committerFullname, config) {
    try {
        jiraAssignIssue idOrKey: idOrKey, 
                                        userName: committer,
                                        accountId: "",
                                        site: config.site_name
    }
    catch (e) {
        // assign to default assignee if failed
        jiraAssignIssue idOrKey: idOrKey, 
                                        userName: config.defects_default_assignee,
                                        accountId: "",
                                        site: config.site_name
        print "Assign issue to ${committer} failed, assign to ${config.defects_default_assignee}"

        def comment = [ body: "Assign issue to ${committer}(${committerFullname}) failed" ]
        jiraAddComment site: config.site_name, idOrKey: idOrKey, input: comment, auditLog: false
    }
}

def updateIssueComponents(issueId, components, jiraSite) {
    def updatedIssue = [fields: [ // id or key must present for project.
                            components: components]]
    jiraEditIssue idOrKey: issueId, issue: updatedIssue, site: jiraSite
}

def publishIssuesToJIRA(jiraConfig, pythonExec) {
    def plainStageName = jiraConfig["plainStageName"]
    if (jiraConfig["jira_credentials"] != "") {
        withCredentials([string(credentialsId: jiraConfig["jira_credentials"], variable: 'JIRA_TOKEN')]) {
            def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -w .pf-${plainStageName} -c PUBLISH"
            if (isUnix()) {
                sh pyCmd
            }
            else {
                bat pyCmd
            }
        }
        return
    }

    def componentsMap
    def jiraIssuesToClose
    def jiraIssuesToReopen
    def jiraIssuesToCreate
    def response
    dir (".pf-${plainStageName}") {
        componentsMap = readJSON file: 'componentsMap.json'
        jiraIssuesToClose = readJSON file: 'jiraIssuesToClose.json'
        jiraIssuesToReopen = readJSON file: 'jiraIssuesToReopen.json'
        jiraIssuesToCreate = readJSON file: 'jiraIssuesToCreate.json'
    }

    for (def i=0; i<jiraIssuesToClose["count"]; i++) {
        try {
            def updates = [:]
            updates["fields"] = [:]
            updates["fields"]["labels"] = jiraIssuesToClose["issues"][i]["labels"]
            print ("publishIssuesToJIRA: update component " + updates)
            jiraEditIssue idOrKey: jiraIssuesToClose["issues"][i]["key"], issue: updates, site: jiraConfig["site_name"]
        }
        catch (e) {
            // already closed
        }

        print ("publishIssuesToJIRA: close " + jiraIssuesToClose["issues"][i]["key"])
        transitIssueStatus(jiraIssuesToClose["issues"][i]["key"], "Close", jiraConfig["site_name"])
    }
    for (def key in jiraIssuesToReopen.keySet()) {
        def jiraIssueToReopen = jiraIssuesToReopen[key]
        def issueComponent = jiraIssueToReopen["component"]
        transitIssueStatus(key, "Reopen", jiraConfig.site_name)
        response = jiraEditIssue idOrKey: key, issue: jiraIssueToReopen, site: jiraConfig.site_name
        if (response.successful == true) {
            if (componentsMap.containsKey(issueComponent) == true) {
                def components = []
                components << componentsMap."$issueComponent"
                updateIssueComponents(key, components, jiraConfig.site_name)
            }
        }
    }
    def jiraIssueType = jiraConfig["defects_issue_type"]
    for (def i=0; i<jiraIssuesToCreate["count"]; i++) {
        def jiraIssueToCreate = jiraIssuesToCreate["issues"][i]
        def issueComponent = jiraIssueToCreate["issue"]["component"]
        jiraIssueToCreate["issue"].remove("component")
        jiraIssueToCreate["issue"]["fields"]["issuetype"] = [:]
        jiraIssueToCreate["issue"]["fields"]["issuetype"]["name"] = jiraIssueType
        response = jiraNewIssue issue: jiraIssueToCreate["issue"], auditLog: false, site: jiraConfig.site_name
        if (response.successful == true) {
            def issueId = response.data.key
            if (componentsMap.containsKey(issueComponent) == true) {
                def components = []
                components << componentsMap."$issueComponent"
                updateIssueComponents(issueId, components, jiraConfig.site_name)
            }
            if (jiraIssueToCreate["assignee"] != "") {
                assignJIRAIssue(issueId, jiraIssueToCreate["assignee"], jiraIssueToCreate["assigneefull"], jiraConfig)
            }
            if (jiraConfig.defects_extra_watcher != "") {
                def watchers = jiraConfig.defects_extra_watcher.split(",")
                for (def watcher in watchers) {
                    jiraAddWatcher idOrKey: issueId, userName: watcher, site: jiraConfig.site_name
                }
            }
            if (jiraIssueToCreate["close"] == true) {
                // tips: first time "Intentional" or "False Positive", transit to close
                // and no attach available caused by cov-format-error skipped that
                transitIssueStatus(issueId, "Close", jiraConfig.site_name)
            }
        }
    }
}

def updateUndetectedDefectsLabel(jiraConfig, pythonExec) {
    def plainStageName = jiraConfig["plainStageName"]
    if (jiraConfig["jira_credentials"] != "") {
        withCredentials([string(credentialsId: jiraConfig["jira_credentials"], variable: 'JIRA_TOKEN')]) {
            def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -w .pf-${plainStageName} -c UPDATE_UNDECTED"
            if (isUnix()) {
                sh pyCmd
            }
            else {
                bat pyCmd
            }
        }
        return
    }

    def jiraIssues
    def jiraIssuesToReopen
    dir (".pf-${plainStageName}") {
        jiraIssues = readJSON file: 'existedJiraIssues.json'
        jiraIssuesToReopen = readJSON file: 'jiraIssuesToReopen.json'
    }
    for (def key in jiraIssues.keySet()) {
        def jiraIssue = jiraIssues[key]
        if (jiraIssue.fields.streams_to_remove.size() > 0) {
            def jiraIssueId = jiraIssue["id"]
            jiraIssue.fields.labels -= jiraIssue.fields.streams_to_remove
            def updatedIssue
            if (jiraIssuesToReopen.containsKey(jiraIssueId)) {
                updatedIssue = [fields: [labels: jiraIssue.fields.labels
                                ]]
                print("Update labels only: $key")
            }
            else {
                updatedIssue = [fields: [labels: jiraIssue.fields.labels,
                                    description: jiraIssue.fields.description
                                ]]
                print("Update labels and description: $key")
            }
            try {
                jiraEditIssue idOrKey: jiraIssue.id, issue: updatedIssue, site: jiraConfig.site_name
            }
            catch(e) {
                // maybe closed, then labels could not be updated
            }
        }
        if (jiraIssue.fields.toremove == true) {
            transitIssueStatus(jiraIssue.id, "Close", jiraConfig.site_name)
        }
    }
}

// A: preview-report-committer.json: all defects () in the stream
// B: cvssreport.json: all defects (with related cvss info.) in the project
// C: existed issue (in specified project)
// in A, and not triaged as Ignore:      create new
// in A, and triaged as Ignore:          create new, and close
// in C, not in B:                       close (existed)
// note:                                 component policy, in A, and triaged as Ignore, only the Jira issue match exact component will be closed
//                                          author policy, in A, and triaged as Ignore, only one Jira issue so only one will be closed
def copyDefectsArtifacts(upstreamJobName, upstreamBuildNumber, buildBranch) {
    def reportFile
    if (buildBranch == null) {
        reportFile = "preview-report-committer.json"
    }
    else {
        reportFile = "preview-report-committer-${buildBranch}.json"
    }
    print "projectName: " + upstreamJobName
    print "buildNumber: " + upstreamBuildNumber
    try {
        step([$class: 'CopyArtifact', 
                filter: reportFile, 
                flatten: false, 
                projectName: upstreamJobName, 
                selector: [$class: 'SpecificBuildSelector', buildNumber: "${upstreamBuildNumber}"]])
    }
    catch (e) {
        if (buildBranch == null) {
            // for standalone build, check artifcats at WORKSPACE
            if (fileExists(reportFile) == true) {
                print "Take preview-report-committer.json under WORKSPACE"
                return true
            }
        }
        unstable("JIRA action: copy artifacts ${reportFile} failed " + e)
        return false
    }

/*
    dir ('.pf-jira') {
        def defectsReportFile
        def targetFolder
        if (buildBranch != null) {
            defectsReportFile = "defectsReport-${buildBranch}.zip"
            targetFolder = ".defectsReport-${buildBranch}"
        }
        else {
            defectsReportFile = "defectsReport.zip"
            targetFolder = ".defectsReport"
        }

        try {
            step([$class: 'CopyArtifact', 
                    filter: defectsReportFile, 
                    flatten: false, 
                    projectName: upstreamJobName, 
                    selector: [$class: 'SpecificBuildSelector', buildNumber: "${upstreamBuildNumber}"], 
                    target: targetFolder])
            dir (targetFolder) {
                unzip zipFile: defectsReportFile
            }
        }
        catch (e) {
            print "JIRA action: copy artifacts ${defectsReportFile} failed " + e
            return true
        }
    }
*/

    return true
}

def jiraGetKeyFields(jiraConfig, pythonExec) {
    def plainStageName = jiraConfig["plainStageName"]
    if (jiraConfig["jira_credentials"] == "") {
        def siteFieldsIdMap = [:]
        def siteFieldsSchemaMap = [:]

        def ret = jiraGetFields site: jiraConfig["site_name"]
        def fields = ret.data
        for (def i=0; i<fields.size(); i++) {
            def field = fields[i]
            if (field.name == "Epic Link") {
                dir (".pf-${plainStageName}") {
                    writeJSON file: "epicLinkField.json", json: field
                }
            }
            else if (field.name == "Epic Name") {
                dir (".pf-${plainStageName}") {
                    writeJSON file: "epicNameField.json", json: field
                }
            }
            if (field.custom == true) {
                siteFieldsIdMap."${field.name}" = field.id
                // supported schema: array, option, string
                siteFieldsSchemaMap."${field.name}" = field.schema.type
            }
        }

        if (jiraConfig["defects_extra_fields"] != "") {
            jiraConfig["defects_extra_fields"] = readJSON text: jiraConfig["defects_extra_fields"]
        }
        else {
            jiraConfig["defects_extra_fields"] = [:]
        }
        def extraFieldsMap = [:]
        for (def key in jiraConfig["defects_extra_fields"].keySet()) {
            def fieldName = key.toString()
            if (siteFieldsIdMap.containsKey(fieldName)) {
                extraFieldsMap[fieldName] = [:]
                extraFieldsMap[fieldName]['id'] = siteFieldsIdMap[fieldName]

                def capturedValue = utils.captureStdout("echo ${jiraConfig['defects_extra_fields'][key]}", isUnix())
                capturedValue = capturedValue[0]
                if (siteFieldsSchemaMap[fieldName] == 'array') {
                    def option = [:]
                    option.value = capturedValue
                    extraFieldsMap[fieldName]['value'] = []
                    extraFieldsMap[fieldName]['value'] << option
                }
                else if (siteFieldsSchemaMap[fieldName] == "option") {
                    def option = [:]
                    option.value = capturedValue
                    extraFieldsMap[fieldName]['value'] = option
                }
                else { // string
                    extraFieldsMap[fieldName]['value'] = capturedValue
                }
            }
        }
        dir (".pf-${plainStageName}") {
            writeJSON file: 'extraFieldsMap.json', json: extraFieldsMap
        }
    }
    else {
        def stageName = jiraConfig["stageName"]
        withCredentials([string(credentialsId: jiraConfig["jira_credentials"], variable: 'JIRA_TOKEN')]) {
            def pyCmdFlush = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -w .pf-${plainStageName} -c FLUSH_LOG"
            def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -w .pf-${plainStageName} -f .pf-all/settings/${stageName}_config.json -c GET_JIRA_INFO"
            if (isUnix()) {
                sh pyCmdFlush
                sh pyCmd
            }
            else {
                bat pyCmdFlush
                bat pyCmd
            }
        }
    }
}

def defectsToJira(pythonExec, plainStageName) {
    def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -r .pf-all -w .pf-${plainStageName} -f .pf-${plainStageName}/stageConfig.json -c DEFECTS_TO_JIRA -d ."
    if (isUnix()) {
        sh pyCmd
    }
    else {
        bat pyCmd
    }
}

def func(stageName) {
    def jiraConfig = readJSON file: ".pf-all/settings/${stageName}_config.json"
    def plainStageName = jiraConfig["plainStageName"]

    def upstreamJobName = env.JOB_NAME
    def upstreamBuildNumber = env.BUILD_NUMBER
    if (env.UPSTREAM_JOB_NAME) {
        upstreamJobName = env.UPSTREAM_JOB_NAME
    }
    if (env.UPSTREAM_BUILD_NUMBER) {
        upstreamBuildNumber = env.UPSTREAM_BUILD_NUMBER
    }

    def pythonExec = utils.getPython()
    def translateCmd = "${pythonExec} .pf-all/pipeline_scripts/utils.py -f .pf-all/settings/${stageName}_config.json -c TRANSLATE_CONFIG"
    if (isUnix()) {
        sh translateCmd
    }
    else {
        bat translateCmd
    }
    if (jiraConfig["jira_credentials"] != "") {
        def validateCmd = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -w .pf-${plainStageName} -f .pf-all/settings/${stageName}_config.json -c VAL_PROJECT_KEY"
        withCredentials([string(credentialsId: jiraConfig["jira_credentials"], variable: 'JIRA_TOKEN')]) {
            if (isUnix()) {
                sh translateCmd
            }
            else {
                bat translateCmd
            }
        }
    }
    // reload after TRANSLATE_CONFIG
    jiraConfig = readJSON file: "${env.PF_ROOT}/settings/${stageName}_config.json"
    jiraConfig["defects_number_limit"] = jiraConfig["defects_number_limit"].toString().toInteger()

    jiraGetKeyFields(jiraConfig, pythonExec)
    if (jiraConfig.defects_to_jira == true || jiraConfig.defects_to_jira == "true") {
        if (jiraConfig.defects_issue_epic == "") {
            // take coverity project name as issue epic
            jiraConfig.defects_issue_epic = jiraConfig.coverity_project_name
        }
        getEPICKey(jiraConfig, pythonExec)

        jiraConfig.buildBranches = []
        if (env.BUILD_BRANCH) {
            // deprecated: would raise concurrent problem
            // jira in parallel build
            error "JIRA under parallel build: ${env.BUILD_BRANCH}"
        }
        else {
            if (env.PF_REMOTE_PARALLEL_BUILD) {
                // remote standalone/parallel build + jira
                // PF_REMOTE_PARALLEL_BUILD 0: remote standalone build
                // PF_REMOTE_PARALLEL_BUILD 1: remote parallel build
                def copyCmd = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -f ${env.PF_ROOT}/settings/${stageName}_config.json -w .pf-${plainStageName} -c COPY_REMOTE_ARTIFACTS -d ."
                if (isUnix()) {
                    sh copyCmd
                }
                else {
                    bat copyCmd
                }
                if (env.PF_REMOTE_PARALLEL_BUILD == "1") {
                    // remoteParallelInfo.json
                    def parallelInfo = readJSON file: ".pf-${plainStageName}/remoteParallelInfo.json"
                    for (def i=0; i<parallelInfo.branches.size(); i++) {
                        jiraConfig.buildBranches << parallelInfo.branches[i]
                    }
                }
            }
            else if (env.PF_GLOBAL_PARALLELINFO) {
                // parallel build + jira
                unstash name: 'pf-global-parallelinfo'
                def parallelInfo = readJSON file: 'parallelInfo.json'
                print "JIRA with parallel build: " + parallelInfo.branches
                for (def i=0; i<parallelInfo.branches.size(); i++) {
                    def buildBranch = parallelInfo.branches[i]
                    def ret = copyDefectsArtifacts(upstreamJobName, upstreamBuildNumber, buildBranch)
                    if (ret == true) {
                        jiraConfig.buildBranches << buildBranch
                    }
                    else {
                        print "Skip branch: ${buildBranch}"
                    }
                }
            }
            else {
                // single build + jira
                print "JIRA with single build "
                copyDefectsArtifacts(upstreamJobName, upstreamBuildNumber, null)
            }
        }

        dir (".pf-${plainStageName}") {
            // write buildBranches to stageConfig.json
            writeJSON file: 'stageConfig.json', json: jiraConfig
        }
        def pyCmd = "${pythonExec} .pf-all/pipeline_scripts/covjira.py -r .pf-all -w .pf-${plainStageName} -f .pf-${plainStageName}/stageConfig.json -c UPDATE_EXCLUDES"
        if (isUnix()) {
            sh pyCmd
        }
        else {
            bat pyCmd
        }
        getExistedJIRAIssues(jiraConfig, pythonExec)
        getComponentsMap(jiraConfig, pythonExec)

        if (env.PF_COV_CREDENTIALS == "") {
            defectsToJira(pythonExec, plainStageName)
        }
        else {
            withCredentials([file(credentialsId: env.PF_COV_CREDENTIALS, variable: 'COV_AUTH_KEY')]) {
                defectsToJira(pythonExec, plainStageName)
            }
        }
        publishIssuesToJIRA(jiraConfig, pythonExec)
        updateUndetectedDefectsLabel(jiraConfig, pythonExec)
    }

    if (jiraConfig.buildresult_to_jira == true && currentBuild.currentResult != "SUCCESS") {
            // create jira issue
            def jiraIssue = [fields: [
                                project: [key: jiraConfig.buildresult_jira_project],
                                summary: "${upstreamJobName} build ${upstreamBuildNumber} status ${currentBuild.currentResult}",
                                description: "",
                                issuetype: [name: "Issue"]]]
            response = jiraNewIssue issue: jiraIssue, auditLog: false, site: jiraConfig.site_name
            //print response.data.toString()
            
            if (response.successful == true) {
                // assign jira issue
                def issueKey = response.data.key
                jiraAssignIssue idOrKey: issueKey, 
                    userName: jiraConfig.buildresult_default_assignee, 
                    accountId: "",
                    site: jiraConfig.site_name
            }
    }
}

return this