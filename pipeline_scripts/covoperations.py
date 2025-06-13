import os, re, sys, json
import subprocess as sb
import utils

def generateLicenseFile(licPath):
    utils.lightLogging('generateLicenseFile: path {}'.format(licPath))
    # change license server to venus5
    licenseServer = '#FLEXnet (do not delete this line)\nlicense-server 1123@172.21.12.98\n'
    with open(licPath, 'w') as fpLic:
        fpLic.write(licenseServer)

def addEmitDB(idir, coverityCommitAdditional, covCmdPrefixes, covScanPath, cmdEnv):
    additionals = coverityCommitAdditional.split(',')
    for additional in additionals:
        utils.heavyLogging('addEmitDB: {}'.format(additional))
        utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-manage-emit'), \
                                                '--dir', idir, 'add', additional], cmdEnv)

def manageEmitDB(idir, covCmdPrefixes, covScanPath, srcDir):
    #filesToRemove = []
    filesToPreserve = []
    pwd = os.getcwd()
    utils.heavyLogging('manageEmitDB: working dir {}'.format(pwd))
    # purge
    cmdPurge = sb.Popen(covCmdPrefixes + [os.path.join(covScanPath, 'cov-manage-emit'), '--dir', idir, '--tus-per-psf=non-latest', 'delete'], stdout=sb.PIPE)
    cmdPurge.wait()

    BLAME_PATH_PATTERN = dict()
    if os.path.isfile('{}/scripts/covBlameReplacement.txt'.format(os.getenv('PF_ROOT'))) == True:
        fpBlamePath = open('{}/scripts/covBlameReplacement.txt'.format(os.getenv('PF_ROOT')), 'r')
        while True:
            line = fpBlamePath.readline()
            if not line:
                break
            if line.startswith('#'):
                continue
            tokens = line.split(':')
            if len(tokens) > 1:
                BLAME_PATH_PATTERN[tokens[0]] = tokens[1].strip()
        fpBlamePath.close()

    fullSrcDir = os.path.join(os.getenv('WORKSPACE'), srcDir)
    tuList = sb.Popen(covCmdPrefixes + [os.path.join(covScanPath, 'cov-manage-emit'), '--dir', idir, 'list'], stdout=sb.PIPE)
    while True:
        line = tuList.stdout.readline()
        if not line:
            break
        if line[:1].isdigit():
            line = bytes.decode(line, 'utf-8')
            tokens = line.split()

            realPath = tokens[2]
            for pattern in BLAME_PATH_PATTERN:
                if re.match(pattern, realPath):
                    realPath = re.sub(r'{}'.format(pattern), BLAME_PATH_PATTERN[pattern], realPath)
                    utils.lightLogging('manageEmitDB: real filepath(re.sub) {}'.format(realPath))
                    break

            realDir = os.path.dirname(os.path.abspath(realPath))
            realFilename = os.path.basename(realPath)
            #dir = os.path.dirname(os.path.abspath(tokens[2]))
            #filename = os.path.basename(tokens[2])
            utils.lightLogging('manageEmitDB: check file {}'.format(tokens[2]))
            try:
                os.chdir(realDir)
                cmdLog = sb.Popen(['git', 'log', '--committer=realtek', '--committer=realsil', '--committer=apowertec', \
                                    '--format=', '--name-only', '--no-merges', 'HEAD', '{}'.format(realFilename)], stdout=sb.PIPE)
                if os.name == "posix":
                    uniqOutput = sb.check_output(('uniq'), stdin=cmdLog.stdout)
                else:
                    uniqOutput = sb.check_output(('sort', '/unique'), stdin=cmdLog.stdout)
                cmdLog.wait()
                uniqLines = uniqOutput.decode("utf-8").splitlines()
                if len(uniqLines) == 0 or uniqLines[0] == "":
                    # not realtek/realsil/apowertec edited
                    utils.lightLogging('manageEmitDB: remove {}'.format(tokens[2]))
                    #filesToRemove.append(tokens[2])
                else:
                    filesToPreserve.append("-tp")
                    filesToPreserve.append("file('{}')".format(os.path.relpath(tokens[2], fullSrcDir)))
                    utils.lightLogging('manageEmitDB: preserve {}'.format(os.path.relpath(tokens[2], fullSrcDir)))
            except Exception as e:
                # An exception occurred
                # file not existed, in emit-db only (caused by incremental build)
                utils.heavyLogging('manageEmitDB: remove(exception) {}'.format(tokens[2]))
                utils.heavyLogging(e)
                #filesToRemove.append(tokens[2])
    os.chdir(pwd)
    return filesToPreserve
    #for fileToRemove in filesToRemove:
    #    utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-manage-emit'), '--dir', idir, '-tp=file(\'{}\')'.format(fileToRemove), 'delete'], cmdEnv)

