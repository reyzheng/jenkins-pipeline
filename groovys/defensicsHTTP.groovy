def init(stageName) {
    def defaultConfigs = [
        url: "",
        //credentials: "",
        api_token: "74e74f46-8f4d-4b20-8f1d-c5963c59fd35",
        test_suite: "",
        set_file: "",

        fuzzbox_ip: "",
        fuzzbox_account: "",
        fuzzbox_password: "",

        export_report: true
    ]

    def utils = load "utils.groovy"
    def config = utils.commonInit(stageName, defaultConfigs)

    if (config.settings.url != "") {
        print "check defensics availability on ${config.settings.url}"
        def curlCmd = "curl --insecure -H 'Authorization: Bearer ${config.settings.api_token}' ${config.settings.url}/api/v2/version"
        def status = sh script: curlCmd, returnStdout: true
        try {
            def json = readJSON text: status
            print "Found defensics " + json.data.monitorVersion
        }
        catch (e) {
            error("Invalid defensics url")
        }
    }

    if (config.settings.test_suite == "80211ap" || config.settings.test_suite == "80211c") {
        // check fuzzbox availability
        def testScript = "sshpass -p ${config.settings.fuzzbox_password} ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 ${config.settings.fuzzbox_account}@${config.settings.fuzzbox_ip} 'exit 0'"
        def statusCode = sh script:testScript, returnStatus:true
        if (statusCode != 0) {
            error("Invalid fuzzobx configuration")
        }
    }

    dir (env.PF_PATH + 'scripts') {
        stash name: "stash-${stageName}-setfile", includes: config.settings.set_file
    }

    return config
}

def setupFuzzBox(ipAddr, account, password) {
    sh "sshpass -p '${password}' scp -o \"StrictHostKeyChecking=no\" ${account}@${ipAddr}:/opt/Synopsys/FuzzBox/certs/fbca.crt ./"
    def fuzzboxCaCert = sh(script: "sed -z 's/\\n//g' fbca.crt", returnStdout: true).trim()
    def endIndex = fuzzboxCaCert.lastIndexOf("-----END CERTIFICATE-----")
    // skip -----BEGIN CERTIFICATE-----
    fuzzboxCaCert = fuzzboxCaCert.substring(27, endIndex)

    def certObject = [:]
    certObject."version" = 1.0
    certObject."fuzzboxes" = []
    fuzzboxObject = [:]
    fuzzboxObject."name" = ipAddr + "-pipeline"
    fuzzboxObject."hostname" = ipAddr
    fuzzboxObject."fuzzboxCaCert" = fuzzboxCaCert
    fuzzboxObject."clientCert" = "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"
    certObject."fuzzboxes" << fuzzboxObject
    writeJSON file: '/k8s/defensics/tmp/fuzzboxes.json', json: certObject
    /*
    sh """
        echo 'debug fuzzboxes.json'
        pwd && cat fuzzboxes.json
    """
    */

    // /opt/Synopsys/FuzzBox/nginx
    //     conf.d/80211scanner.secure.conf
    //     conf.d/defensics-core-services.secure.conf
    //     stream.conf.d/80211socket.secure.conf
    //sh "sshpass -p '123456qwerty' ssh -o "StrictHostKeyChecking=no" root@${ipAddr} \"sed -e '/ssl_verify_client/ s/^#*/#/' -i /etc/nginx/conf.d/defensics-core-services.secure.conf\""
    //sh "sshpass -p '123456qwerty' ssh -o "StrictHostKeyChecking=no" root@192.168.56.110 \"systemctl restart nginx\""
}

def loadTestSuite(baseUrl, configs) {
    def feature
    switch(configs.test_suite) {
        case "ipv4":
            feature = "d3-ipv4"
            break
        case "dns-client":
            feature = "d3-dns-client"
            break
        case "rtsp":
            feature = "d3-rtsp-server"
            break
        case "80211ap":
            setupFuzzBox(configs.fuzzbox_ip, configs.fuzzbox_account, configs.fuzzbox_password)
            feature = "d3-80211ap-fp1"
            break
        case "80211c":
            setupFuzzBox(configs.fuzzbox_ip, configs.fuzzbox_account, configs.fuzzbox_password)
            feature = "d3-80211c-fp1"
            break
        default:
            error("Unsupported test suite ${configs.test_suite}")
            break
    }

    def url = "${baseUrl}/suites/${feature}/load"
    def response = sh(script: "curl ${url} -k -X POST -H \"Accept: application/json\" -H \"Authorization: Bearer ${configs.api_token}\"", returnStdout: true).trim()
    print "Load test suite: " + response
    def retObj = readJSON text: response
    if (retObj.errors) {
        return null
    }
    else {
        return retObj.data.id
    }
}

