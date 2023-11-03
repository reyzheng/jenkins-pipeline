#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, shutil
import getopt, sys
import subprocess as sb
import json, logging
import utils, covanalyze

JENKINS_WS = ''
WORK_DIR = ''
HTML_REPORT = '.pf-htmlreport'
configs = dict()

def getDiffFiles(src, fileOperation):
    pwd = os.getcwd()
    repoPath = utils.getREPOPath(src, WORK_DIR)
    os.chdir(os.path.join(src, repoPath))
    # git log --format=\"%H\" -n 2
    commitIds = []
    cmdCommitIds = sb.Popen(['git', 'log', '--format=\"%H\"', '-n', '2'], stdout=sb.PIPE)
    while True:
        line = cmdCommitIds.stdout.readline()
        if not line:
            break
        commitIds.append(line.decode("utf-8") .strip()[1:-1])

    cmdDiffs = sb.Popen(['git', 'diff', '--submodule=diff', '{}..{}'.format(commitIds[1], commitIds[0])], stdout=sb.PIPE)
    if os.name == "posix":
        nameDiffs = sb.check_output(('grep', 'diff --git'), stdin=cmdDiffs.stdout)
    else:
        nameDiffs = sb.check_output(('findstr', '/l', 'diff --git'), stdin=cmdDiffs.stdout)
    cmdDiffs.wait()
    os.chdir(pwd)
    lines = nameDiffs.decode("utf-8").splitlines()
    rets = []
    for line in lines:
        tokens = line.split()
        if fileOperation == "BASE":
            # cov-configure skip_files
            rets.append('(?i){}'.format(os.path.basename(tokens[3][2:])))
        else:
            # cov-analyze -tu
            rets.append("file('{}')".format(tokens[3][2:]))

    return rets

def manageEmitDB(idir, covCmdPrefixes, covScanPath):
    filesToRemove = []
    filesToPreserve = []
    pwd = os.getcwd()
    logging.debug("manageEmitDB: working dir {}".format(pwd))
    # purge
    cmdPurge = sb.Popen(covCmdPrefixes + [os.path.join(covScanPath, 'cov-manage-emit'), '--dir', idir, '--tus-per-psf=non-latest', 'delete'], stdout=sb.PIPE)
    cmdPurge.wait()
    tuList = sb.Popen(covCmdPrefixes + [os.path.join(covScanPath, 'cov-manage-emit'), '--dir', idir, 'list'], stdout=sb.PIPE)
    while True:
        line = tuList.stdout.readline()
        if not line:
            break
        if line[:1].isdigit():
            tokens = line.split()
            dir = os.path.dirname(os.path.abspath(tokens[2]))
            filename = os.path.basename(tokens[2])
            try:
                os.chdir(dir)
                cmdLog = sb.Popen(['git', 'log' ,'--committer=realtek', '--committer=realsil', '--format=', '--name-only', '--no-merges', 'HEAD', '{}'.format(filename.decode("utf-8"))], stdout=sb.PIPE)
                if os.name == "posix":
                    uniqOutput = sb.check_output(('uniq'), stdin=cmdLog.stdout)
                else:
                    uniqOutput = sb.check_output(('sort', '/unique'), stdin=cmdLog.stdout)
                cmdLog.wait()
                uniqLines = uniqOutput.decode("utf-8").splitlines()
                if len(uniqLines) == 0 or uniqLines[0] == "":
                    # not realtek/realsil edited
                    filesToRemove.append(tokens[2])
                else:
                    filesToPreserve.append(tokens[2])
            except:
                # An exception occurred
                # file not existed, in emit-db only (caused by incremental build)
                print("exception at {}".format(tokens[2]))
                filesToRemove.append(tokens[2])
    os.chdir(pwd)
    file = open(os.path.join(WORK_DIR, '.pf-manage-emit'), 'w') #write to file
    for fileToRemove in filesToRemove:
        file.write("delete {}\n".format(fileToRemove.decode("utf-8")))
        cmdDelete = sb.Popen(covCmdPrefixes + [os.path.join(covScanPath, 'cov-manage-emit'), '--dir', idir, '-tp=file(\'{}\')'.format(fileToRemove.decode("utf-8")), 'delete'], stdout=sb.PIPE)
        cmdDelete.wait()
    for fileToPreserve in filesToPreserve:
        file.write("preserve {}\n".format(fileToPreserve.decode("utf-8")))
    file.close()

