#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, shutil, glob
import getopt, sys
import json, logging
import utils, covanalyze, covoperations
import git, repo

CONST_COVERITY_OK = 0
CONST_COVERITY_NO_TRANSLATION_UNIT = 1

JENKINS_WS = ''
HTML_REPORT = 'pf-htmlreport.html'

COVERITY_BASE_CHECKOUT_OPTIONS = ['prev', 'branch', 'custom', 'parent']

def getDiffFiles(srcType, src, fileOperation, workDir):
    pwd = os.getcwd()

    if srcType == 'repo':
        repoPath = repo.getREPOPath(src, workDir)
        os.chdir(os.path.join(src, repoPath))
        utils.heavyLogging('getDiffFiles: src {}({}), repoPath {}'.format(src, pwd, repoPath))
    else:
        utils.heavyLogging('getDiffFiles: src {}({})'.format(src, pwd))
        os.chdir(src)
    lines = git.diffRecursiveSubmodules(patchFilePrefix='')

    os.chdir(pwd)
    rets = []
    for line in lines:
        if fileOperation == 'NONE':
            rets.append('{}\n'.format(line.strip()))
        elif fileOperation == "BASE":
            # cov-configure skip_files
            rets.append('(?i){}'.format(os.path.basename(line)))
        else:
            # cov-analyze -tu
            rets.append("file('{}')".format(line))

    return rets


def checkEnv(covCmdPrefixes, covScanPath):
    cmdEnv = dict(os.environ)

    version = utils.popenFirstLine(covCmdPrefixes + [os.path.join(covScanPath, 'cov-analyze'), '--version'], cmdEnv)
    os.environ['COVERITY_VERSION_TXT'] = version

    ouput = utils.popenReturnStderr(covCmdPrefixes + [os.path.join(covScanPath, 'cov-generate-hostid')], cmdEnv)
    outputLines = ouput['lines']
    for outputLine in outputLines:
        print ('checkEnv: err, {}'.format(outputLine), flush=True)
        try:
            if 'COVERITY_UNSUPPORTED=1' in outputLine.decode('utf-8'):
                utils.heavyLogging('checkEnv: COVERITY_UNSUPPORTED')
                os.environ['COVERITY_UNSUPPORTED'] = '1'
                break
        except:
            utils.heavyLogging('checkEnv: cov-generate-hostid exception')
            pass
    return

def extractAnalyzeArgs(configs, idx):
    extraAnalyzeArgs = ''
    try:
        extraAnalyzeArgs = configs['coverity_analyze_option'][idx]
        extraAnalyzeArgs = extraAnalyzeArgs.split(',')
        extraAnalyzeArgs = ' '.join(extraAnalyzeArgs)
    except:
        logging.debug('extractAnalyzeArgs: invalid coverity_analyze_option config')

    logging.debug('extractAnalyzeArgs: coverity_analyze_option {}'.format(extraAnalyzeArgs))
    return extraAnalyzeArgs

def diffGerritPatchset(buildIdx, workDir):
    sourceType = utils.getEnv('PF_SOURCE_TYPE_{}'.format(buildIdx))
    sourceDir = utils.getEnv('PF_SOURCE_DST_{}'.format(buildIdx))
    existedDiffFile = os.path.join(os.getenv('WORKSPACE'), '.pf-source', '.pf-diff-files-{}'.format(buildIdx))
    if os.path.isfile(existedDiffFile):
        # already calculated in source.diffFiles()
        fpDiff = open(existedDiffFile)
        diffLines = fpDiff.readlines()
        fpDiff.close()
    else:
        utils.heavyLogging('diffGerritPatchset: getDiffFiles({})'.format(sourceType))
        if sourceType == 'git':
            diffLines = getDiffFiles(sourceType, sourceDir, 'NONE', workDir)
        elif sourceType == 'repo':
            if 'GERRIT_PROJECT' not in os.environ:
                utils.heavyLogging('diffGerritPatchset: invalid GERRIT_PROJECT')
                sys.exit(-1)
            diffLines = getDiffFiles(sourceType, sourceDir, 'NONE', workDir)
    utils.heavyLogging('diffGerritPatchset: diffLines {}'.format(diffLines))
    fpResult = open(os.path.join(workDir, 'gerrit-patchset.diff'), 'w')
    fpResult.writelines(diffLines)
    fpResult.close()