def queryLoadingStatus(baseUrl, apiToken, testSuiteId) {
    def url = "${baseUrl}/suite-instances/${testSuiteId}"

    def response = sh(script: "curl ${url} -k -X GET -H \"Accept: application/json\" -H \"Authorization: Bearer ${apiToken}\"", returnStdout: true).trim()
    print "queryLoadingStatus: " + response
    def retObj = readJSON text: response
    if (retObj.data.state == "LOADED") {
        return true
    }
    else {
        return false
    }
    
}

def createRun(baseUrl, apiToken) {
    def url = "${baseUrl}/runs"
    def response = sh(script: "curl ${url} -k -X POST -H \"Accept: application/json\" -H \"Authorization: Bearer ${apiToken}\"", returnStdout: true).trim()
    def testRun = readJSON text: response
    print "Create run: ${testRun.data.id}"
    return testRun.data.id
}

def assignTestSuite(baseUrl, apiToken, runId, testSuiteId) {
    def url = "${baseUrl}/runs/${runId}/configuration/assign-suite"
    def jsonParameter = [:]
    jsonParameter."suiteInstanceId" = testSuiteId
    writeJSON file: 'data.json', json: jsonParameter
    def response = sh(script: "curl ${url} -w '%{http_code}' -k -X POST -d@data.json -H \"Content-Type: application/json\" -H \"Accept: application/json\" -H \"Authorization: Bearer ${apiToken}\"", returnStdout: true).trim()

    if (response == "204") {
        print "Assign test suite success"
        return true
    }
    else {
        print "Assign test suite fail"
        return false
    }
}

def loadSettings(baseUrl, apiToken, runId, stageName, setFile) {
    def url = "${baseUrl}/runs/${runId}/configuration/settings"

    def response = sh(script: "curl ${url} -k -X GET -H \"Content-Type: application/json\" -H \"Accept: application/json\" -H \"Authorization: Bearer ${apiToken}\"", returnStdout: true).trim()
    print "Available settings: " + response

    unstash name: "stash-${stageName}-setfile"
    def file = readFile setFile
    def lines = file.readLines()

    def json = [:]
    json.settings = []
    for (def line in lines) {
        def tokens = line.split(" ")
        def cfg = [:]
        cfg.name = tokens[0].substring(2, tokens[0].length())
        if (tokens.size() > 1) {
            cfg.value = tokens[1]
        }
        else {
            if (cfg.name == "loop") {
                cfg.value = true
            }
        }
        if (cfg.name == "device" || cfg.name == "virtual-ip" || cfg.name == "virtual-ip-instr" || cfg.name == "instr-device") {
            cfg.autoConfigureTarget = [:]
            cfg.autoConfigureTarget.state = "DISABLED"
        }
        json.settings << cfg
    }

    writeJSON file: 'data.json', json: json
    print "loadSettings: "
    sh "cat data.json"

    response = sh(script: "curl ${url} -k -X POST -d@data.json -H \"Content-Type: application/json\" -H \"Accept: application/json\" -H \"Authorization: Bearer ${apiToken}\"", returnStdout: true).trim()
    print "Apply settings: " + response
    return true
}

def startRun(baseUrl, apiToken, runId) {
    def url = "${baseUrl}/runs/${runId}/start"
    def response = sh(script: "curl ${url} -w '%{http_code}' -k -X POST -H \"Accept: application/json\" -H \"Authorization: Bearer ${apiToken}\"", returnStdout: true).trim()
    if (response == "204") {
        print "Start run ${runId} success"
    }
    else {
        print "Start run ${runId} fail"
    }
}

def waitingRun(baseUrl, apiToken, runId) {
    def url = "${baseUrl}/runs/${runId}"

    while (true) {
        print "Query test run status"
        sleep 10
        def response = sh(script: "curl ${url} -k -X GET -H \"Accept: application/json\" -H \"Authorization: Bearer ${apiToken}\"", returnStdout: true).trim()
        //print "181 " + response
        def json = readJSON text: response
        if (json.data.state == "IDLE" || json.data.state == "COMPLETED" || json.data.state == "ERROR" || json.data.state == "FATAL") {
            print "test run stopped: ${json.data.state}"
            return json.data.resultId
        }
    }
}

def deleteRun(baseUrl, apiToken, runId) {
    def url = "${baseUrl}/runs/${runId}"
    sh(script: "curl ${url} -k -X DELETE -H \"Accept: application/json\" -H \"Authorization: Bearer ${apiToken}\"", returnStdout: true).trim()
}