def checkEnv(covCmdPrefixes, covScanPath):
    envVars = dict()
    cmdEnv = dict(os.environ)
    ouput = utils.popenReturnStderr(covCmdPrefixes + [os.path.join(covScanPath, 'cov-generate-hostid')], cmdEnv)
    outputLines = ouput['lines']
    for outputLine in outputLines:
        print ('checkEnv: err, {}'.format(outputLine), flush=True)
        try:
            if 'COVERITY_UNSUPPORTED=1' in outputLine.decode('utf-8'):
                utils.heavyLogging('checkEnv: COVERITY_UNSUPPORTED')
                envVars['COVERITY_UNSUPPORTED'] = '1'
                break
        except:
            utils.heavyLogging('checkEnv: cov-generate-hostid exception')
            pass
    return envVars

def extractAnalyzeArgs(idx):
    extraAnalyzeArgs = ''
    try:
        extraAnalyzeArgs = configs['coverity_analyze_option'][idx]
        extraAnalyzeArgs = extraAnalyzeArgs.split('')
        extraAnalyzeArgs = ' '.join(extraAnalyzeArgs)
    except:
        logging.debug('extractAnalyzeArgs: invalid coverity_analyze_option config')

    logging.debug('extractAnalyzeArgs: coverity_analyze_option {}'.format(extraAnalyzeArgs))
    return extraAnalyzeArgs

def calTuPattern(buildIdx, configIdx):
    tuPattern = ''
    try:
        if configs['coverity_pattern_specified'][configIdx] == 'PF_DIFF_PREV':
            sourceDir = os.getenv('PF_SOURCE_DST_{}'.format(buildIdx))
            diffLines = getDiffFiles(sourceDir, 'PF_DIFF_PREV_FULL')
            tuPattern = '||'.join(diffLines)
            utils.heavyLogging('calTuPattern: PF_DIFF_PREV_FULL {}'.format(tuPattern))
        else:
            patterns = configs['coverity_pattern_specified'][configIdx].split(',')
            # --tu-pattern "file('path/to/dira/.*') || file('path/to/dirb/.*')"
            for i in range(len(patterns)):
                if patterns[i].endsWith('/') or patterns[i].endsWith('\\'):
                    # directory
                    patterns[i] = patterns[i] + ".*"
                patterns[i] = "file('" + patterns[i] + "')"
            tuPattern = '||'.join(patterns)
            utils.heavyLogging('calTuPattern: general {}'.format(tuPattern))
    except:
        utils.heavyLogging('calTuPattern: invalid {}th coverity_pattern_specified'.format(configIdx))
    return tuPattern

def emitComplementaryInfo(extraAnalyzeArgs, checkerFilePath):
    hasCodingStandard = False
    with open(checkerFilePath) as f:
        if '--coding-standard-config' in f.read():
            hasCodingStandard = True
    if '--coding-standard-config' in extraAnalyzeArgs or hasCodingStandard == True:
        return '--emit-complementary-info '
        logging.debug('emitComplementaryInfo: --emit-complementary-info')
    return ''