def diffGerritPatchsetToNegtivePattern(workDir):
    diffs = []
    if os.path.isfile(os.path.join(workDir, 'gerrit-patchset.diff')):
        fpDiff = open(os.path.join(workDir, 'gerrit-patchset.diff'), 'r')
        while True:
            # Get next line from file
            line = fpDiff.readline().strip()
            if line != '':
                baseFilename = os.path.basename(line)
                line = baseFilename.replace('.', '\.')
                # ?! negative look ahead
                # ?i case insensitive
                diffs.append('(?!(?i){})'.format(line))
            # if line is empty
            # end of file is reached
            if not line:
                break
        fpDiff.close()
    return diffs

def covConfigureSkipFiles(workDir, skipParams):
    diffs = []
    if 'PF_DIFF_GERRIT_PATCHSET' in skipParams:
        diffs = diffGerritPatchsetToNegtivePattern(workDir)

    # do not skip pre-compiled header, ex) PF_COV_PCH:Mp_Precomp_src.c
    for skipParam in skipParams:
        if skipParam.startswith('PF_COV_PCH:'):
            tokens = skipParam.split(':')
            baseFilename = os.path.basename(tokens[1])
            baseFilename = baseFilename.replace('.', '\.')
            diffs.append('(?!(?i){})'.format(baseFilename))

    diffStr = ''.join(diffs)
    return "--xml-option=skip_file:^({}.)*$".format(diffStr)