def calTuPattern(configs, buildIdx, configIdx, rtkOnlys):
    tuPattern = ''
    try:
        if configs['coverity_pattern_specified'][configIdx] == '':
            if len(rtkOnlys) > 0:
                # rtkOnlys, last priority
                tuPattern = rtkOnlys
            else:
                utils.heavyLogging('calTuPattern: empty coverity_pattern_specified')
        elif configs['coverity_pattern_specified'][configIdx] == 'PF_DIFF_GERRIT_PATCHSET' or \
                configs['coverity_pattern_specified'][configIdx] == 'PF_DIFF_GERRIT_PATCHSET_USER':
            if configs['coverity_pattern_specified'][configIdx] == 'PF_DIFF_GERRIT_PATCHSET':
                diffFile = os.path.join(configs['workDir'], 'gerrit-patchset.diff')
            else:
                diffFile = 'gerrit-patchset.diff'
            if os.path.isfile(diffFile):
                patterns = []
                fpDiff = open(diffFile, 'r')
                while True:
                    line = fpDiff.readline()
                    if not line:
                        break
                    if line != '':
                        patterns.append("file('{}')".format(line.strip()))
                fpDiff.close()
                tuPattern = '||'.join(patterns)
                utils.heavyLogging('calTuPattern: PF_DIFF_GERRIT_PATCHSET {}'.format(tuPattern))
            else:
                utils.heavyLogging('calTuPattern: gerrit-patchset.diff not found')
                sys.exit(-1)
        elif configs['coverity_pattern_specified'][configIdx] == 'PF_DIFF_PREV':
            if configs['coverity_analyze_parent'] == 'none':
                sourceType = utils.getEnv('PF_SOURCE_TYPE_{}'.format(buildIdx))
                sourceDir = utils.getEnv('PF_SOURCE_DST_{}'.format(buildIdx))
                diffLines = getDiffFiles(sourceType, sourceDir, 'PF_DIFF_PREV_FULL', configs['workDir'])
                tuPattern = '||'.join(diffLines)
                utils.heavyLogging('calTuPattern: PF_DIFF_PREV_FULL {}'.format(tuPattern))
            else:
                utils.heavyLogging('calTuPattern: PF_DIFF_PREV is invalid if "Coverity Analyze Base Repository" enabled')
        else:
            patterns = configs['coverity_pattern_specified'][configIdx].split(',')
            # --tu-pattern "file('path/to/dira/.*') || file('path/to/dirb/.*')"
            for i in range(len(patterns)):
                if patterns[i].endswith('/') or patterns[i].endswith('\\'):
                    # directory
                    patterns[i] = patterns[i] + ".*"
                patterns[i] = "file('" + patterns[i] + "')"
            tuPattern = '||'.join(patterns)
            utils.heavyLogging('calTuPattern: general {}'.format(tuPattern))
    except Exception as e:
        print(e)
        utils.heavyLogging('calTuPattern: invalid {}th coverity_pattern_specified'.format(configIdx))
    return tuPattern

def emitComplementaryInfo(extraAnalyzeArgs, checkerFilePath):
    hasCodingStandard = False
    with open(checkerFilePath) as f:
        if '--coding-standard-config' in f.read():
            hasCodingStandard = True
    if '--coding-standard-config' in extraAnalyzeArgs or hasCodingStandard == True:
        utils.heavyLogging('emitComplementaryInfo: --emit-complementary-info')
        return '--emit-complementary-info '
    return ''

def fillCOVEnvInfo(basePhase, scanInfo, workDir):
    if basePhase == True:
        utils.saveEnv(workDir, 'COV_COUNT_PARENT', scanInfo['defectsCount'])
        utils.saveEnv(workDir, 'COV_STREAM_PARENT', scanInfo['stream'])
        utils.saveEnv(workDir, 'COV_SNAPSHOT_PARENT', scanInfo['snapshotID'])
    else:
        utils.saveEnv(workDir, 'COV_COUNT', scanInfo['defectsCount'])
        utils.saveEnv(workDir, 'COV_STREAM', scanInfo['stream'])
        utils.saveEnv(workDir, 'COV_SNAPSHOT', scanInfo['snapshotID'])

def generateHtmlReport(configs, scanInfo, workDir):
    checkerFile = open(scanInfo['checkerfile'], 'r')
    checker = checkerFile.read()
    checkerFile.close()
    previewReportPath = 'preview_report_v2.json'

    htmlTxt = '<dl>\n'
    if configs['basePhase'] == True:
        htmlTxt += '<dt>Index</dt><dd>0</dd>\n'
        previewReportPath = 'preview_report_v2_parent.json'
    else:
        htmlTxt += '<dt>Index</dt><dd>1</dd>\n'
    htmlTxt += '<dt>Coverity Stream</dt><dd>{}</dd>\n'.format(scanInfo['stream'])
    htmlTxt += '<dt>Coverity Snapshot</dt><dd>{}</dd>\n'.format(scanInfo['snapshotID'])
    htmlTxt += '<dt>Defect Occurrences</dt><dd>{}</dd>\n'.format(scanInfo['defectsCount'])
    if os.path.isfile(previewReportPath):
        htmlTxt += '<dt>Defect Info.</dt><dd><table>\n'
        htmlTxt += '<tr style="background-color: #00bfff">\n'
        htmlTxt += '<td>CID</td>\n'
        htmlTxt += '<td>Checker</td>\n'
        htmlTxt += '<td>File</td>\n'
        htmlTxt += '<td>Line Number</td>\n'
        htmlTxt += '</tr>\n'
        with open(previewReportPath, encoding='utf-8') as fpPreviewReport:
            jsonPreviewReport = json.load(fpPreviewReport)
            for issue in jsonPreviewReport['issueInfo']:
                htmlTxt += '<tr style="background-color: #00ddff">\n'
                htmlTxt += '<td>{}</td>\n'.format(issue['cid'])
                htmlTxt += '<td>{}</td>\n'.format(issue['occurrences'][0]['checker'])
                htmlTxt += '<td>{}</td>\n'.format(issue['occurrences'][0]['file'])
                htmlTxt += '<td>{}</td>\n'.format(issue['occurrences'][0]['mainEventLineNumber'])
                htmlTxt += '</tr>\n'
        htmlTxt += '</dd></table>\n'

    htmlTxt += '<dt>Checker Enablement</dt><dd>{}</dd>\n'.format(checker)
    htmlTxt += '</dl>\n'

    if configs['basePhase'] == False and os.path.isfile(os.path.join(workDir, 'gerrit-patchset.diff')):
        htmlTxt += '<dl>\n'
        htmlTxt += '<dt>Diff</dt>\n'

        fpDiff = open(os.path.join(workDir, 'gerrit-patchset.diff'), 'r')
        while True:
            line = fpDiff.readline()
            if not line:
                break
            htmlTxt += '<dd>{}</dd>\n'.format(line)
        fpDiff.close()

        htmlTxt += '</dl>\n'

    if not os.path.isfile(os.path.join(workDir, HTML_REPORT)):
        utils.heavyLogging('generateHtmlReport: {}'.format(os.path.join(workDir, HTML_REPORT)))
        fp = open(os.path.join(workDir, HTML_REPORT), 'a')
        # append build branch, stage info
        if 'BUILD_BRANCH' in os.environ:
            fp.write('<h3>Build branch: {}</h3>'.format(os.getenv('BUILD_BRANCH')))
        fp.write('<h4>Stage: {}</h4>'.format(configs['stageName']))
        fp.close()

    fp = open(os.path.join(workDir, HTML_REPORT), 'a')
    fp.write(htmlTxt)
    fp.close()

