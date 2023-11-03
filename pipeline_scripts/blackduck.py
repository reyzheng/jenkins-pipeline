import json
import getopt, sys
import os, shutil, glob
import subprocess as sb
import zipfile
import logging
import utils

configs = dict()

def bdScan():
    global configs
    pwd = os.getcwd()
    scanEnv = 'native'

    if configs['blackduck_enabled'] == False:
        print('Skip blackduck scan')
        return

    cmdEnv = dict(os.environ)
    if 'scan_env' in configs and configs['scan_env'] == 'android':
        scanEnv = 'android'
        utils.makeEmptyDirectory(os.path.join(configs['WORK_DIR'], 'android'))
        cmds = ['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/jenkins-pipeline/singularity/blackduck', \
                            '--depth', '1', '-b', 'android', os.path.join(configs['WORK_DIR'], 'android')]
        utils.popenWithStdout(cmds, cmdEnv)

    utils.makeEmptyDirectory(os.path.join(configs['WORK_DIR'], 'blackduck_scan'))
    if 'bdaas' in configs and configs['bdaas'] == True:
        cmdEnv['GIT_SSL_NO_VERIFY'] = 'true'
        cmdGit = sb.Popen(['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/hub-rest-api-python/builds', \
                            '--depth', '1', os.path.join(configs['WORK_DIR'], 'blackduck_scan')], stdout=sb.PIPE, env=cmdEnv)
        cmdGit.wait()
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
        branch = "9.0.0-air-gap"
        jarPath = "synopsys-detect-9.0.0.jar"
        if configs['blackduck_airgap_mode'] == False:
            branch = "9.0.0"
            jarPath = "9.0.0/synopsys-detect-9.0.0.jar"
        cmdEnv = dict(os.environ)
        cmdEnv['GIT_SSL_NO_VERIFY'] = 'true'
        cmdGit = sb.Popen(['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/blackduck/synopsys_detect', \
                            '--depth', '1', '-b', branch, '--single-branch', os.path.join(configs['WORK_DIR'], 'blackduck_scan')], stdout=sb.PIPE, env=cmdEnv)
        cmdGit.wait()
        utils.heavyLogging('bdScan: branch {}'.format(branch))
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
    for scanPath in scanPaths:
        if scanPath == '.':
            scanPath = pwd
        else:
            scanPath = os.path.join(pwd, scanPath)
        utils.heavyLogging('bdScan: scanPath {}'.format(scanPath))

        # .git is excluded by synopsys_detect already
        generalExcludes = "blackduck_scan,.repo"

        subDirs = ['']
        subExcludes = ['']
        pfRoot = ''
        if 'PF_ROOT' in os.environ:
            pfRoot = os.getenv('PF_ROOT')
        utils.heavyLogging('bdScan: pfRoot {}'.format(pfRoot))
        if 'blackduck_project_excludes' in configs and configs['blackduck_project_excludes'] != "":
            subExcludes = configs['blackduck_project_excludes']
            utils.heavyLogging('User defiend excludes {}'.format(subExcludes))
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
            utils.heavyLogging('User defined pathList {}'.format(pathList))
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
            if configs['blackduck_snippet_scan'] == True:
                snippetParam = '--do-snippet-matching=on'
            else:
                snippetParam = '--do-snippet-matching=off'

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
                scanEnvPrefix = []
                if scanEnv == 'android':
                    scanEnvPrefix = ['singularity', 'exec', os.path.join(configs['WORK_DIR'], 'android', 'android.sif')]
                utils.heavyLogging('bdScan: scanEnvPrefix {}'.format(scanEnvPrefix))
                if os.name == "posix":
                    bdCliExec = 'bd_cli'
                else:
                    bdCliExec = 'bd_cli.exe'
                #cmdBDScan = sb.Popen(cmdEnv + [os.path.join(configs['WORK_DIR'], 'blackduck_scan', bdCliExec), \
                #                    '--debug=on', '--location', 'RT', '--network', 'SD', \
                #                    '-j1', '--config', 'bd_cli.yml', \
                #                    'scan', BLACKDUCK_PROJECT, BLACKDUCK_VERSION, snippetParam, \
                #                    '--source-path={}'.format(subScanPath)] + excludesParam, stdout=sb.PIPE, env=cmdEnv)
                #cmdBDScan.communicate()
                returncode = utils.popenReturnCode(scanEnvPrefix + [os.path.join(configs['WORK_DIR'], 'blackduck_scan', bdCliExec), \
                                                '--debug=on', '--location', 'RT', '--network', 'SD', \
                                                '-j1', '--config', 'bd_cli.yml', \
                                                'scan', BLACKDUCK_PROJECT, BLACKDUCK_VERSION, snippetParam, \
                                                '--source-path={}'.format(subScanPath)] + excludesParam, cmdEnv)
                if returncode != 0:
                    logging.debug('bd_cli failed scanning {}({},{})'.format(subScanPath, BLACKDUCK_PROJECT, BLACKDUCK_VERSION))
                    sys.exit(1)
                idx = idx + 1
            os.remove('bd_cli.yml')
        else:
            if configs['blackduck_offline_mode'] == True:
                # download signature scanner from mirror.rtkbf.com
                signatureScannerVersion = "2022.2.1"
                utils.makeEmptyDirectory('scan.cli')
                cmdEnv = dict(os.environ)
                cmdEnv['GIT_SSL_NO_VERIFY'] = 'true'
                cmdGit = sb.Popen(['git', 'clone', 'https://mirror.rtkbf.com/gerrit/sdlc/blackduck/scan.cli', \
                                    '--depth', '1', '-b', signatureScannerVersion, os.path.join(configs['WORK_DIR'], 'scan.cli')], stdout=sb.PIPE, env=cmdEnv)
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
            snippetParams = []
            offlineParams = []
            if configs['blackduck_snippet_scan'] == True:
                snippetParams = ['--detect.blackduck.signature.scanner.snippet.matching=FULL_SNIPPET_MATCHING']
            else:
                snippetParams = ['--detect.blackduck.signature.scanner.snippet.matching=NONE']
            if configs['blackduck_offline_mode'] == True:
                offlineParams = ['--detect.scan.output.path={}'.format(os.path.join(configs['WORK_DIR'], 'offline_output')), '--detect.blackduck.signature.scanner.local.path={}'.format(signatureScannerPath)]

            for subDir in subDirs:
                subScanPath = os.path.join(scanPath, subDir)
                cmdEnv = dict(os.environ)
                cmdEnv['SYNOPSYS_SKIP_PHONE_HOME'] = 'true'
                airgappedParams = []
                if configs['blackduck_airgap_mode'] == True:
                    airgappedParams = ['--detect.gradle.inspector.air.gap.path={}'.format(os.path.join('blackduck_scan', 'packaged-inspectors', 'gradle'))]
                utils.heavyLogging('bdScan: snippetParams {}'.format(snippetParams))
                utils.heavyLogging('bdScan: offlineParams {}'.format(offlineParams))
                utils.heavyLogging('bdScan: airgappedParams {}'.format(airgappedParams))
                cmdBDScan = sb.Popen(['java', '-jar', os.path.join(configs['WORK_DIR'], 'blackduck_scan', jarPath), \
                                    '--blackduck.api.token={}'.format(os.getenv('BD_TOKEN')), \
                                    '--blackduck.trust.cert=true', \
                                    '--blackduck.url={}'.format(BLACKDUCK_URL), \
                                    '--detect.excluded.directories={}'.format(generalExcludes), \
                                    '--detect.project.name={}'.format(BLACKDUCK_PROJECT), \
                                    '--detect.project.version.name={}'.format(BLACKDUCK_VERSION), \
                                    '--detect.source.path={}'.format(subScanPath), \
                                    '--blackduck.offline.mode={}'.format(configs['blackduck_offline_mode']), \
                                    '--detect.blackduck.scan.mode=INTELLIGENT', \
                                    '--detect.cleanup=false', \
                                    '--detect.timeout=800'
                                    #'--detect.tools=SIGNATURE_SCAN'
                                    ] + snippetParams + offlineParams + airgappedParams, stdout=sb.PIPE, env=cmdEnv)
                for line in cmdBDScan.stdout:
                    try:
                        line = line.decode("utf-8").rstrip()
                    except:
                        pass
                    utils.heavyLogging("bdScan: synopsys_detect " + line)
                cmdBDScan.communicate()
                if cmdBDScan.returncode != 0:
                    utils.heavyLogging('bdScan: synopsys_detect failed')
                    sys.exit(cmdBDScan.returncode)
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
    global configs

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
            logging.basicConfig(filename=os.path.join(workDir, 'blackduck.log'), level=logging.DEBUG, filemode='w')

    if skipTranslate == False:
        utils.translateConfig(configFile)
    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir
    if configs['blackduck_enabled'] == False:
        logging.debug('Skip blackduck scan')
        sys.exit(0)
    bdScan()

if __name__ == "__main__":
    main(sys.argv)