def covConfigure(configs, configIdx, covCmdPrefixes, covScanPath, coverityXml, cmdEnv):
    ret = dict()
    ret['isInterpretingLanguage'] = False
    ret['ignorePCH'] = False

    interpretingLanguages = ['python']

    extraConfigureArgs = []
    try:
        if configs['coverity_configure_option'][configIdx] != '':
            skipParams = []
            covConfigureArgs = configs['coverity_configure_option'][configIdx]
            covConfigureArgs = covConfigureArgs.split(',')
            for covConfigureArg in covConfigureArgs:
                if covConfigureArg == 'PF_DIFF_GERRIT_PATCHSET':
                    #if configs['coverity_analyze_parent'] == 'none':
                    #    utils.heavyLogging('covConfigure: PF_DIFF_GERRIT_PATCHSET is invalid if "Coverity Analyze Base Repository" disabled')
                    #    sys.exit(-1)
                    #else:
                    skipParams.append(covConfigureArg)
                elif covConfigureArg.startswith('PF_COV_PCH:'):
                    skipParams.append(covConfigureArg)
                else:
                    covConfigureTokens = covConfigureArg.split()
                    extraConfigureArgs.extend(covConfigureTokens)
                    #extraConfigureArgs.append(covConfigureArg)
            if len(skipParams) > 0:
                extraConfigureArgs.append(covConfigureSkipFiles(configs['workDir'], skipParams))
    except Exception as e:
        utils.heavyLogging('covConfigure: invalid coverity_configure_option config')
        utils.heavyLogging(e)
    utils.heavyLogging('covConfigure: extraConfigureArgs {}'.format(extraConfigureArgs))

    templateConfiguration = ['--template']
    if 'coverity_static_configuration' in configs and configs['coverity_static_configuration'] == True:
        templateConfiguration = []
    # cov-configure --platform
    try:
        if configs['coverity_comptype_platform'][configIdx] != '':
            buildPlatforms = configs['coverity_comptype_platform'][configIdx].split(',')
            for buildPlatform in buildPlatforms:
                # TODO: windows
                utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-configure'), '--config', coverityXml, \
                                                            '--{}'.format(buildPlatform)] + extraConfigureArgs + templateConfiguration, cmdEnv)
                if buildPlatform in interpretingLanguages:
                    ret['isInterpretingLanguage'] = True
                if buildPlatform == 'msvc':
                    ret['ignorePCH'] = True
    except:
        utils.heavyLogging('covConfigure: invalid coverity_comptype_platform config')
    # cov-configure --comptype prefix
    try:
        if configs['coverity_comptype_prefix'][configIdx] != '':
            compPrefixes = configs['coverity_comptype_prefix'][configIdx].split(',')
            for compPrefix in compPrefixes:
                utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-configure'), '--config', coverityXml, \
                                                            '--comptype', 'prefix', '--compiler', compPrefix] + templateConfiguration, cmdEnv)
    except:
        utils.heavyLogging('covConfigure: invalid coverity_comptype_prefix config')
    # cov-configure --comptype COMPILER_TYPE --compiler COMPILER
    try:
        if configs['coverity_comptype'][configIdx] != '':
            comptypes = configs['coverity_comptype'][configIdx].split(',')
            compilers = configs['coverity_comptype_gcc'][configIdx].split(',')
            for i in range(len(compilers)):
                compiler = compilers[i]
                comptype = ''
                if len(comptypes) > i:
                    comptype = comptypes[i]
                if comptype == '':
                    utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-configure'), '--config', coverityXml, \
                                                                '--compiler', compiler] + extraConfigureArgs + templateConfiguration, cmdEnv)
                else:
                    utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-configure'), '--config', coverityXml, \
                                                                '--comptype', comptype, '--compiler', compiler] + extraConfigureArgs + templateConfiguration, cmdEnv)
    except:
        utils.heavyLogging('covConfigure: invalid coverity_comptype, coverity_comptype_gcc config')

    utils.heavyLogging('covConfigure: result {}'.format(ret))
    return ret