def codingStandards(configs, idx):
    command = ""
    try:
        # got "ECHO 已關閉。" on windows, windows really ....
        if configs['coverity_coding_standards'][idx] != '' and configs['coverity_coding_standards'][idx].startswith('ECHO') == False:
            standards = configs['coverity_coding_standards'][idx].split(',')
            for standard in standards:
                userStandardPath = '{}/scripts/{}'.format(os.getenv('PF_ROOT'), standard)
                if os.path.isfile(userStandardPath):
                    command = command + ' --coding-standard-config={}'.format(userStandardPath)
                else:
                    command = command + ' --coding-standard-config={}/rtk_coverity/coding-standards/{}.config'.format(os.getenv('PF_ROOT'), standard)
    except:
        utils.heavyLogging('codingStandards: invalid coverity_coding_standards config')
        pass
    utils.heavyLogging('codingStandards: {}'.format(command))
    return command

def pickChecker(configs, configIdx):
    if configs['coverity_checker_enablement'][configIdx] == 'custom' or configs['coverity_checker_enablement'][configIdx] == 'checkers_custom':
        utils.heavyLogging('pickChecker: custom checker')
        checkFilePath = os.path.abspath('{}/scripts/checkers_custom'.format(os.getenv('PF_ROOT')))
    elif configs['coverity_checker_enablement'][configIdx].startswith('$'):
        parameter = configs['coverity_checker_enablement'][configIdx][1:]
        if parameter in os.environ:
            checkerText = os.getenv(parameter)
            if checkerText in ['default', 'default-light', 'medium', 'medium-light', 'heavy', 'custom']:
                utils.heavyLogging('pickChecker: pick existed checker from option {}'.format(checkerText))
                if checkerText == 'custom':
                    checkFilePath = os.path.abspath('{}/scripts/checkers_custom'.format(os.getenv('PF_ROOT')))
                else:
                    checkFilePath = os.path.abspath('{}/rtk_coverity/checkers_{}'.format(os.getenv('PF_ROOT'), checkerText))
            else:
                utils.heavyLogging('pickChecker: checker from parameter')
                checkerTextLines = checkerText.split()
                # write back to .pf-all/scripts/checkers_custom
                checkFilePath = os.path.abspath('{}/scripts/checkers_custom'.format(os.getenv('PF_ROOT')))
                fpChecker = open(checkFilePath, 'w')
                for checkerTextLine in checkerTextLines:
                    fpChecker.write('{}\n'.format(checkerTextLine))
                fpChecker.close()
        else:
            utils.heavyLogging('pickChecker: invalid checker file configuration')
            sys.exit(-1)
    else:
        utils.heavyLogging('pickChecker: pick existed checker')
        checkFilePath = os.path.abspath('{}/rtk_coverity/checkers_{}'.format(os.getenv('PF_ROOT'), configs['coverity_checker_enablement'][configIdx]))
    utils.heavyLogging('pickChecker: checkFilePath {}'.format(checkFilePath))

    resultPath = os.path.join(configs['workDir'], 'checker-{}'.format(configIdx))
    if checkFilePath.endswith('checkers_custom') == True:
        fpResult = open(resultPath, 'w')
        fpCustom = open(checkFilePath, 'r')
        while True:
            line = fpCustom.readline()
            if not line:
                break
            if line.strip() != '':
                fpResult.write(line.strip() + '\n')
        fpCustom.close()
        fpResult.close()
    else:
        version = os.getenv('COVERITY_VERSION_TXT').split('-')
        version = version[1].strip()
        utils.heavyLogging('pickChecker: "{}" "{}"'.format(os.getenv('COVERITY_VERSION_TXT'), version))
        with open(checkFilePath) as f:
            jsonChecker = json.load(f)
        if version not in jsonChecker:
            version = 'default'
        fpResult = open(resultPath, 'w')
        fpResult.write(jsonChecker[version]['options'])
        fpResult.write('\n')
        fpResult.close()

    try:
        fpResult = open(resultPath, 'a')
        if configs['coverity_checker_extra'][configIdx].strip() != '':
            extras = configs['coverity_checker_extra'][configIdx].split(',')
            for extra in extras:
                fpExtra = open(os.path.join(os.getenv('PF_ROOT'), 'rtk_coverity', 'checkers_{}'.format(extra)))
                while True:
                    line = fpExtra.readline()
                    if not line:
                        break
                    fpResult.write(line)
                fpExtra.close()
        fpResult.close()
    except:
        utils.heavyLogging('pickChecker: coverity_checker_extra undefined')

    return os.path.abspath(resultPath)