def fillCOVEnvInfo(refParent, scanInfo):
    if utils.hasEnv('BUILD_BRANCH'):
        buildBranch = utils.getEnv('BUILD_BRANCH')
        if refParent == True:
            utils.saveEnv(WORK_DIR, '{}_COV_COUNT_PARENT'.format(buildBranch), scanInfo['defectsCount'])
            utils.saveEnv(WORK_DIR, '{}_COV_STREAM_PARENT'.format(buildBranch), scanInfo['stream'])
            utils.saveEnv(WORK_DIR, '{}_COV_SNAPSHOT_PARENT'.format(buildBranch), scanInfo['snapshotID'])
        else:
            utils.saveEnv(WORK_DIR, '{}_COV_COUNT'.format(buildBranch), scanInfo['defectsCount'])
            utils.saveEnv(WORK_DIR, '{}_COV_STREAM'.format(buildBranch), scanInfo['stream'])
            utils.saveEnv(WORK_DIR, '{}_COV_SNAPSHOT'.format(buildBranch), scanInfo['snapshotID'])
    else:
        if refParent == True:
            utils.saveEnv(WORK_DIR, 'COV_COUNT_PARENT', scanInfo['defectsCount'])
            utils.saveEnv(WORK_DIR, 'COV_STREAM_PARENT', scanInfo['stream'])
            utils.saveEnv(WORK_DIR, 'COV_SNAPSHOT_PARENT', scanInfo['snapshotID'])
        else:
            utils.saveEnv(WORK_DIR, 'COV_COUNT', scanInfo['defectsCount'])
            utils.saveEnv(WORK_DIR, 'COV_STREAM', scanInfo['stream'])
            utils.saveEnv(WORK_DIR, 'COV_SNAPSHOT', scanInfo['snapshotID'])

def generateHtmlReport(scanInfo, workDir):
    global configs
    checkerFile = open(scanInfo['checkerfile'], 'r')
    checker = checkerFile.read()
    checkerFile.close()

    htmlTxt = '<dl>\n'
    if configs['refParent'] == True:
        htmlTxt += '<dt>Index</dt><dd>0</dd>\n'
    else:
        htmlTxt += '<dt>Index</dt><dd>1</dd>\n'
    htmlTxt += '<dt>Coverity Stream</dt><dd>{}</dd>\n'.format(scanInfo['stream'])
    htmlTxt += '<dt>Coverity Snapshot</dt><dd>{}</dd>\n'.format(scanInfo['snapshotID'])
    htmlTxt += '<dt>Defect Count</dt><dd>{}</dd>\n'.format(scanInfo['defectsCount'])
    htmlTxt += '<dt>Checker Enablement</dt><dd>{}</dd>\n'.format(checker)
    htmlTxt += '</dl>\n'

    if not os.path.isfile(os.path.join(workDir, HTML_REPORT)):
        fp = open(os.path.join(workDir, HTML_REPORT), 'a')
        # append build branch, stage info
        if 'BUILD_BRANCH' in os.environ:
            fp.write('<h3>Build branch: {}</h3>'.format(os.getenv('BUILD_BRANCH')))
        fp.write('<h4>Stage: {}</h4>'.format(configs['stageName']))
        fp.close()

    fp = open(os.path.join(workDir, HTML_REPORT), 'a')
    fp.write(htmlTxt)
    fp.close()

def codingStandards(idx):
    command = ""
    try:
        #command = "--security"
        standards = configs['coverity_coding_standards'][idx].split(',')
        for standard in standards:
            command = command + ' --coding-standard-config=.pf-all/rtk_coverity/coding-standards/{}.config'.format(standard)
    except:
        logging.debug('codingStandards: invalid coverity_coding_standards config')
        pass
    logging.debug('codingStandards: {}'.format(command))
    return command

def pickChecker(versionText, checkerFilePath):
    version = versionText.split('-')
    version = version[1].strip()
    logging.debug('pickChecker: "{}" "{}"'.format(versionText, version))
    with open(checkerFilePath) as f:
        jsonChecker = json.load(f)
    if version not in jsonChecker:
        version = 'default'
    fpChecker = open(os.path.join(WORK_DIR, "checker"), "w")
    fpChecker.write(jsonChecker[version]['options'])
    fpChecker.close()
    return os.path.join(WORK_DIR, "checker")

