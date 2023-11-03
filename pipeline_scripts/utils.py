import getopt, sys
import json
import os, shutil
import subprocess as sb
import logging

def loadConfigs(configFile):
    fpConfig = open(configFile)

    global configs
    configs = json.load(fpConfig)
    fpConfig.close()

    return configs

def checkLicense(baseDir, configs, action):
    if 'PF_STAGES' in os.environ:
        # pipeline framework, skip
        return
    cmdEnv = dict(os.environ)
    if 'BUILD_URL' in os.environ:
        # jenkins job, but not pipeline framework
        cmdEnv['BUILD_URL'] = os.getenv('BUILD_URL')
    else:
        # not pipeline framework, not jenkins job
        if 'realtek_unit' not in configs:
            print('Undefined unit')
            sys.exit(-99)
        rtkUnits = ['cn2sd5', 'cn2sd6', \
                        'cn3sd4', 'cn3sd7', 'cn3sd8', 'cn3sd9', \
                        'cn3wd1', 'cn3wd3', 'cn3wd7', \
                        'cm1sd1', 'cm1sd3', 'cm2sd6', \
                        'mm1', 'mm2sa', 'mm2sd', \
                        'pcswpcaud', 'rsipcam', \
                        'ctcsoc']
        configs['realtek_unit'] = configs['realtek_unit'].lower()
        if configs['realtek_unit'] not in rtkUnits:
            print('Invalid unit {}'.format(configs['realtek_unit']))
            sys.exit(-99)
        cmdEnv['BUILD_URL'] = 'https://{}.rtkbf.com/'.format(configs['realtek_unit'])
    cmdEnv['JOB_NAME'] = 'STANDALONE'
    cmdEnv['ACTIONS'] = action
    if baseDir == '':
        baseDir = 'pipeline_scripts'
    if os.name == "posix":
        prog = os.path.join(baseDir, 'wrapper_pipeline_linux')
    else:
        prog = os.path.join(baseDir, 'wrapper_pipeline_win.exe')
    try:
        cmdGit = sb.Popen([prog, '-s', 'CTCSOCPIPELINE'], stdout=sb.PIPE, env=cmdEnv)
        cmdGit.communicate()
    except:
        pass

def getREPOPath(srcDir, workDir):
    scriptPath = os.path.abspath(os.path.join(workDir, 'repoPath.sh'))
    scriptLog = os.path.abspath(os.path.join(workDir, 'repoPath.log'))

    repoPath = ''
    pwd = os.getcwd()
    os.chdir(srcDir)
    if os.path.isdir('.repo'):
        # REPO
        logging.debug('getREPOPath: REPO repository')
        if 'GERRIT_PROJECT' in os.environ:
            logging.debug('getDiffFiles: REPO project {}'.format(os.getenv('GERRIT_PROJECT')))
            with open(scriptPath, 'w') as f:
                f.write('#!/bin/sh\n\n')
                f.write('if [ "$REPO_PROJECT" = "$1" ]; then\n')
                f.write('    echo $REPO_PATH > {}\n'.format(scriptLog))
                f.write('fi')
            os.chmod(scriptPath, 0o744)
            repoCmd = '{} {}'.format(scriptPath, os.getenv('GERRIT_PROJECT'))
            cmdEnv = dict(os.environ)
            cmdEnv['REPO_TRACE'] = '1'
            cmdRepo = sb.Popen(['repo', 'forall', '-c', '{}'.format(repoCmd)], stdout=sb.PIPE, env=cmdEnv)
            cmdRepo.communicate()
            if os.path.isfile(scriptLog):
                fpLog = open(scriptLog, 'r')
                line = fpLog.readline()
                if line:
                    repoPath = line.strip()
                    logging.debug('getDiffFiles: got REPO_PATH {}'.format(repoPath))
                fpLog.close()
    else:
        logging.debug('getREPOPath: Non-REPO repository')

    os.chdir(pwd)
    return repoPath

def popenWithStdout(cmds, envs):
    cmdShell = sb.Popen(cmds, stdout=sb.PIPE, env=envs)
    print('popenWithStdout: {}'.format(cmdShell.args), flush=True)
    while True:
        line = cmdShell.stdout.readline()
        try:
            print(line.decode('utf-8').strip(), flush=True)
        except:
            print(line.strip(), flush=True)
        if not line:
            break
    cmdShell.communicate()
    return cmdShell.returncode

def popenReturnStdout(cmds, envs):
    cmdShell = sb.Popen(cmds, stdout=sb.PIPE, env=envs)
    print('popenReturnStdout: {}'.format(cmdShell.args), flush=True)
    lines = []
    while True:
        line = cmdShell.stdout.readline()
        #try:
        #    lines.append(line.decode('utf-8').strip())
        #except:
        lines.append(line.strip())
        if not line:
            break
    cmdShell.communicate()
    ret = dict()
    ret['code'] = cmdShell.returncode
    ret['lines'] = lines
    return ret