def prepareCovtekConfig(covCmdPrefixes, covScanPath, idir, workDir):
    configs = dict()
    configs['workDir'] = os.path.join(workDir, 'covtek')
    os.makedirs(configs['workDir'], exist_ok=True)
    if covCmdPrefixes == 0:
        configs['coverity_prefix'] = covScanPath
    else:
        configs['coverity_prefix'] = '{} {}'.format(' '.join(covCmdPrefixes), covScanPath)
    configs['cov-build_idir'] = idir
    return configs

def checkCodeXMCheckers():
    codeXMArgs = ''
    for codeXMChecker in glob.glob(os.path.join(os.getenv('WORKSPACE'), os.getenv('PF_ROOT'), 'scripts', '*.cxm')):
        codeXMArgs = codeXMArgs + ' --codexm {}'.format(codeXMChecker)
    return codeXMArgs

def outputLocalReport(basePhase, licensePath, covCmdPrefixes, covScanPath, coverityBuildDir, workDir):
    reportDir = 'coverityReport'
    jsonReport = 'coverity_report.json'
    if basePhase == True:
        reportDir = 'coverityReport-base'
        jsonReport = 'coverity_report_base.json'
    utils.makeEmptyDirectory(os.path.join(workDir, reportDir))
    htmlReportScript = '-sf {} --dir {} --html-output {}'.format(licensePath, coverityBuildDir, os.path.join(workDir, reportDir))
    jsonReportScript = '-sf {} --dir {} --json-output-v10 {}'.format(licensePath, coverityBuildDir, jsonReport)
    utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-format-errors')] + htmlReportScript.split(), dict(os.environ))
    utils.popenWithStdout(covCmdPrefixes + [os.path.join(covScanPath, 'cov-format-errors')] + jsonReportScript.split(), dict(os.environ))