def coverityScan(buildIdx, configIdx):
    coverityScanInfo = dict()
    if configs['coverity_scan_enabled'] == False or configs['coverity_scan_enabled'] == "false":
        logging.debug('coverityScan: skip {}th build'.format(buildIdx))
        return
    logging.debug('coverityScan: {}th build with {}th config'.format(buildIdx, configIdx))

    if configs['coverity_checker_enablement'][configIdx] == 'custom' or configs['coverity_checker_enablement'][configIdx] == 'checkers_custom':
        checkFilePath = os.path.abspath('{}/scripts/checkers_custom'.format(os.getenv('PF_ROOT')))
    else:
        checkFilePath = os.path.abspath('{}/rtk_coverity/checkers_{}'.format(os.getenv('PF_ROOT'), configs['coverity_checker_enablement'][configIdx]))
    logging.debug('coverityScan: checkFilePath {}'.format(checkFilePath))

    coverityBuildDir = os.path.join(WORK_DIR, configs['coverity_build_dir'] + str(buildIdx))
    #if os.name != 'posix':
    #    coverityBuildDir = coverityBuildDir.replace('/', '\\')
    logging.debug('coverityScan: coverityBuildDir {}'.format(coverityBuildDir))

    covScanPath = ''
    covCmdPrefixes = []
    if configs['coverity_scan_toolbox'] != '':
        # bind WORKSPACE
        WORKSPACE = os.getcwd()
        bindPath = '-B {}:{} {}'.format(WORKSPACE, WORKSPACE, configs['coverity_scan_toolbox_args'])
        if configs['coverity_secondary_toolbox'] != '':
            bindPath = '--overlay {} {}'.format(configs['coverity_secondary_toolbox'], bindPath)
        singularityCmd = 'singularity exec {} {} '.format(bindPath, configs['coverity_scan_toolbox'])
        covCmdPrefixes = singularityCmd.split()
    if configs['coverity_scan_path'] != '':
        covScanPath = configs['coverity_scan_path']

    extraEnvs = checkEnv(covCmdPrefixes, covScanPath)
    cmdEnv = dict(os.environ)
    for key in extraEnvs:
        cmdEnv[key] = extraEnvs[key]

    if configs['coverity_clean_builddir'] == True:
        if os.path.exists(coverityBuildDir):
            shutil.rmtree(coverityBuildDir)

    if os.path.exists(os.path.join(WORK_DIR, '.pf-covconfig')):
        shutil.rmtree(os.path.join(WORK_DIR, '.pf-covconfig'))
    coverityXml = os.path.join(WORK_DIR, '.pf-covconfig', 'coverity.xml')
    os.makedirs(coverityBuildDir, exist_ok=True)

    isInterpretingLanguage = False
    interpretingLanguages = ['python']
    # cov-configure --platform
    try:
        if configs['coverity_comptype_platform'][configIdx] != '':
            buildPlatforms = configs['coverity_comptype_platform'][configIdx].split(',')
            for buildPlatform in buildPlatforms:
                # TODO: windows
                utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-configure'), '--config', coverityXml, '--{}'.format(buildPlatform), '--template'], cmdEnv)
                if buildPlatform in interpretingLanguages:
                    isInterpretingLanguage = True
    except:
        logging.debug('coverityScan: invalid coverity_comptype_platform config')
    # cov-configure --comptype prefix
    try:
        if configs['coverity_comptype_prefix'][configIdx] != '':
            compPrefixes = configs['coverity_comptype_prefix'][configIdx].split(',')
            for compPrefix in compPrefixes:
                utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-configure'), '--config', coverityXml, '--comptype', 'prefix', '--compiler', compPrefix, '--template'], cmdEnv)
    except:
        logging.debug('coverityScan: invalid coverity_comptype_prefix config')
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
                    utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-configure'), '--config', coverityXml, '--compiler', compiler, '--template'], cmdEnv)
                else:
                    utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-configure'), '--config', coverityXml, '--comptype', comptype, '--compiler', compiler, '--template'], cmdEnv)
    except:
        logging.debug('coverityScan: invalid coverity_comptype, coverity_comptype_gcc config')
    # cov-configure --comptype ld
    # skip

    # prepare cov-build, cov-analyze options
    extraBuildArgs = ''
    extraAnalyzeArgs = extractAnalyzeArgs(configIdx)
    tuPattern = ''

    pattern = calTuPattern(buildIdx, configIdx)
    if pattern != '':
        tuPattern = "({})".format(pattern)
    try:
        if configs['coverity_pattern_excluded'][configIdx] != '':
            patterns = configs['coverity_pattern_excluded'][configIdx].split(',')
            # --tu-pattern "!file('.*/mydir/.*')"
            for i in range(len(patterns)):
                if patterns[i].endswith('/') or patterns[i].endswith('\\'):
                    # directory
                    patterns[i] = patterns[i] + ".*"
                patterns[i] = "!file('" + patterns[i] + "')"
            if tuPattern == '':
                tuPattern = '&&'.join(patterns)
            else:
                tuPattern = tuPattern + '&&' + '&&'.join(patterns)
    except:
        utils.lightLogging('coverityScan: invalid coverity_pattern_excluded config')

    if tuPattern != '':
        extraAnalyzeArgs = extraAnalyzeArgs + ' -tp {}'.format(tuPattern)
    extraBuildArgs = emitComplementaryInfo(extraAnalyzeArgs, checkFilePath)

    covCmdPieces = covCmdPrefixes + [os.path.join(covScanPath, 'cov-analyze'), '--version']
    version = utils.popenFirstLine(covCmdPieces, cmdEnv)
    coverityScanInfo['version'] = version

    if configs['coverity_checker_enablement'][configIdx] == 'custom' or configs['coverity_checker_enablement'][configIdx] == 'checkers_custom':
        pass
    else:
        checkFilePath = pickChecker(version, checkFilePath)

    coverityScanInfo['stream'] = configs['coverity_stream'][configIdx]
    coverityScanInfo['snapshotID'] = 0
    coverityScanInfo['defectsCount'] = 0
    fillCOVEnvInfo(configs['refParent'], coverityScanInfo)
    # cov-build
    try:
        buildArgs = configs['coverity_build_option'][configIdx]
        buildArgs = buildArgs.split(',')
        extraBuildArgs += ''.join(buildArgs)
        utils.heavyLogging('coverityScan: add build args {}'.format(buildArgs))
    except:
        utils.heavyLogging('coverityScan: invalid coverity_build_option config')

    if configs['types'][buildIdx] == 'inline':
        if isInterpretingLanguage == True:
            buildCommand = '--dir {} --config {} {} --no-command --fs-capture-search {}'.format(coverityBuildDir, coverityXml, extraBuildArgs, configs['contents'][buildIdx])
        else:
            buildCommand = '--dir {} --config {} {} {}'.format(coverityBuildDir, coverityXml, extraBuildArgs, configs['contents'][buildIdx])
        utils.heavyLogging('coverityScan: COVBUILD {}'.format(buildCommand))
        covBuildRet = utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-build')] + buildCommand.split(), cmdEnv)
    else:
        scriptFile = '.pf-all/scripts/{}'.format(configs['contents'][buildIdx])
        if os.name == 'posix':
            shell = 'sh'
            statusCode = utils.popenReturnCode(['bash'], cmdEnv)
            if statusCode == 0:
                shell = 'bash'
            # ALLOW_NINJA_ENV should be placed in front of cov-build
            cmdEnv['ALLOW_NINJA_ENV'] = '1'
            cmd = '--dir {} --config {} {} {} {}'.format(coverityBuildDir, coverityXml, extraBuildArgs, shell, scriptFile)
        else:
            cmd = '--dir {} --config {} {} {}'.format(coverityBuildDir, coverityXml, extraBuildArgs, scriptFile)
        covBuildRet = utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-build')] + cmd.split(), cmdEnv)
    if covBuildRet != 0:
        utils.heavyLogging('coverityScan: cov-build error {}'.format(covBuildRet))
        sys.exit(covBuildRet)
    if configs['coverity_analyze_rtkonly'] == True:
        manageEmitDB(coverityBuildDir, covCmdPrefixes, covScanPath)

    # cov-analyze
    licPath = os.path.join(WORK_DIR, '.coverity.license.config')
    licenseServer = '#FLEXnet (do not delete this line)\nlicense-server 1123@papyrus.realtek.com\n'
    with open(licPath, 'w') as fpLic:
        fpLic.write(licenseServer)
    coverityCodingStandards = codingStandards(configIdx)
    coverityAnalyzeScript = "-sf {} --dir {} {} @@{} {}".format(licPath, coverityBuildDir, extraAnalyzeArgs, checkFilePath, coverityCodingStandards)
    coverityScanInfo['checkerfile'] = checkFilePath
    # write checkers to WORK_DIR/.checker
    analyzeOutput = utils.popenReturnStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-analyze')] + coverityAnalyzeScript.split(), cmdEnv)
    analyzeOutputLines = analyzeOutput['lines']
    for analyzeOutputLine in analyzeOutputLines:
        print (analyzeOutputLine, flush=True)
        try:
            if analyzeOutputLine.decode('utf-8').startswith("Defect occurrences found"):
                tokens = analyzeOutputLine.split()
                defectsCount = int(tokens[4])
        except:
            pass
    if analyzeOutput['code'] != 0:
        utils.heavyLogging('coverityScan: cov-analyze error {}'.format(analyzeOutput['code']))
        sys.exit(analyzeOutput['code'])
    utils.heavyLogging("coverityScan: defects occurrences: {}".format(defectsCount))

    # cov-commit
    # COVERITY_KEY_USER configured in jenkins credentials
    if os.name == 'posix':
        os.chmod(os.getenv('COV_AUTH_KEY'), 0o600)
    commitScript = covCmdPrefixes + \
                    [os.path.join(covScanPath, 'cov-commit-defects'), '-sf', licPath, '--dir', coverityBuildDir] + \
                    ['--url', 'http://{}:{}'.format(configs['coverity_host'], configs['coverity_port'])] + \
                    ['--stream', configs['coverity_stream'][configIdx], '--auth-key-file', os.getenv('COV_AUTH_KEY'), '--encryption', 'none']
    commitReportScript = covCmdPrefixes + \
                    [os.path.join(covScanPath, 'cov-commit-defects'), '-sf', licPath, '--dir', coverityBuildDir] + \
                    ['--url', 'http://{}:{}'.format(configs['coverity_host'], configs['coverity_port'])] + \
                    ['--stream', configs['coverity_stream'][configIdx], '--auth-key-file', os.getenv('COV_AUTH_KEY'), '--encryption', 'none'] + \
                    ['--preview-report-v2', 'preview_report_v2.json']
    try:
        commitScript = commitScript + ['--version', configs['coverity_snapshot_version'][configIdx]]
    except:
        logging.debug('coverityScan: invalid coverity_snapshot_version config')
    try:
        commitScript = commitScript + ['--description', configs['coverity_snapshot_description'][configIdx]]
    except:
        logging.debug('coverityScan: invalid coverity_snapshot_description config')

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
        logging.debug('coverityScan: intermediate directory contains no translation units.')

    if configs['coverity_local_report'] == True:
        utils.makeEmptyDirectory('coverityReport')
        htmlReportScript = "-sf {} --dir {}".format(licPath, coverityBuildDir) + \
                    " --html-output coverityReport"
        utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-format-errors')] + htmlReportScript.split(), cmdEnv)
    else:
        logging.debug('coverityScan: skip_local_report')

    #snapshotID = 29285
    print("Got snapshotID {}".format(snapshotID), flush=True)
    coverityScanInfo['snapshotID'] = snapshotID
    coverityScanInfo['defectsCount'] = defectsCount
    fillCOVEnvInfo(configs['refParent'], coverityScanInfo)
    generateHtmlReport(coverityScanInfo, WORK_DIR)
    # cov-format-errors defects occurrence is more precise than that on cov-connect
    if configs['coverity_local_report'] == True:
        if 'BUILD_BRANCH' in os.environ:
            reportFileName = os.path.join(WORK_DIR, 'coverityReport-{}-{}'.format(buildIdx, os.getenv('BUILD_BRANCH')))
        else:
            reportFileName = os.path.join(WORK_DIR, 'coverityReport-{}'.format(buildIdx))
        utils.makeEmptyDirectory(os.path.join(WORK_DIR, 'coverityReport'))
        shutil.make_archive(reportFileName, 'zip', 'coverityReport')

    # TODO: is 'coverity_command_prefix' necessary?
    #configs['coverity_command_prefix'] = coverityCommandPrefix
    configs['coverity_build_root'] = os.getcwd()
    # TODO: test gerritsubmit.py
    with open('.pf-coverity.json', "w") as outfile:
        json.dump(configs, outfile, indent=2)

    # call covanalyze to do coverity analysis
    if configs['coverity_analyze_defects'] == True or configs['coverity_analyze_defects'] == 'true':
        covanalyzeConfigs = configs.copy()
        covanalyzeConfigs['coverity_build_dir'] = coverityBuildDir
        if len(configs['coverity_project']) > configIdx:
            covanalyzeConfigs['coverity_project'] = configs['coverity_project'][configIdx]
        else:
            covanalyzeConfigs['coverity_project'] = ''
        covanalyzeConfigs['coverity_stream'] = configs['coverity_stream'][configIdx]
        covanalyzeConfigs['coverity_snapshot'] = snapshotID
        if configs['refParent'] == True:
            covanalyzeConfigsPath = 'covanalyze-{}-parent.json'.format(buildIdx)
        else:
            covanalyzeConfigsPath = 'covanalyze-{}-commit.json'.format(buildIdx)        
        with open(os.path.join(WORK_DIR, covanalyzeConfigsPath), 'w') as outfile:
            json.dump(covanalyzeConfigs, outfile, indent=2)
    #print("442 stm ", configs, flush=True)

