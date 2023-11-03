def init(stageName) {
    def utils = load "utils.groovy"
    def defaultConfigs = [
        display_name: "HSM",
        hsm_credential: "",
        hsm_authcode: "",
        hsm_src_files: [],
        hsm_dst_files: [],
        hsm_sha_types: [],

        scriptableParams: ["hsm_src_files", "hsm_dst_files", "hsm_sha_types"]
    ]
    def config = utils.commonInit(stageName, defaultConfigs)
    utils.stashScriptedParamScripts(config.settings)

    return config
}

def extractFilenameFromPath(fullPath) {
    def srcFileToken
    if (fullPath.contains("/")) {
        srcFileToken = fullPath.split("/")
    }
    else {
        srcFileToken = fullPath.split(/\\{1}/)
    }
    return srcFileToken[srcFileToken.size() - 1]
}

def call(Map config = [:]) {
    def underUnix = isUnix()
    def defaultConfig = [
        hsm_credential: '',
        hsm_authcode: '',
        hsm_src_files: '',
        hsm_dst_files: '',
        hsm_sha_types: '',
        hsm_semaphore: "hsmLock-user"
    ]
    defaultConfig << config
    /*
    if (defaultConfig.hsm_semaphore == null) {
        defaultConfig.hsm_semaphore = "hsmLock-user"
    }
    */

    def filesToSign = findFiles glob: defaultConfig.hsm_src_files
    print "Found files to sign: " + filesToSign
    for (def srcFile in filesToSign) {
        def srcFileNameRaw = extractFilenameFromPath(srcFile.path)

        //def srcFile = defaultConfig.hsm_src_files
        if (srcFile.path.endsWith(".zip") == false) {
            def hsmTemporalFolder = Math.abs(new Random().nextInt())
            if (underUnix == true) {
                sh "mkdir -p ${hsmTemporalFolder}"
                sh "cp -a $srcFile ${hsmTemporalFolder}"
            }
            else {
                bat "if not exist \"${hsmTemporalFolder}\" mkdir ${hsmTemporalFolder}"
                bat "xcopy $srcFile ${hsmTemporalFolder} /Y"
            }
            // zip step cannot zip file, folders only
            zip zipFile: 'hsmTemporal.zip', dir: "$hsmTemporalFolder", overwrite: true
            srcFile = 'hsmTemporal.zip'
        }
        else {
            srcFile = srcFile.path
        }

        def srcFileName = extractFilenameFromPath(srcFile)
        def shaType = defaultConfig.hsm_sha_types
        def dstFile = defaultConfig.hsm_dst_files

        def outputTmp = "signed-stuff.zip"
        withCredentials([string(credentialsId: defaultConfig.hsm_authcode, variable: 'AUTH_CODE')]) {
            lock (defaultConfig.hsm_semaphore) {
                print "Get lock: " + defaultConfig.hsm_semaphore
                // HTTP Request 1.14 required
                def response = httpRequest httpMode: 'POST',
                                        authentication: defaultConfig.hsm_credential, 
                                        formData: [
                                            [body: shaType, contentType: '', fileName: '', name: 'shaType', uploadFile: ''],
                                            [body: AUTH_CODE, contentType: '', fileName: '', name: 'authCode', uploadFile: ''],
                                            [body: '', contentType: '', fileName: srcFileName, name: 'File', uploadFile: srcFile]
                                        ], 
                                        //outputFile: dstFile, 
                                        outputFile: outputTmp, 
                                        responseHandle: 'LEAVE_OPEN', 
                                        timeout: 300,
                                        url: 'https://certsign.realtek.com/api/SignAPI/HSMSign', 
                                        ignoreSslErrors: true,
                                        wrapAsMultipart: false
                response.close()
                // check outputTmp is ZIP
                unzip zipFile: outputTmp, dir: ".test-unzip"
                dir (".test-unzip") {
                    deleteDir()
                }

                if (dstFile.endsWith("\\") || dstFile.endsWith("/")) {
                    def srcFileNameTokens = srcFileNameRaw.split("\\.")
                    dir (dstFile) {
                        writeFile file: '.dummy', text: ' '
                        print "HSM: move signed file to ${dstFile}"
                    }
                    // hsm_dst_files is directory
                    if (underUnix == true) {
                        sh "mv ${outputTmp} $dstFile/${srcFileNameTokens[0]}-signed.zip"
                    }
                    else {
                        bat("move ${outputTmp} $dstFile\\${srcFileNameTokens[0]}-signed.zip")
                    }
                    def dstFileName = dstFile
                    dir (dstFile) {
                        archiveArtifacts artifacts: "${srcFileNameTokens[0]}-signed.zip"
                    }
                }
                else {
                    // unzip if suffix is not ".zip"
                    if (dstFile.endsWith(".zip") == false) {
                        def hsmTemporalFolder = Math.abs(new Random().nextInt())
                        // TODO: cannot determine sign result by HTTP code
                        // catch unzip exception is stupid
                        try {
                            unzip zipFile: outputTmp, dir: "${hsmTemporalFolder}"
                        }
                        catch (e) {
                            def errorMessage = readFile outputTmp
                            error("HSM error: " + errorMessage)
                        }
                        if (underUnix == true) {
                            sh "mv ${hsmTemporalFolder}/* $dstFile"
                        }
                        else {
                            bat("move ${hsmTemporalFolder}\\* $dstFile")
                        }
                    }
                    else {
                        if (underUnix == true) {
                            sh "mv ${outputTmp} $dstFile"
                        }
                        else {
                            bat("move ${outputTmp} $dstFile")
                        }
                    }
                    def dstFileName = dstFile
                    if (dstFileName.startsWith(WORKSPACE)) {
                        if (underUnix == true) {
                            dstFileName = dstFileName.substring(dstFileName.lastIndexOf("/") + 1)
                        }
                        else {
                            dstFileName = dstFileName.substring(dstFileName.lastIndexOf("\\") + 1)
                        }
                    }
                    archiveArtifacts artifacts: dstFileName
                }
                print "Release lock: " + defaultConfig.hsm_semaphore
            }
        }

    }
}

def func(pipelineAsCode, hsmConfigRaw, hsmPreloads) {
    unstash name: "stash-script-utils"
    def utils = load "utils.groovy"
    def hsmConfig = [:]
    utils.unstashScriptedParamScripts(hsmPreloads.plainStageName, hsmConfigRaw, hsmConfig)

    try {
        for (def hsmIte=0; hsmIte<hsmConfig.hsm_src_files.size(); hsmIte++) {
            def config = [:]
            config.hsm_credential = hsmConfig.hsm_credential
            config.hsm_authcode = hsmConfig.hsm_authcode
            config.hsm_src_files = hsmConfig.hsm_src_files[hsmIte]
            config.hsm_dst_files = hsmConfig.hsm_dst_files[hsmIte]
            config.hsm_sha_types = hsmConfig.hsm_sha_types[hsmIte]
            call(config)
        }
    }
    catch (e) {
        error "HSM error: $e"
    }
}

return this