def coverityScan(configs, buildIdx, configIdx):
    coverityScanInfo = dict()
    if configs['coverity_scan_enabled'] == False or configs['coverity_scan_enabled'] == "false":
        utils.heavyLogging('coverityScan: skip {}th build'.format(buildIdx))
        return
    utils.heavyLogging('coverityScan: {}th build with {}th config'.format(buildIdx, configIdx))


    if os.path.isabs(configs['coverity_build_dir']):
        coverityBuildDir = configs['coverity_build_dir']
    else:
        coverityBuildDir = os.path.join(configs['workDir'], configs['coverity_build_dir'] + str(buildIdx))
    #if os.name != 'posix':
    #    coverityBuildDir = coverityBuildDir.replace('/', '\\')
    utils.heavyLogging('coverityScan: coverityBuildDir {}'.format(coverityBuildDir))

    covScanPath = ''
    covCmdPrefixes = []
    singularityCmd = ''
    if configs['coverity_scan_toolbox'] != '':
        # bind WORKSPACE
        WORKSPACE = os.getcwd()
        bindPath = '-B {}:{} {}'.format(WORKSPACE, WORKSPACE, configs['coverity_scan_toolbox_args'])
        if configs['coverity_secondary_toolbox'] != '':
            bindPath = '--overlay {}:ro {}'.format(configs['coverity_secondary_toolbox'], bindPath)
        singularityCmd = 'singularity exec {} {} '.format(bindPath, configs['coverity_scan_toolbox'])
        covCmdPrefixes = singularityCmd.split()
    if configs['coverity_scan_path'] != '':
        covScanPath = configs['coverity_scan_path']

    checkEnv(covCmdPrefixes, covScanPath)
    cmdEnv = dict(os.environ)
    if configs['coverity_codetek_training'] != 'none':
        covtekConfigs  = prepareCovtekConfig(covCmdPrefixes, covScanPath, coverityBuildDir, configs['workDir'])
        utils.heavyLogging('coverityScan: codetek training enabled {}, source path {}'.format(covtekConfigs, os.path.abspath(configs['sourceDst'])))
        if os.name == "posix":
            covtekExecutable = os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'covtek', 'dist_linux', 'covtek')
        else:
            covtekExecutable = os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'covtek', 'dist_windows', 'covtek')
        cmdPieces = [covtekExecutable, 'inspect', '-d', os.path.abspath(configs['sourceDst']), '-w', covtekConfigs['workDir']]
        utils.popenWithStdout(cmdPieces, cmdEnv)
        fpSha256Sum = open(os.path.join(covtekConfigs['workDir'], 'sha256sum'), "r")
        sha256sum = fpSha256Sum.read()
        fpSha256Sum.close()

    if configs['coverity_codetek_training'] == 'accumulate':
        # force preserve build dir for coverity_codetek_training(accumulate)
        utils.heavyLogging('coverityScan: preserve build dir {}'.format(coverityBuildDir))
    else:
        if configs['coverity_clean_builddir'] == True:
            utils.heavyLogging('coverityScan: clean build dir {}'.format(coverityBuildDir))
            if os.path.exists(coverityBuildDir):
                shutil.rmtree(coverityBuildDir)
        else:
            utils.heavyLogging('coverityScan: keep build dir {}'.format(coverityBuildDir))

    utils.heavyLogging('coverityScan: search template dir {}'.format(os.path.join(configs['workDir'], '.pf-covconfig', 'template*')))
    for templateDir in glob.glob(os.path.join(configs['workDir'], '.pf-covconfig', 'template*')):
        utils.heavyLogging('coverityScan: remove template dir {}'.format(templateDir))
        shutil.rmtree(templateDir)
    coverityXml = os.path.join(configs['workDir'], '.pf-covconfig', 'coverity.xml')
    if os.path.isfile(coverityXml):
        os.remove(coverityXml)
    os.makedirs(coverityBuildDir, exist_ok=True)

    retCovConfigure = covoperations.covConfigure(configs, configIdx, covCmdPrefixes, covScanPath, coverityXml, cmdEnv)

    # prepare cov-build, cov-analyze options
    extraBuildArgs = ''
    # extractAnalyzeArgs: "coverity_analyze_option"
    extraAnalyzeArgs = extractAnalyzeArgs(configs, configIdx)
    checkFilePath = pickChecker(configs, configIdx)
    extraAnalyzeArgs = extraAnalyzeArgs + codingStandards(configs, configIdx)
    extraBuildArgs = emitComplementaryInfo(extraAnalyzeArgs, checkFilePath)

    coverityScanInfo['version'] = os.getenv('COVERITY_VERSION_TXT')
    coverityScanInfo['stream'] = configs['coverity_stream'][configIdx]
    coverityScanInfo['snapshotID'] = 0
    coverityScanInfo['defectsCount'] = 0
    fillCOVEnvInfo(configs['basePhase'], coverityScanInfo, configs['workDir'])
    # cov-build
    try:
        buildArgs = configs['coverity_build_option'][configIdx]
        buildArgs = buildArgs.split(',')
        extraBuildArgs += ' '.join(buildArgs)
        utils.heavyLogging('coverityScan: add build args {}'.format(buildArgs))
    except:
        utils.heavyLogging('coverityScan: invalid coverity_build_option config')
    if configs['basePhase'] == True:
        cmdEnv['PF_GERRIT_PATCH_APPLIED'] = '0'
    else:
        if configs['coverity_analyze_parent'] in COVERITY_BASE_CHECKOUT_OPTIONS:
            extraBuildArgs += ' --delete-stale-tus'
        cmdEnv['PF_GERRIT_PATCH_APPLIED'] = '1'
    currentDir = os.getcwd()
    if 'USR_COV_BUILD_DIR' in os.environ:
        os.chdir(os.getenv('USR_COV_BUILD_DIR'))
    utils.heavyLogging('coverityScan: USR_COV_BUILD_DIR {}'.format(os.getcwd()))
    covoperations.covBuild(configs, covCmdPrefixes, covScanPath, coverityXml, coverityBuildDir, extraBuildArgs, \
                            buildIdx, retCovConfigure['ignorePCH'], retCovConfigure['isInterpretingLanguage'], cmdEnv)
    os.chdir(currentDir)
    rtkOnlys = []
    if configs['coverity_analyze_rtkonly'] == True:
        rtkOnlys = covoperations.manageEmitDB(coverityBuildDir, covCmdPrefixes, covScanPath, configs['sourceDst'])
    try:
        if configs['coverity_analysis_operation'] == 'BUILD_ONLY':
            utils.heavyLogging('coverityScan: BUILD_ONLY')
            return
    except:
        utils.lightLogging('coverityScan: invalid coverity_analysis_operation')

    tuPattern = ''
    # calTuPattern: "coverity_pattern_specified", 
    pattern = calTuPattern(configs, buildIdx, configIdx, rtkOnlys)
    if type(pattern) is list:
        # coverity_analyze_rtkonly == True
        expandedAnalyzeArgs = pattern
        utils.lightLogging('coverityScan: expandedAnalyzeArgs {}'.format(expandedAnalyzeArgs))
        # merge coverity_pattern_excluded
        try:
            if configs['coverity_pattern_excluded'][configIdx] != '':
                patterns = configs['coverity_pattern_excluded'][configIdx].split(',')
                # --tu-pattern "!file('.*/mydir/.*')"
                for i in range(len(patterns)):
                    if patterns[i].endswith('/') or patterns[i].endswith('\\'):
                        # directory
                        patterns[i] = patterns[i] + ".*"
                    patterns[i] = "!file('" + patterns[i] + "')"
                tuPattern = '&&'.join(patterns)
                for i in range(len(expandedAnalyzeArgs)):
                    if expandedAnalyzeArgs[i].startswith('file'):
                        expandedAnalyzeArgs[i] = '{}&&{}'.format(expandedAnalyzeArgs[i], tuPattern)
                utils.lightLogging('coverityScan: expandedAnalyzeArgs(merged) {}'.format(expandedAnalyzeArgs))
        except:
            utils.lightLogging('coverityScan: invalid coverity_pattern_excluded config')
    else:
        expandedAnalyzeArgs = []
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
            utils.lightLogging('coverityScan: extraAnalyzeArgs {}'.format(extraAnalyzeArgs))
    extraAnalyzeArgs = '{}{}'.format(extraAnalyzeArgs, checkCodeXMCheckers())

    try:
        if configs['coverity_commit_additional'][configIdx] != '':
            covoperations.addEmitDB(coverityBuildDir, configs['coverity_commit_additional'][configIdx], covCmdPrefixes, covScanPath, cmdEnv)
    except:
        utils.lightLogging('coverityScan: invalid coverity_commit_additional config')

    # cov-analyze
    licPath = os.path.join(configs['workDir'], '.coverity.license.config')
    covoperations.generateLicenseFile(licPath)
    utils.heavyLogging('coverityScan: start cov-analyze')
    coverityAnalyzeScript = "-sf {} -s {} --dir {} {} @@{}".format(licPath, os.getenv('WORKSPACE'), coverityBuildDir, extraAnalyzeArgs, checkFilePath)
    coverityScanInfo['checkerfile'] = checkFilePath
    # write checkers to WORK_DIR/.checker
    noTranslationUnitsError = False
    if os.name == 'posix':
        analyzeOutput = utils.popenReturnStdoutStderr(covCmdPrefixes + [os.path.join(covScanPath, 'cov-analyze')] + coverityAnalyzeScript.split() + expandedAnalyzeArgs, cmdEnv)
    else:
        # cov-analyze hangs on windows
        logStdout = os.path.join(configs['workDir'], 'cov-analyze.stdout')
        logStderr = os.path.join(configs['workDir'], 'cov-analyze.stderr')
        analyzeReturnCode = utils.popenToFile(covCmdPrefixes + [os.path.join(covScanPath, 'cov-analyze')] + coverityAnalyzeScript.split() + expandedAnalyzeArgs, cmdEnv, logStdout, logStderr)
        analyzeOutput = dict()
        analyzeOutput['code'] = analyzeReturnCode
        with open(logStderr) as outfile:
            analyzeOutput['lines'] = outfile.readlines()
        with open(logStdout) as outfile:
            analyzeOutput['lines'].extend(outfile.readlines())
    analyzeOutputLines = analyzeOutput['lines']
    for analyzeOutputLine in analyzeOutputLines:
        try:
            analyzeOutputLine = analyzeOutputLine.decode('utf-8')
        except:
            pass
        print(analyzeOutputLine, flush=True)
        try:
            if analyzeOutputLine.startswith('Defect occurrences found') or \
                    analyzeOutputLine.startswith('Defects/Coding rule violations found'):
                tokens = analyzeOutputLine.split(':')
                tokens = tokens[1].split()
                defectsCount = int(tokens[0])
            elif 'intermediate directory contains no translation units' in analyzeOutputLine or \
                    'No matching translation units' in analyzeOutputLine:
                defectsCount = 0
                noTranslationUnitsError = True
                utils.heavyLogging('coverityScan: intermediate directory contains no translation units')
        except Exception as ex:
            print(ex)
    if analyzeOutput['code'] != 0:
        if noTranslationUnitsError == True and configs['allow_empty_analysis'] == True:
            utils.heavyLogging('coverityScan: cov-analyze error noTranslationUnits (allow_empty_analysis)')
            utils.saveEnv(configs['workDir'], 'COVERITY_EMPTY_ANALYSIS', 'TRUE')
        else:
            utils.heavyLogging('coverityScan: cov-analyze error {}'.format(analyzeOutput['code']))
            sys.exit(analyzeOutput['code'])
    utils.heavyLogging("coverityScan: defects occurrences: {}".format(defectsCount))

    if configs['coverity_codetek_training'] != 'none':
        if configs['basePhase'] == True:
            covtekConfigs['diffReport'] = False
        else:
            covtekConfigs['diffReport'] = True
        with open(os.path.join(configs['workDir'], 'covtekCoverityConfig.json'), 'w') as outfile:
            json.dump(covtekConfigs, outfile, indent=2)
        cmdPieces = [covtekExecutable, 'coverity', '-r', sha256sum, '-cf', os.path.join(configs['workDir'], 'covtekCoverityConfig.json')]
        if configs['coverity_codetek_inference_only'] == True:
            cmdPieces = cmdPieces + ['-io', 'true']
        utils.popenWithStdout(cmdPieces, cmdEnv)
        if os.path.isfile(os.path.join(configs['workDir'], '.artifacts')):
            fpArtifacts = open(os.path.join(configs['workDir'], '.artifacts'), 'a')
        else:
            fpArtifacts = open(os.path.join(configs['workDir'], '.artifacts'), 'w')
        fpArtifacts.write(os.path.join('covtek', 'training', '*.zip') + ',')
        fpArtifacts.close()
    # cov-commit
    # COVERITY_KEY_USER configured in jenkins credentials
    if noTranslationUnitsError == True:
        return CONST_COVERITY_NO_TRANSLATION_UNIT
    else:
        configs['covCmdPrefixes'] = covCmdPrefixes
        if configs['coverity_local_report'] == True:
            outputLocalReport(configs['basePhase'], licPath, covCmdPrefixes, covScanPath, coverityBuildDir, configs['workDir'])
        else:
            utils.heavyLogging('coverityScan: skip_local_report')
    if configs['coverity_local_analysis'] == True:
        utils.heavyLogging('coverityScan: local analysis only')
        return
    else:
        commitInfo = covoperations.covCommit(configs, configIdx, covCmdPrefixes, covScanPath, coverityBuildDir)

        #snapshotID = 29285
        utils.heavyLogging("coverityScan: got snapshotID {}".format(commitInfo['snapshotID']))
        coverityScanInfo['snapshotID'] = commitInfo['snapshotID']
        coverityScanInfo['defectsCount'] = commitInfo['defectsCount']
        fillCOVEnvInfo(configs['basePhase'], coverityScanInfo, configs['workDir'])
        generateHtmlReport(configs, coverityScanInfo, configs['workDir'])

        configs['coverity_command_prefix'] = singularityCmd + covScanPath
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
            covanalyzeConfigs['coverity_snapshot'] = commitInfo['snapshotID']
            if configs['basePhase'] == True:
                covanalyzeConfigsPath = 'covanalyze-{}-parent.json'.format(buildIdx)
            else:
                covanalyzeConfigsPath = 'covanalyze-{}-commit.json'.format(buildIdx)
            with open(os.path.join(configs['workDir'], covanalyzeConfigsPath), 'w') as outfile:
                json.dump(covanalyzeConfigs, outfile, indent=2)


        return 0