def covBuild(configs, covCmdPrefixes, covScanPath, coverityXml, coverityBuildDir, extraBuildArgs, buildIdx, \
                ignorePCH, isInterpretingLanguage, cmdEnv):
    if ignorePCH == True:
        cmdEnv['COV_IGNORE_PCH'] = '1'
    utils.lightLogging('coverityScan: cov-build with env {}'.format(cmdEnv))
    if configs['types'][buildIdx] == 'inline':
        if isInterpretingLanguage == True:
            buildCommand = '--dir {} --config {} {} --no-command --fs-capture-search {}'.format(coverityBuildDir, coverityXml, extraBuildArgs, configs['contents'][buildIdx])
        else:
            buildCommand = '--dir {} --config {} {} {}'.format(coverityBuildDir, coverityXml, extraBuildArgs, configs['contents'][buildIdx])
        utils.heavyLogging('coverityScan: COVBUILD {}'.format(buildCommand))
        # TODO: buildCommand.split() may be failed on windows (folder name with space)
        covBuildRet = utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-build')] + buildCommand.split(), cmdEnv)
    elif 'USR_COV_BUILD_DIR' in os.environ:
        cmd = '--dir {} --config {} --initialize'.format(coverityBuildDir, coverityXml)
        utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-build')] + cmd.split(), cmdEnv)
        scriptFile = os.path.join(os.getenv('WORKSPACE'), '.pf-all', 'scripts', configs['contents'][buildIdx])
        fpScript = open(scriptFile, 'r')
        while True:
            line = fpScript.readline()
            if not line:
                break
            if line.startswith('#') == False:
                cmd = '--dir {} --config {} {} --capture {}'.format(coverityBuildDir, coverityXml, extraBuildArgs, line)
                utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-build')] + cmd.split(), cmdEnv)
        fpScript.close()
        cmd = '--dir {} --config {} --finalize'.format(coverityBuildDir, coverityXml)
        covBuildRet = utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-build')] + cmd.split(), cmdEnv)
    else:
        scriptFile = os.path.join('.pf-all', 'scripts', configs['contents'][buildIdx])
        if os.name == 'posix':
            shell = 'sh'
            statusCode = utils.popenReturnCode(['bash'], cmdEnv)
            if statusCode == 0:
                shell = 'bash'
            # ALLOW_NINJA_ENV should be placed in front of cov-build
            import socket
            cmdEnv['COV_HOST'] = socket.gethostname()
            cmdEnv['ALLOW_NINJA_ENV'] = '1'
            cmd = '--dir {} --config {} {} {} {}'.format(coverityBuildDir, coverityXml, extraBuildArgs, shell, scriptFile)
        else:
            if scriptFile.endswith('.sh'):
                # cygwin shell script
                cygpathOutput = utils.popenReturnStdout('cygpath {}'.format(os.path.join(os.getenv('WORKSPACE'), scriptFile)), cmdEnv)
                cygpathOutputLines = cygpathOutput['lines']
                cmd = '--dir {} --config {} {} bash -c {}'.format(coverityBuildDir, coverityXml, extraBuildArgs, cygpathOutputLines[0].decode('utf-8'))
            else:
                # windows batch
                cmd = '--dir {} --config {} {} {}'.format(coverityBuildDir, coverityXml, extraBuildArgs, scriptFile)
        if os.name == 'posix':
            covBuildRet = utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-build')] + cmd.split(), cmdEnv)
        else:
            #covBuildRet = utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-build')] + cmd.split(), cmdEnv)
            logStdout = os.path.join(configs['workDir'], 'cov-build.stdout')
            logStderr = os.path.join(configs['workDir'], 'cov-build.stderr')
            covBuildRet = utils.popenToFile(covCmdPrefixes + [os.path.join(covScanPath, 'cov-build')] + cmd.split(), cmdEnv, logStdout, logStderr)
            fpCov = open(logStdout, 'rb')
            while True:
                line = fpCov.readline()
                if not line:
                    break
                utils.heavyLogging('covBuild(stdout): {}'.format(line.decode('utf-8', errors='ignore').rstrip()))
            fpCov.close()
            fpCov = open(logStderr, 'rb')
            while True:
                line = fpCov.readline()
                if not line:
                    break
                utils.heavyLogging('covBuild(stderr): {}'.format(line.decode('utf-8', errors='ignore').rstrip()))
            fpCov.close()
    utils.heavyLogging('coverityScan: end of cov-build {}'.format(covBuildRet))
    if covBuildRet != 0:
        utils.heavyLogging('coverityScan: cov-build error {}'.format(covBuildRet))
        utils.saveEnv(configs['workDir'], 'COVERITY_FAILURE_BUILD', covBuildRet)
        if configs['coverity_codetek_training'] == 'iterate':
            pass
        else:
            sys.exit(covBuildRet)