def coverityAnalyze(buildIdx, refParent):
    if refParent == True:
        configFile = "covanalyze-{}-parent.json".format(buildIdx)
    else:
        configFile = "covanalyze-{}-commit.json".format(buildIdx)
    configFile = os.path.join(WORK_DIR, configFile)

    if 'PF_ROOT' in os.environ:
        utils.heavyLogging('coverityAnalyze: Start {}th coverity analyze'.format(buildIdx))
        if os.path.isfile('{}/scripts/coverity_report_config.yaml'.format(os.getenv('PF_ROOT'))):
            covReportFile = '{}/scripts/coverity_report_config.yaml'.format(os.getenv('PF_ROOT'))
        else:
            covReportFile = '{}/rtk_coverity/coverity_report_config.yaml'.format(os.getenv('PF_ROOT'))
        utils.heavyLogging('coverityAnalyze: covReportFile, {}'.format(covReportFile))
        args = ['{}/pipeline_scripts/covanalyze.py'.format(os.getenv('PF_ROOT')), '-f', configFile, \
                '-r', covReportFile, '-w', WORK_DIR, '-s']
        if os.path.isfile('{}/scripts/covBlameReplacement.txt'.format(os.getenv('PF_ROOT'))) == True:
            args.append('-b')
            args.append('{}/scripts/covBlameReplacement.txt'.format(os.getenv('PF_ROOT')))
        utils.heavyLogging('coverityAnalyze: args, {}'.format(args))
        covanalyze.main(args)