def unloadTestSuite(baseUrl, apiToken, testSuiteId) {
    def url = "${baseUrl}/suite-instances/${testSuiteId}"
    sh(script: "curl ${url} -k -X DELETE -H \"Accept: application/json\" -H \"Authorization: Bearer ${apiToken}\"", returnStdout: true).trim()
}

def exportReport(baseUrl, apiToken, resultId) {
    // curl -k -H 'Authorization: Bearer 74e74f46-8f4d-4b20-8f1d-c5963c59fd35' 
    // 'https://192.168.56.101:9090/api/v2/results/result-package?resultId=2a3939f9-2a30-4d94-af9a-4f46e50b6b05' --output remediation.zip
    def url = "${baseUrl}/results/report?resultId=${resultId}\\&format=report"
    sh """
        curl -k -H \"Authorization: Bearer ${apiToken}\" ${url} --output defensics-report.html 
    """
    archiveArtifacts artifacts: "defensics-report.html"

    url = "${baseUrl}/results/report?resultId=${resultId}\\&format=summary"
    sh """
        curl -k -H \"Authorization: Bearer ${apiToken}\" ${url} --output defensics-summary.html
    """
    archiveArtifacts artifacts: "defensics-summary.html"
}

def startTest(configs, preloads) {
    def resultId = "0"
    def stageName = preloads.stageName
    def baseUrl = configs.url + "/api/v2"
    dir (".pf-defensics") {
        def loadingStatus = false
        def testSuiteId = loadTestSuite(baseUrl, configs)
        print "Test suite '${configs.test_suite}' id: ${testSuiteId} loaded"
        if (testSuiteId == null) {
            return
        }
        for (def i=0; i<6; i++) {
            // wait 90 seconds max.
            print "Query suite loading status"
            sleep 15
            loadingStatus = queryLoadingStatus(baseUrl, configs.api_token, testSuiteId)
            if (loadingStatus == true) {
                break
            }
        }
        if (loadingStatus == true) {
            def runId = createRun(baseUrl, configs.api_token)
            if (assignTestSuite(baseUrl, configs.api_token, runId, testSuiteId) == true) {
                print "Load and start run"
                if (loadSettings(baseUrl, configs.api_token, runId, stageName, configs.set_file) == true) {
                    startRun(baseUrl, configs.api_token, runId)
                    resultId = waitingRun(baseUrl, configs.api_token, runId)

                    deleteRun(baseUrl, configs.api_token, runId)
                    unloadTestSuite(baseUrl, configs.api_token, testSuiteId)
                }
            }
            else {
                deleteRun(baseUrl, configs.api_token, runId)
            }
        }
        else {
            unloadTestSuite(baseUrl, configs.api_token, testSuiteId)
        }

        if (configs.export_report == true && resultId != "0") {
            exportReport(baseUrl, configs.api_token, resultId)
        }
    }

    /*
    def defensicsScreen = "screen-${env.JOB_NAME}-${env.BUILD_NUMBER}"
    def defensicsScreenLog = "screenlog-${env.JOB_NAME}-${env.BUILD_NUMBER}.txt"
    if (configs.screen_enabled == true) {
        sh """
            # remember to restart agent if screen failed
            JENKINS_NODE_COOKIE=dontKillMe screen -dm -S ${defensicsScreen} -L -Logfile ${defensicsScreenLog} ${configs.screen_tty} ${configs.screen_baud}
            screen -ls
        """
    }
    if (configs.screen_enabled == true) {
        sh """
            screen -X -S ${defensicsScreen} kill
        """
        archiveArtifacts artifacts: defensicsScreenLog
    }
    */

    // outside docker
    /*
    def reportDir = "defensics-report"
    if (configs.export_report == true) {
        dir(WORKSPACE) {
            archiveArtifacts artifacts: "${reportDir}/report.html"
        }
    }
    if (configs.export_remediation == true) {
        dir(WORKSPACE) {
            archiveArtifacts artifacts: "${reportDir}/remediation.zip"
        }
    }
    // prevent next build failure, ${reportDir} created by root
    withDockerServer([uri: 'tcp://localhost:4243']) {
        def args = "-u root --mount type=bind,src=$WORKSPACE,dst=/tmp/report"
        withDockerContainer(args: args, image: 'defensics-exec-image') {
            sh """
                rm -rf ${reportDir}
            """
        }
    } // inside docker
    */
    //}
}

def func(pipelineAsCode, configs, preloads) {
    startTest(configs, preloads)
    /*
    if (configs.node == "" || env.NODE_NAME == configs.node) {
        startTest(configs, preloads)
    }
    else {
        node(configs.node) {
            startTest(configs, preloads)
        }
    }
    */
}

return this