def covCommit(configs, configIdx, covCmdPrefixes, covScanPath, coverityBuildDir):
    cmdEnv = dict(os.environ)
    licPath = os.path.join(configs['workDir'], '.coverity.license.config')

    if configs['coverity_host'] == '':
        snapshotID = 0
    else:
        extraParameters = []
        if 'coverity_commit_excluded' in configs and len(configs['coverity_commit_excluded']) > configIdx:
            if configs['coverity_commit_excluded'][configIdx] != '':
                # Option 'exclude-files' may only appear on the command line once.
                if configs['coverity_commit_excluded'][configIdx] == 'N_PF_DIFF_GERRIT_PATCHSET':
                    extraParameters.append('--exclude-files')
                    diffs = diffGerritPatchsetToNegtivePattern(configs['workDir'])
                    extraParameters.append('^({}.)*$'.format(''.join(diffs)))
                else:
                    excludes = configs['coverity_commit_excluded'][configIdx].split(',')
                    for i in range(len(excludes)):
                        if excludes[i].endswith('/') or excludes[i].endswith('\\'):
                            # directory
                            excludes[i] = excludes[i] + ".*"
                    extraParameters.append('--exclude-files')
                    extraParameters.append('({})'.format('|'.join(excludes)))

        if os.name == 'posix':
            os.chmod(os.getenv('COV_AUTH_KEY'), 0o600)
        if configs['coverity_stream'][configIdx] == '':
            utils.heavyLogging('covCommit: empty coverity stream')
            sys.exit(1)
        commitScript = covCmdPrefixes + \
                        [os.path.join(covScanPath, 'cov-commit-defects'), '-sf', licPath, '--dir', coverityBuildDir] + \
                        ['--url', 'http://{}:{}'.format(configs['coverity_host'], configs['coverity_port'])] + \
                        ['--stream', configs['coverity_stream'][configIdx], '--auth-key-file', os.getenv('COV_AUTH_KEY'), '--encryption', 'none'] + extraParameters
        if configs['basePhase'] == True:
            previewReportPath = 'preview_report_v2_parent.json'
        else:
            previewReportPath = 'preview_report_v2.json'
        commitReportScript = covCmdPrefixes + \
                        [os.path.join(covScanPath, 'cov-commit-defects'), '-sf', licPath, '--dir', coverityBuildDir] + \
                        ['--url', 'http://{}:{}'.format(configs['coverity_host'], configs['coverity_port'])] + \
                        ['--stream', configs['coverity_stream'][configIdx], '--auth-key-file', os.getenv('COV_AUTH_KEY'), '--encryption', 'none'] + \
                        ['--preview-report-v2', previewReportPath] + extraParameters
        try:
            snapshotVersion = utils.extractScriptedParameter(configs['coverity_snapshot_version'][configIdx], 'params-snapshotVersion-{}'.format(configIdx))
            commitScript = commitScript + ['--version', snapshotVersion]
            utils.heavyLogging('coverityScan: coverity_snapshot_version {}({})'.format(snapshotVersion, configIdx))
        except:
            utils.heavyLogging('coverityScan: invalid coverity_snapshot_version config')
        try:
            snapshotDesc = utils.extractScriptedParameter(configs['coverity_snapshot_description'][configIdx], 'params-snapshotDesc-{}'.format(configIdx))
            commitScript = commitScript + ['--description', snapshotDesc]
            utils.heavyLogging('coverityScan: coverity_snapshot_description {}({})'.format(snapshotDesc, configIdx))
        except:
            utils.heavyLogging('coverityScan: invalid coverity_snapshot_description config')

        try:
            commitOutput = utils.popenReturnStdout(commitScript, cmdEnv)
            commitOutputLines = commitOutput['lines']
            for commitOutputLine in commitOutputLines:
                print(commitOutputLine, flush=True)
                try:
                    if commitOutputLine.decode('utf-8').startswith('New snapshot ID '):
                        tokens = commitOutputLine.split()
                        snapshotID = int(tokens[3])
                except:
                    pass
            utils.popenWithStdout(commitReportScript, cmdEnv)
        except:
            utils.heavyLogging('coverityScan: intermediate directory contains no translation units.')

    commitInfo = dict()
    commitInfo['snapshotID'] = snapshotID
    defectsCount = 0
    with open(previewReportPath, encoding='utf-8') as fpPreviewReport:
        jsonPreviewReport = json.load(fpPreviewReport)
        defectsCount = len(jsonPreviewReport['issueInfo'])
        for issue in jsonPreviewReport['issueInfo']:
            try:
                if issue['triage']['classification'] == 'Intentional' or issue['triage']['classification'] == 'False Positive':
                    defectsCount = defectsCount - 1
            except:
                pass
    commitInfo['defectsCount'] = defectsCount
    return commitInfo