def popenReturnStderr(cmds, envs):
    cmdShell = sb.Popen(cmds, stdout=sb.PIPE, stderr=sb.PIPE, env=envs)
    print('popenReturnStdout: {}'.format(cmdShell.args), flush=True)
    lines = []
    while True:
        line = cmdShell.stderr.readline()
        #try:
        #    lines.append(line.decode('utf-8').strip())
        #except:
        lines.append(line.strip())
        if not line:
            break
    cmdShell.communicate()
    ret = dict()
    ret['code'] = cmdShell.returncode
    ret['lines'] = lines
    return ret

def popenReturnCode(cmds, envs):
    print('popenReturnCode: {}'.format(cmds), flush=True)
    cmdShell = sb.Popen(cmds, stdout=sb.PIPE, env=envs)
    cmdShell.communicate()
    return cmdShell.returncode

def popenFirstLine(cmds, envs):
    cmdShell = sb.Popen(cmds, stdout=sb.PIPE, env=envs)
    return cmdShell.stdout.readline().decode('utf-8').strip()

def heavyLogging(message):
    logging.debug(message)
    print(message, flush=True)

def lightLogging(message):
    logging.debug(message)

def hasEnv(var):
    if var in os.environ:
        return True
    return False

def getEnv(var):
    if var in os.environ:
        return os.getenv(var)
    return ''

def initEnv(workDir):
    # workDir: abs path
    if os.path.isfile(os.path.join(workDir, 'env')):
        os.remove(os.path.join(workDir, 'env'))
        heavyLogging('initEnv: remove {}'.format(os.path.join(workDir, 'env')))

def saveEnv(workDir, var, val):
    # workDir: abs path
    with open(os.path.join(workDir, 'env'), 'a') as fpEnv:
        fpEnv.write('{}={}\n'.format(var, val))

def addJenkinsArchives(workDir, fileName):
    # workDir: abs path
    with open(os.path.join(workDir, 'archives'), 'a') as fpEnv:
        fpEnv.write('{}:{}\n'.format(os.path.dirname(fileName), os.path.basename(fileName)))
    logging.debug('addJenkinsArchives: {}'.format(fileName))

def cleanEnvAndArchives(workDir):
    if os.path.exists(os.path.join(workDir, 'archives')):
        os.remove(os.path.join(workDir, 'archives'))
    if os.path.exists(os.path.join(workDir, 'env')):
        os.remove(os.path.join(workDir, 'env'))

def makeEmptyDirectory(dir):
    if os.path.exists(dir):
        shutil.rmtree(dir)
    os.makedirs(dir)

def getURFConfig(configFile, parameter):
    fpConfig = open(configFile, 'r')
    configs = fpConfig.readlines()
    fpConfig.close()
    for config in configs:
        if config.startswith('{}='.format(parameter)):
            tokens = config.split('=')
            return tokens[1]
    return ''

def queryURFReleaseRecord(smsId):
    postParam = "token={}&id={}".format('v482xkmhzafg', smsId)
    cmdCurl = sb.Popen(['curl', '-s', '-d', postParam, '-o', '.pf-urfrecord.json', \
                            'https://sms.realtek.com/RestApi/GetURFRecord'], stdout=sb.PIPE)
    cmdCurl.wait()
    with open('.pf-urfrecord.json') as f:
        jsonObject = json.load(f)
    #ret = int(jsonObject['StatusCode'])
    #print("Query SMS Release {} Status: {}".format(smsId, ret), flush=True)

    return jsonObject

def queryURFReleaseStatus(account, token, smsId):
    # 0: Start SD release
    # 10: Check by checkers (done)
    # 20: Finish SD release (done)
    # 25: Finish IT release (done)
    # 210: Check by checkers (fail)
    # 207: Parse software BOM (fail)
    ret = -1
    postParam = "Account={}&Token={}&Id={}".format(account, token, smsId)
    cmdCurl = sb.Popen(['curl', '-s', '-d', postParam, '-o', '.pf-queryurf.json', \
                            'https://sms.realtek.com/RestApi/ReleaseStatus'], stdout=sb.PIPE)
    cmdCurl.wait()
    with open('.pf-queryurf.json') as f:
        jsonObject = json.load(f)
    ret = int(jsonObject['StatusCode'])
    print("Query SMS Release {} Status: {}".format(smsId, ret), flush=True)

    return ret

# configs['coverity_host']
# configs['coverity_port']
# configs['coverity_stream']
#def retrieveCoverityProjectFromStream(configs, covuser, covkey):
#    if 'coverity_url' in configs:
#        covUrl = configs['coverity_url']
#        if covUrl.endswith('/') == False:
#            covUrl = covUrl + "/"
#    elif 'coverity_host' in configs:
#        coverityHost = configs['coverity_host']
#        coverityPort = configs['coverity_port']
#        covUrl = 'http://{}:{}/'.format(coverityHost, coverityPort)
#    elif 'PF_COV_HOST' in os.environ:
#        coverityHost = os.getenv('PF_COV_HOST')
#        coverityPort = os.getenv('PF_COV_PORT')
#        covUrl = 'http://{}:{}/'.format(coverityHost, coverityPort)
#    cmdCurl = sb.Popen(['curl', '-s', '-X', 'GET', '-H', 'Content-Type: application/json', \
#                    '-H', 'Accept: application/json', '--user', '{}:{}'.format(covuser, covkey), \
#                    '{}api/v2/streams/{}?locale=en_us'.format(covUrl, configs["coverity_stream"])], stdout=sb.PIPE)
#    cmdCurl.wait()
#    coverityProject = ""
#    while True:
#        line = cmdCurl.stdout.readline()
#        projectObj = json.loads(line)
#        coverityProject = projectObj["streams"][0]["primaryProjectName"]
#        break
#    print("UTILS: got coverity project name {}".format(coverityProject))
#    return coverityProject