def advancedAnalysis(buildIdx, basePhase, workDir):
    if basePhase == True:
        configFile = "covanalyze-{}-parent.json".format(buildIdx)
    else:
        configFile = "covanalyze-{}-commit.json".format(buildIdx)
    configFile = os.path.join(workDir, configFile)

    if 'PF_ROOT' in os.environ:
        utils.heavyLogging('coverityAnalyze: Start {}th coverity analyze'.format(buildIdx))
        if os.path.isfile('{}/scripts/coverity_report_config.yaml'.format(os.getenv('PF_ROOT'))):
            covReportFile = '{}/scripts/coverity_report_config.yaml'.format(os.getenv('PF_ROOT'))
        else:
            covReportFile = '{}/rtk_coverity/coverity_report_config.yaml'.format(os.getenv('PF_ROOT'))
        utils.heavyLogging('coverityAnalyze: covReportFile, {}'.format(covReportFile))
        args = ['{}/pipeline_scripts/covanalyze.py'.format(os.getenv('PF_ROOT')), '-f', configFile, \
                '-r', covReportFile, '-w', workDir, '-s']
        if os.path.isfile('{}/scripts/covBlameReplacement.txt'.format(os.getenv('PF_ROOT'))) == True:
            args.append('-b')
            args.append('{}/scripts/covBlameReplacement.txt'.format(os.getenv('PF_ROOT')))
        utils.heavyLogging('coverityAnalyze: args, {}'.format(args))
        covanalyze.main(args)
        #fpArtifacts = open(os.path.join(workDir, '.artifacts'), 'a')
        #if "BUILD_BRANCH" in os.environ:
        #    fpArtifacts.write('WORKSPACE:preview-report-committer-{}.json,'.format(os.getenv('BUILD_BRANCH')))
        #else:
        #    fpArtifacts.write('WORKSPACE:preview-report-committer.json,')
        #fpArtifacts.close()