def coverityBuild(buildIdx):
    validOptions = ["prev", "branch", "custom"]
    # handle coverity_analyze_parent
    standardScanCleanDir = configs['coverity_clean_builddir']
    if configs['coverity_analyze_parent'] in validOptions:
        standardScanCleanDir = False
        if 'BUILD_BRANCH' in os.environ:
            varname = '{}_SOURCE_DIR{}'.format(os.getenv('BUILD_BRANCH'), buildIdx)
        else:
            varname = 'SOURCE_DIR{}'.format(buildIdx)
        if varname not in os.environ:
            logging.error('coverityBuild: env. var {} not defined'.format(varname))
            sys.exit(-1)
        sourceDst = os.getenv(varname)

        logging.debug('coverityBuild: checkout parent {} at {}'.format(configs['coverity_analyze_parent'], sourceDst))
        if configs['coverity_analyze_parent'] == 'custom':
            cmdCheckoutParent = sb.Popen(['sh', '.pf-all/pipeline_scripts/bdsh.sh', 'scripts/checkout-parent.sh'], stdout=sb.PIPE)
            cmdCheckoutParent.communicate()
        else:
            cmdCheckoutParent = sb.Popen(['sh', '.pf-all/pipeline_scripts/git-label-submodules.sh', sourceDst], stdout=sb.PIPE)
            for line in cmdCheckoutParent.stdout:
                logging.debug("coverityBuild: git-label-submodules.sh " + line.decode("utf-8").rstrip())
            cmdCheckoutParent.communicate()
            cmdCheckoutParent = sb.Popen(['sh', '.pf-all/pipeline_scripts/git-checkout-parent.sh', sourceDst, configs['coverity_analyze_parent']], stdout=sb.PIPE)
            for line in cmdCheckoutParent.stdout:
                logging.debug("coverityBuild: git-checkout-parent.sh " + line.decode("utf-8").rstrip())
            cmdCheckoutParent.communicate()

        configs['refParent'] = True
        if configs['buildmapping'] == "manytoone":
            coverityScan(buildIdx, 0)
        else:
            coverityScan(buildIdx, buildIdx)

        if configs["coverity_analyze_defects"] == True or configs["coverity_analyze_defects"] == "true":
            coverityAnalyze(buildIdx, configs['refParent'])

        if configs['coverity_analyze_parent'] == 'custom':
            cmdCheckoutParent = sb.Popen(['sh', '.pf-all/pipeline_scripts/bdsh.sh', 'scripts/checkout-current.sh'], stdout=sb.PIPE)
            cmdCheckoutParent.communicate()
            logging.debug('coverityBuild: userdefined scripts/checkout-current.sh')
        else:
            cmdCheckoutParent = sb.Popen(['sh', '.pf-all/pipeline_scripts/git-checkout-parent.sh', sourceDst, 'forward'], stdout=sb.PIPE)
            cmdCheckoutParent.communicate()
            logging.debug('coverityBuild: checkout {} forward'.format(sourceDst))
    # handle standard build
    configs['refParent'] = False
    configs['coverity_clean_builddir'] = standardScanCleanDir
    if configs['buildmapping'] == "manytoone":
        coverityScan(buildIdx, 0)
    else:
        coverityScan(buildIdx, buildIdx)
    if configs['coverity_analyze_defects'] == True or configs["coverity_analyze_defects"] == "true":
        coverityAnalyze(buildIdx, configs['refParent'])

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'f:w:e:c:s:i:d:v', ["config=", "work_dir=", "coverity=", "command=", "source=", "idir=", "build_idx=", "version"])
    except getopt.GetoptError:
        sys.exit()

    global configs
    global WORK_DIR
    # coverity installation path
    COVDIR = ""
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-c', '--command'):
            COMMAND = value
        elif name in ('-s', '--source'):
            SRC = value
        elif name in ('-i', '--idir'):
            IDIR = value
        elif name in ('-d', '--build_idx'):
            BUILD_IDX = int(value)
        elif name in ('-e', '--coverity'):
            COVDIR = value
        elif name in ('-w', '--work_dir'):
            WORK_DIR = value

    if os.path.isdir(WORK_DIR) == False:
        os.makedirs(WORK_DIR)
    WORK_DIR = os.path.abspath(WORK_DIR)
    logging.basicConfig(filename=os.path.join(WORK_DIR, 'coverity.log'), level=logging.DEBUG, filemode='w')
    print('log file: {}'.format(os.path.join(WORK_DIR, 'coverity.log')))
    configs = utils.loadConfigs(configFile)
    if COMMAND == "TRANSLATE_CONFIG":
        utils.translateConfig(configFile)
    elif COMMAND == "PF_DIFF_PREV_BASE":
        getDiffFiles(SRC, "BASE")
    #elif COMMAND == "PF_DIFF_PREV_FULL":
    #    getDiffFiles(SRC, "FULL")
    #elif COMMAND == "PF_RTK_ONLY":
    #    manageEmitDB(IDIR, COVDIR)
    #elif COMMAND == "CHECK_ENV":
    #    checkEnv(COVDIR)
    elif COMMAND == "ANALYZE":
        utils.initEnv(WORK_DIR)
        if os.path.isfile(os.path.join(WORK_DIR, HTML_REPORT)):
            os.remove(os.path.join(WORK_DIR, HTML_REPORT))
        coverityBuild(BUILD_IDX)
    elif COMMAND == "INIT_WORKDIR":
        utils.cleanEnvAndArchives(WORK_DIR)

if __name__ == '__main__':
    main(sys.argv)