def isScriptedParameter(parameter):
    if parameter is None or parameter == "":
        return False

    if isinstance(parameter, str):
        dynamicPrefixes = ["sh", "bat", "bash"]
        tokens = parameter.split()
        if tokens[0] in dynamicPrefixes:
            return True
        else:
            return False

    return False

def extractShellParameter(parameter):
    pfRoot = ''
    if 'PF_ROOT' in os.environ:
        pfRoot = os.getenv('PF_ROOT')
    print("utils: extractShellParameter param '{}':".format(parameter), flush=True)
    tokens = parameter.split()
    if parameter.startswith("sh") or parameter.startswith("bash"):
        cmd = sb.Popen([tokens[0], os.path.join(pfRoot, 'scripts', tokens[1])], stdout=sb.PIPE)
    else:
        cmd = sb.Popen([os.path.join(pfRoot, 'scripts', tokens[1])], stdout=sb.PIPE)
    cmd.wait()
    while True:
        extractedParam = cmd.stdout.readline()
        extractedParam = str(extractedParam.strip(), 'utf-8')
        break
    print("utils: extractShellParameter value '{}'".format(extractedParam), flush=True)
    return extractedParam

def extractScriptedParameter(param, stashName):
    extractedParam = ""

    if param is None:
        extractedParam = ""
    elif isScriptedParameter(param) == True:
        extractedParam = extractShellParameter(param)
    elif isinstance(param, str) and ("%" in param or "$" in param):
        try:
            os.mkdir('.pf-parameters')
        except FileExistsError:
            pass
        pwd = os.getcwd()
        os.chdir('.pf-parameters')
        f = open('{}.bat'.format(stashName), "w")
        if os.name != "posix":
            f.write('@echo off\n')
        else:
            param = param.replace('\"', '\\"')
        f.write("echo {}".format(param))
        f.close()
        if os.name == "posix":
            cmd = sb.Popen(['sh', '{}.bat'.format(stashName)], stdout=sb.PIPE)
        else:
            cmd = sb.Popen(['{}.bat'.format(stashName)], stdout=sb.PIPE)
        cmd.wait()
        while True:
            extractedParam = cmd.stdout.readline()
            extractedParam = str(extractedParam.strip(), 'utf-8')
            break
        os.chdir(pwd)
    else:
        if isinstance(param, str):
            extractedParam = param.strip()
        else:
            extractedParam = param

    return extractedParam

def translateConfig(configFile):
    logging.debug('translateConfig: {}'.format(configFile))
    stageName = os.path.splitext(os.path.basename(configFile))[0]
    plainStageName = stageName.replace("@", "at")

    with open(os.path.join(configFile)) as f:
        stageConfigs = json.load(f)
    for key in stageConfigs:
        # scripted params may be.
        if isinstance(stageConfigs[key], list):
            # like scm_branchs: ["master"]
            for i in range(len(stageConfigs[key])):
                stageConfigs[key][i] = extractScriptedParameter(stageConfigs[key][i], "{}-params-{}-{}".format(plainStageName, key, i))
        elif isinstance(stageConfigs[key], dict):
            # like parallel_parameters: { "os": ["linux", "windows", "macos"] },
            for paramKey in stageConfigs[key]:
                if isinstance(stageConfigs[key][paramKey], list):
                    for i in range(len(stageConfigs[key][paramKey])):
                        stageConfigs[key][paramKey][i] = extractScriptedParameter(stageConfigs[key][paramKey][i], "{}-params-{}-{}-{}".format(plainStageName, key, paramKey, i), pfRoot)
                elif isinstance(stageConfigs[key][paramKey], str):
                    stageConfigs[key][paramKey] = extractScriptedParameter(stageConfigs[key][paramKey], "{}-params-{}-{}".format(plainStageName, key, paramKey))
        else:
            # scalar variables: like string, boolean
            # ex. repo_path: "repo"
            stageConfigs[key] = extractScriptedParameter(stageConfigs[key], "{}-params-{}".format(plainStageName, key))
    with open(os.path.join(configFile), "w") as outfile:
        json.dump(stageConfigs, outfile, indent=2)

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'c:f:v', ["command=", "config=", "version"])
    except getopt.GetoptError:
        sys.exit()

    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-c', '--command'):
            # override if --user
            command = value
        elif name in ('-f', '--config'):
            # override if --user
            configFile = value

    if command == "TRANSLATE_CONFIG":
        translateConfig(configFile)
        sys.exit(0)

if __name__ == "__main__":
    main(sys.argv)