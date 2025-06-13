import getopt, sys, os
import subprocess as sb
import logging, glob, shutil
import utils

def bdScan(configs):
    pwd = os.getcwd()
    gitEnv = dict(os.environ)
    cmdEnv = dict(os.environ)
    artifactsToArchive = []

    if configs['blackduck_enabled'] == False:
        print('Skip blackduck scan')
        return

    userEnvPath = os.path.join(os.getenv('PF_ROOT'), 'scripts', '{}.env'.format(configs['stageName']))
    if os.path.isfile(userEnvPath):
        with open(userEnvPath) as fpEnv:
            while True:
                line = fpEnv.readline()
                if not line or line.strip() == '':
                    break
                if line.strip().startswith('#'):
                    continue
                arg = line[:line.index('=')].strip()
                value = line[line.index('=') + 1:].strip()
                cmdEnv[arg] = value
                utils.lightLogging('bdScan: add env {}, value {}'.format(arg, value))
    gitEnv['GIT_TRACE_PACKET'] = '1'
    gitEnv['GIT_TRACE'] = '1'
    gitEnv['GIT_CURL_VERBOSE'] = '1'
    scanEnvPrefix = []
    if 'scan_env' in configs and configs['scan_env'] == 'android':
        utils.makeEmptyDirectory(os.path.join(configs['WORK_DIR'], 'android'))
        gitEnv['GIT_SSL_NO_VERIFY'] = 'true'
        cmds = ['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/jenkins-pipeline/singularity/blackduck', \
                            '--depth', '1', '-b', 'android', os.path.join(configs['WORK_DIR'], 'android')]
        utils.popenWithStdout(cmds, gitEnv)
        scanEnvPrefix = ['singularity', 'exec', os.path.join(configs['WORK_DIR'], 'android', 'android.sif')]
    utils.heavyLogging('bdScan: scanEnvPrefix {}'.format(scanEnvPrefix))

    utils.makeEmptyDirectory(os.path.join(configs['WORK_DIR'], 'blackduck_scan'))
    if 'bdaas' in configs and configs['bdaas'] == True:
        gitEnv['GIT_SSL_NO_VERIFY'] = 'true'
        cmds = ['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/hub-rest-api-python/builds', \
                            '--depth', '1', os.path.join(configs['WORK_DIR'], 'blackduck_scan')]
        ret = utils.popenReturnCode(cmds, gitEnv)
        if ret != 0:
            utils.heavyLogging('bdScan: download bd_cli failed')
            sys.exit(-1)
    else:
        # check java existence
        try:
            cmdJava = sb.Popen(['java', '-version'], stdout=sb.PIPE)
            cmdJava.communicate()
            if cmdJava.returncode != 0:
                utils.heavyLogging('bdScan: cannot find java')
                sys.exit(1)
        except:
            utils.heavyLogging('bdScan: cannot find java')
            sys.exit(1)
        if configs['blackduck_detect_path'] != '':
            jarPath = configs['blackduck_detect_path']
        else:
            branch = "9.10.1-air-gap"
            jarPath = "synopsys-detect-9.10.1.jar"
            if configs['blackduck_airgap_mode'] == False:
                branch = "9.10.1"
                jarPath = "9.10.1/synopsys-detect-9.10.1.jar"
            gitEnv['GIT_SSL_NO_VERIFY'] = 'true'
            cmdGit = sb.Popen(['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/blackduck/synopsys_detect', \
                                '--depth', '1', '-b', branch, '--single-branch', os.path.join(configs['WORK_DIR'], 'blackduck_scan')], stdout=sb.PIPE, env=gitEnv)
            cmdGit.wait()
            utils.heavyLogging('bdScan: branch {}'.format(branch))
            jarPath = os.path.join(configs['WORK_DIR'], 'blackduck_scan', jarPath)
        utils.heavyLogging('bdScan: jarPath {}'.format(jarPath))

    BLACKDUCK_URL = configs['blackduck_url']
    if BLACKDUCK_URL == '':
        BLACKDUCK_URL = 'https://blackduck.rtkbf.com/'
    BLACKDUCK_PROJECT = configs['blackduck_project_name']
    BLACKDUCK_VERSION = configs['blackduck_project_version']
    if configs['blackduck_project_path'].strip() == "":
        # TODO: re-checkout source to WORK_DIR
        configs['blackduck_project_path'] = '.'

    scanPaths = configs['blackduck_project_path'].split(',')
    utils.heavyLogging('bdScan: WORKSPACE {}'.format(pwd))
    utils.heavyLogging('bdScan: scanPaths {}'.format(scanPaths))

    detectParams = []
    # TODO: waiting SD Nexus to remove detect.accuracy.required=NONE
    if 'scan_env' in configs and configs['scan_env'] == 'android':
        if 'bdaas' in configs and configs['bdaas'] == True:
            #detectParams = ['--blackduck-detect-options', '{"detect.accuracy.required":"NONE"}']
            detectParams = ['--blackduck-detect-options', '{"detect.accuracy.required":"NONE", "detect.diagnostic":"true"}']
        else:
            detectParams = ['detect.accuracy.required=NONE']
    snippetParams = []
    if configs['blackduck_snippet_scan'] == True:
        if 'bdaas' in configs and configs['bdaas'] == True:
            snippetParams = ['--do-snippet-matching=on', '--do-bdaas=off']
        else:
            snippetParams = ['--detect.blackduck.signature.scanner.snippet.matching=SNIPPET_MATCHING']

    for scanPath in scanPaths:
        if scanPath == '.':
            scanPath = pwd
        else:
            scanPath = os.path.join(pwd, scanPath)
        utils.heavyLogging('bdScan: scanPath {}'.format(scanPath))

        subDirs = ['']
        subExcludes = ['']
        pfRoot = ''
        if 'PF_ROOT' in os.environ:
            pfRoot = os.getenv('PF_ROOT')
        utils.heavyLogging('bdScan: pfRoot {}'.format(pfRoot))
        if 'blackduck_project_excludes' in configs and configs['blackduck_project_excludes'] != "":
            subExcludes = [configs['blackduck_project_excludes']]
            utils.heavyLogging('bdScan: user defiend excludes {}'.format(subExcludes))
        if 'bdaas' in configs and configs['bdaas'] == True:
            # bdaas: check scan_list.out
            pathList = 'scan_list.out'
        else:
            # classic: check detect_list.out
            pathList = 'detect_list.out'
        utils.heavyLogging('bdScan: check {}'.format(os.path.join(pwd, pfRoot, 'scripts', pathList)))
        if os.path.isfile(os.path.join(pwd, pfRoot, 'scripts', pathList)):
            subDirs = []
            subExcludes = []
            fpOut = open(os.path.join(pwd, pfRoot, 'scripts', pathList), 'r')
            while True:
                line = fpOut.readline()
                if not line:
                    break
                if line.startswith('#'):
                    continue
                tokens = line.split(',')
                subDirs.append(tokens[0].strip())
                if len(tokens) > 1:
                    subExcludes.append(line[line.index(',') + 1:].strip())
                else:
                    subExcludes.append('')
            fpOut.close()
            if len(subDirs) == 0:
                utils.heavyLogging('bdScan: empty {}'.format(pathList))
                subDirs = ['']
                subExcludes = ['']
            else:
                utils.heavyLogging('bdScan: user defined pathList {}'.format(pathList))
                utils.heavyLogging(subDirs)
                utils.heavyLogging(subExcludes)
        else:
            utils.heavyLogging('bdScan: {} not defined'.format(pathList))

        if 'bdaas' in configs and configs['bdaas'] == True:
            with open('bd_cli.yml', 'w') as fpYaml:
                fpYaml.write('bd_url: {}\n'.format(BLACKDUCK_URL))
                fpYaml.write('bd_token: {}\n'.format(os.getenv('BD_TOKEN')))
                fpYaml.write('dashboard_url: https://devops.realtek.com\n')
                fpYaml.write('insecure: true\n')
                fpYaml.write('timeout: 600\n')
                fpYaml.write('debug: true\n')

            excludesREPOProjectParam = []
            if configs['blackduck_repoproject_excludes'] != '':
                excludes = configs['blackduck_repoproject_excludes'].split(',')
                for exclude in excludes:
                    excludesREPOProjectParam.append('--repo-excluded-project={}'.format(exclude))
            idx = 0
            for subDir in subDirs:
                subScanPath = os.path.join(scanPath, subDir)
                excludes = subExcludes[idx]
                utils.heavyLogging('bdScan: start scan path {}'.format(subScanPath))
                utils.heavyLogging('bdScan: start exclude path')
                utils.heavyLogging(excludes)
                excludesPieces = excludes.split(',')
                excludesParam = []
                for excludesPiece in excludesPieces:
                    if excludesPiece == '.repo' or excludesPiece == 'blackduck_scan' or excludesPiece == '':
                        continue
                    excludesParam.append('--excluded-dir')
                    excludesParam.append(excludesPiece)
                dir = os.listdir(subScanPath)
                if len(dir) == 0:
                    logging.debug("bd_cli, skip empty directory")
                    continue
                if os.name == "posix":
                    bdCliExec = 'bd_cli'
                else:
                    bdCliExec = 'bd_cli.exe'
                # --blackduck-detect-bundle [JAR|AIR_GAP|AIR_GAP_NO_DOCKER]
                #             The Synopsys Detect bundle to be used.  [default: AIR_GAP_NO_DOCKER]
                logStdout = os.path.join(configs['WORK_DIR'], 'bd_cli.stdout')
                logStderr = os.path.join(configs['WORK_DIR'], 'bd_cli.stderr')
                # https://community.synopsys.com/s/article/Detect-scanning-failed-Malformed-input-or-input-contains-unmappable-characters
                cmdEnv['LC_CTYPE'] = 'en_US.UTF-8'
                cmdEnv['LC_ALL'] = 'en_US.UTF-8'
                if os.name == 'posix':
                    utils.popenWithStdout(scanEnvPrefix + ['printenv'], cmdEnv)
                returncode = utils.popenToFile(scanEnvPrefix + [os.path.join(configs['WORK_DIR'], 'blackduck_scan', bdCliExec), \
                                                '--debug=on', '--location', 'RT', '--network', 'SD', \
                                                '-j1', '--config', 'bd_cli.yml', \
                                                'scan', BLACKDUCK_PROJECT, BLACKDUCK_VERSION] + snippetParams + \
                                                ['--source-path={}'.format(subScanPath)] + excludesParam + detectParams + excludesREPOProjectParam, \
                                                cmdEnv, logStdout, logStderr)
                with open(logStderr) as outfile:
                    returnlines = outfile.readlines()
                with open(logStdout) as outfile:
                    returnlines.extend(outfile.readlines())
                hasDetectLog = False
                for line in returnlines:
                    try:
                        line = bytes.decode(line, 'utf-8').strip()
                    except:
                        pass
                    utils.heavyLogging('{}'.format(line))
                    if line.startswith('[INFO] The log directory for this run'):
                        logTokens = line.split(': ')
                        logTokens[1] = logTokens[1].strip()
                        copySrc = os.path.join(logTokens[1], 'execution', 'blackduck_detect-0.log')
                        if 'BUILD_BRANCH' in os.environ:
                            copyDstBase = 'blackduck_detect-{}-{}.log'.format(configs['stageName'], os.getenv('BUILD_BRANCH'))
                            copyDst = os.path.join(configs['WORK_DIR'], copyDstBase)
                        else:
                            copyDstBase = 'blackduck_detect-{}.log'.format(configs['stageName'])
                            copyDst = os.path.join(configs['WORK_DIR'], copyDstBase)
                        utils.heavyLogging('bdScan: add artifactsToArchive {}'.format(copySrc))
                        artifactsToArchive.append(copyDstBase)
                        hasDetectLog = True
                if hasDetectLog == True:
                    shutil.copyfile(copySrc, copyDst)
                if returncode != 0:
                    utils.heavyLogging('bdScan: failed scanning {}({},{})'.format(subScanPath, BLACKDUCK_PROJECT, BLACKDUCK_VERSION))
                    sys.exit(1)
                idx = idx + 1
            os.remove('bd_cli.yml')
        else:
            # .git is excluded by synopsys_detect already
            generalExcludes = ['blackduck_scan', '.repo']
            if configs['blackduck_project_excludes'] != '':
                generalExcludes.extend(configs['blackduck_project_excludes'].split(','))
            utils.heavyLogging('generalExcludes: {}'.format(generalExcludes))
            if configs['blackduck_offline_mode'] == True:
                # download signature scanner from mirror.rtkbf.com
                signatureScannerVersion = "2022.2.1"
                utils.makeEmptyDirectory('scan.cli')
                gitEnv['GIT_SSL_NO_VERIFY'] = 'true'
                cmdGit = sb.Popen(['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/blackduck/scan.cli', \
                                    '--depth', '1', '-b', signatureScannerVersion, os.path.join(configs['WORK_DIR'], 'scan.cli')], stdout=sb.PIPE, env=gitEnv)
                cmdGit.wait()
                import zipfile
                if os.name == "posix":
                    zipTarget = os.path.join(configs['WORK_DIR'], 'scan.cli', 'scan.cli-{}.zip'.format(signatureScannerVersion))
                else:
                    zipTarget = os.path.join(configs['WORK_DIR'], 'scan.cli', 'scan.cli-windows-{}.zip'.format(signatureScannerVersion))
                with zipfile.ZipFile(zipTarget, 'r') as zip_ref:
                    zip_ref.extractall(configs['WORK_DIR'])
                signatureScannerPath = os.path.join(configs['WORK_DIR'], 'scan.cli-{}'.format(signatureScannerVersion))
                if os.name == "posix":
                    cmdChmod = sb.Popen(['chmod', '755', os.path.join(configs['WORK_DIR'], 'scan.cli-{}'.format(signatureScannerVersion), 'jre', 'bin', 'java')], stdout=sb.PIPE, env=cmdEnv)
                    cmdChmod.wait()
            offlineParams = []

            if configs['blackduck_offline_mode'] == True:
                offlineParams = ['--detect.scan.output.path={}'.format(os.path.join(configs['WORK_DIR'], 'offline_output')), '--detect.blackduck.signature.scanner.local.path={}'.format(signatureScannerPath)]

            cmdEnv['SYNOPSYS_SKIP_PHONE_HOME'] = 'true'
            utils.lightLogging('bdScan: synopsys detect env, {}'.format(cmdEnv))
            for subDir in subDirs:
                if subDir == '':
                    subScanPath = scanPath
                else:
                    subScanPath = os.path.join(scanPath, subDir)
                airgappedParams = []
                #if configs['blackduck_airgap_mode'] == True:
                #    airgappedParams = ['--detect.gradle.inspector.air.gap.path={}'.format(os.path.join('blackduck_scan', 'packaged-inspectors', 'gradle'))]
                utils.heavyLogging('bdScan: snippetParams {}'.format(snippetParams))
                utils.heavyLogging('bdScan: offlineParams {}'.format(offlineParams))
                utils.heavyLogging('bdScan: airgappedParams {}'.format(airgappedParams))
                utils.heavyLogging('bdScan: detectParams {}'.format(detectParams))
                cmdBDScan = sb.Popen(scanEnvPrefix + ['java', '-jar', jarPath, \
                                    '--blackduck.api.token={}'.format(os.getenv('BD_TOKEN')), \
                                    '--blackduck.trust.cert=true', \
                                    '--blackduck.url={}'.format(BLACKDUCK_URL), \
                                    '--detect.excluded.directories={}'.format(','.join(generalExcludes)), \
                                    '--detect.accuracy.required=NONE', \
                                    '--detect.project.name={}'.format(BLACKDUCK_PROJECT), \
                                    '--detect.project.version.name={}'.format(BLACKDUCK_VERSION), \
                                    '--detect.source.path={}'.format(subScanPath), \
                                    '--blackduck.offline.mode={}'.format(configs['blackduck_offline_mode']), \
                                    '--detect.blackduck.scan.mode=INTELLIGENT', \
                                    '--detect.cleanup=false', \
                                    '--detect.timeout=800'
                                    #'--detect.tools=SIGNATURE_SCAN'
                                    ] + detectParams + snippetParams + offlineParams + airgappedParams, stdout=sb.PIPE, env=cmdEnv)
                for line in cmdBDScan.stdout:
                    try:
                        line = line.decode("utf-8").rstrip()
                    except:
                        pass
                    utils.heavyLogging("bdScan: synopsys_detect " + line)
                    if line.startswith('Logging to file:'):
                        logTokens = line.split(': ')
                        logTokens[1] = logTokens[1].strip()
                        copySrc = logTokens[1]
                        if 'BUILD_BRANCH' in os.environ:
                            copyDstBase = 'synopsys_detect-{}-{}.log'.format(configs['stageName'], os.getenv('BUILD_BRANCH'))
                            copyDst = os.path.join(configs['WORK_DIR'], copyDstBase)
                        else:
                            copyDstBase = 'synopsys_detect-{}.log'.format(configs['stageName'])
                            copyDst = os.path.join(configs['WORK_DIR'], copyDstBase)
                        utils.heavyLogging('bdScan: add artifactsToArchive {}'.format(copySrc))
                        artifactsToArchive.append(copyDstBase)
                        shutil.copyfile(copySrc, copyDst)
                cmdBDScan.communicate()
                if cmdBDScan.returncode != 0:
                    utils.heavyLogging('bdScan: synopsys_detect failed')
                    sys.exit(cmdBDScan.returncode)

    for file in glob.glob(os.path.join(configs['WORK_DIR'], 'offline_output', '**', '*.bdio'), recursive=True):
        artifactsToArchive.append(os.path.relpath(file, configs['WORK_DIR']))
    fpArtifacts = open(os.path.join(configs['WORK_DIR'], '.artifacts'), 'w')
    fpArtifacts.write(','.join(artifactsToArchive))
    fpArtifacts.close()

    os.chdir(pwd)

def main(argv):
    # check if jenkins credentials defined (as env. variable)
    if "BD_TOKEN" in os.environ:
        print("BLACKDUCK: got environmental variable, BD_TOKEN")
    else:
        sys.exit("Environmental variable BD_TOKEN not defined")

    configFile = ''
    skipTranslate = False
    workDir = ''

    try:
        opts, args = getopt.getopt(argv[1:], 'w:f:u:p:vs', ["work_dir=", "config=", "user=", "password=", "version", "skip_translate"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-s', '--skip_translate'):
            skipTranslate = True
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value
            logging.basicConfig(filename=os.path.join(workDir, 'blackduck.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')

    if skipTranslate == False:
        utils.translateConfig(configFile)
    # step 1
    #     Load configurations
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir
    if configs['blackduck_enabled'] == False:
        logging.debug('Skip blackduck scan')
        sys.exit(0)
    utils.cleanEnvAndArchives(configs['WORK_DIR'])
    bdScan(configs)

if __name__ == "__main__":
    main(sys.argv)