def coverityIterateBuild(configs, buildIdx):
    sourceDst = utils.getEnv('PF_SOURCE_DST_{}'.format(buildIdx))
    utils.heavyLogging('coverityIterateBuild: PF_SOURCE_DST {}'.format(sourceDst))
    revisions = git.listRevisions(sourceDst, configs['training_revision_start'], configs['training_revision_end'])
    firstIteration = True
    for revision in revisions:
        utils.heavyLogging('coverityIterateBuild: checkoutRevision {}({})'.format(revision, sourceDst))
        git.checkoutRevision(sourceDst, revision)
        try:
            # for incremental build on coverityIterateBuild
            if firstIteration == True:
                configs['coverity_clean_builddir'] = True
            else:
                configs['coverity_clean_builddir'] = False
            coverityBuild(configs, buildIdx)
            firstIteration = False
        except:
            utils.heavyLogging('coverityIterateBuild: coverityBuild {} failure'.format(revision))

def coverityBuild(configs, buildIdx):
    configs['sourceDst'] = utils.getEnv('PF_SOURCE_DST_{}'.format(buildIdx))
    configs['sourceType'] = utils.getEnv('PF_SOURCE_TYPE_{}'.format(buildIdx))
    if configs['buildmapping'] == "manytoone":
        configIdx = 0
    else:
        configIdx = buildIdx
    cmdEnv = dict(os.environ)
    PF_ROOT = ''
    if 'PF_ROOT' in os.environ:
        PF_ROOT = os.getenv('PF_ROOT')
    try:
        if 'PF_DIFF_GERRIT_PATCHSET' in configs['coverity_pattern_specified'][configIdx] or \
                'PF_DIFF_GERRIT_PATCHSET' in configs['coverity_configure_option'][configIdx]:
            diffGerritPatchset(buildIdx, configs['workDir'])
    except Exception as e: 
        utils.heavyLogging('coverityBuild: invalid coverity_pattern_specified/coverity_configure_option')
        utils.heavyLogging(e)
    # handle coverity_analyze_parent
    standardScanCleanDir = configs['coverity_clean_builddir']
    if configs['coverity_analyze_parent'] in COVERITY_BASE_CHECKOUT_OPTIONS:
        standardScanCleanDir = False
        if configs['coverity_analyze_parent'] == 'custom':
            if os.name == "posix":
                checkoutCmd = ['sh', os.path.join(PF_ROOT, 'pipeline_scripts/bdsh.sh'), os.path.join(PF_ROOT, 'scripts/checkout-parent.sh')]
            else:
                checkoutCmd = [os.path.join(PF_ROOT, 'scripts', 'checkout-parent.bat')]
            retCheckoutParent = utils.popenWithStdout(checkoutCmd, cmdEnv)
            if retCheckoutParent != 0:
                utils.heavyLogging('coverityBuild: checkout base revision fail {}'.format(retCheckoutParent))
                sys.exit(retCheckoutParent)
            utils.heavyLogging('coverityBuild: userdefined scripts/checkout-parent.sh')
        else:
            utils.heavyLogging('coverityBuild: checkout parent {} at {}({})'.format(configs['coverity_analyze_parent'], configs['sourceDst'], configs['sourceType']))
            if configs['sourceType'] == 'git':
                #git.labelSubmodules(sourceDst)
                git.checkoutParent(configs['sourceDst'], configs['workDir'], configs['coverity_analyze_parent'])
            elif configs['sourceType'] == 'repo':
                repo.checkoutParent(configs['sourceDst'], configs['workDir'], configs['coverity_analyze_parent'])
            else:
                utils.heavyLogging('coverityBuild: invalid source type {}'.format(configs['sourceType']))
        if configs['sourceType'] == 'git':
            utils.heavyLogging('coverityBuild: revision info. (base)')
            git.recursiveRevision(configs['sourceDst'])
        configs['basePhase'] = True
        ret = coverityScan(configs, buildIdx, configIdx)
        if ret == CONST_COVERITY_OK:
            if configs['coverity_analyze_defects'] == True or configs['coverity_analyze_defects'] == 'true':
                advancedAnalysis(buildIdx, configs['basePhase'], configs['workDir'])

        utils.heavyLogging('coverityBuild: checkout current')
        if configs['coverity_analyze_parent'] == 'custom':
            if os.name == "posix":
                checkoutCmd = ['sh', os.path.join(PF_ROOT, 'pipeline_scripts/bdsh.sh'), os.path.join(PF_ROOT, 'scripts/checkout-current.sh')]
            else:
                checkoutCmd = [os.path.join(PF_ROOT, 'scripts', 'checkout-current.bat')]
            retCheckoutCurrent = utils.popenWithStdout(checkoutCmd, cmdEnv)
            if retCheckoutCurrent != 0:
                utils.heavyLogging('coverityBuild: checkout build revision fail {}'.format(retCheckoutCurrent))
                sys.exit(retCheckoutCurrent)
            utils.heavyLogging('coverityBuild: userdefined scripts/checkout-current.sh')
        else:
            mode = 'forward'
            if configs['coverity_analyze_parent'] == 'parent':
                mode = 'cherry-pick'
            if configs['sourceType'] == 'git':
                git.checkoutParent(configs['sourceDst'], configs['workDir'], mode)
            elif configs['sourceType'] == 'repo':
                repo.checkoutParent(configs['sourceDst'], configs['workDir'], mode)
            utils.heavyLogging('coverityBuild: checkout {} forward'.format(configs['sourceDst']))
        if configs['sourceType'] == 'git':
            utils.heavyLogging('coverityBuild: revision info. (patch)')
            git.recursiveRevision(configs['sourceDst'])
    # handle standard build
    configs['basePhase'] = False
    configs['coverity_clean_builddir'] = standardScanCleanDir
    ret = coverityScan(configs, buildIdx, configIdx)
    if ret == CONST_COVERITY_OK:
        if configs['coverity_analyze_defects'] == True or configs["coverity_analyze_defects"] == "true":
            advancedAnalysis(buildIdx, configs['basePhase'], configs['workDir'])
    # cov-format-errors defects occurrence is more precise than that on cov-connect
    if configs['coverity_local_report'] == True:
        if 'BUILD_BRANCH' in os.environ:
            reportFileName = os.path.join(configs['workDir'], 'coverityReport-{}-{}'.format(buildIdx, os.getenv('BUILD_BRANCH')))
        else:
            reportFileName = os.path.join(configs['workDir'], 'coverityReport-{}'.format(buildIdx))
        archiveDir = 'coverityReport'
        if configs['basePhase'] == True:
            reportFileName = '{}-base'.format(reportFileName)
            archiveDir = '{}-base'.format(archiveDir)
        if os.path.isdir(os.path.join(configs['workDir'], archiveDir)):
            shutil.make_archive(reportFileName, 'zip', os.path.join(configs['workDir'], archiveDir))
            if os.path.isfile(os.path.join(configs['workDir'], '.artifacts')):
                fpArtifacts = open(os.path.join(configs['workDir'], '.artifacts'), 'a')
            else:
                fpArtifacts = open(os.path.join(configs['workDir'], '.artifacts'), 'w')
            fpArtifacts.write(os.path.basename('{}.zip,'.format(reportFileName)))
            fpArtifacts.close()
        else:
            utils.heavyLogging('coverityBuild: local report invalid - possible empty analysis result')
            pass

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'f:w:e:c:s:i:d:v', ["config=", "work_dir=", "coverity=", "command=", "source=", "idir=", "build_idx=", "version"])
    except getopt.GetoptError:
        sys.exit()

    # coverity installation path
    COVDIR = ""
    workDir = ''
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
            workDir = value

    if os.path.isdir(workDir) == False:
        os.makedirs(workDir)
    workDir = os.path.abspath(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'coverity.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    print('log file: {}'.format(os.path.join(workDir, 'coverity.log')))
    configs = utils.loadConfigs(configFile)
    configs['workDir'] = workDir
    if COMMAND == "TRANSLATE_CONFIG":
        utils.translateConfig(configFile)
    elif COMMAND == "PF_DIFF_PREV_BASE":
        # TODO: repo only
        getDiffFiles('repo', SRC, "BASE", configs['workDir'])
    elif COMMAND == "ANALYZE":
        if configs['coverity_codetek_training'] != 'none':
            if os.name == "posix":
                covtekExecutable = os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'covtek', 'dist_linux', 'covtek')
            else:
                covtekExecutable = os.path.join(os.getenv('PF_ROOT'), 'pipeline_scripts', 'covtek', 'dist_windows', 'covtek')
            if configs['coverity_codetek_training'] == 'iterate':
                cmdPieces = [covtekExecutable, 'init-training', '-w', os.path.join(configs['workDir'], 'covtek')]
            else:
                cmdPieces = [covtekExecutable, 'reset-training', '-w', os.path.join(configs['workDir'], 'covtek')]
            utils.popenWithStdout(cmdPieces, dict(os.environ))
        if configs['coverity_codetek_training'] == 'iterate':
            coverityIterateBuild(configs, BUILD_IDX)
        else:
            coverityBuild(configs, BUILD_IDX)
    elif COMMAND == "INIT_WORKDIR":
        utils.cleanEnvAndArchives(workDir)

if __name__ == '__main__':
    main(sys.argv)