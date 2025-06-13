import getopt, sys
import json
import os, shutil
import subprocess as sb
import logging
import stat
import time

POPEN_TIMEOUT=999

def getCodetekPrompts(promptsFile):
    ret = []
    fpPrompts = open(promptsFile, 'r')
    while True:
        line = fpPrompts.readline()
        if not line:
            break
        ret.append(line.strip())
    fpPrompts.close()
    return ret

def checkSingularity(workDir):
    error = False
    try:
        popenReturnStdout(['singularity', '--version'], dict(os.environ))
        popenReturnStdout(['git', '--version'], dict(os.environ))
    except:
        error = True
    lfsCheck = popenReturnCode(['git', 'lfs', '--version'], dict(os.environ))
    if error == True or lfsCheck != 0:
        # singularity not exist
        # git lfs not available
        with open(os.path.join(workDir, 'singularity_error'), 'w') as f:
            f.write('error')

def getPFPreviewReport(basePhase=False):
    baseSuffix = ''
    if basePhase == True:
        baseSuffix = '_parent'
    if 'BUILD_BRANCH' in os.environ:
        return 'preview-report-committer-{}{}.json'.format(os.getenv('BUILD_BRANCH'), baseSuffix)
    else:
        return 'preview-report-committer{}.json'.format(baseSuffix)

def parseUrl(url):
    ret = []
    # separate url and path, ssh://psp.sdlc.rd.realtek.com:29418/test/test ->
    # ret[0] ssh://psp.sdlc.rd.realtek.com:29418
    # ret[1] test/test
    tokens = url.split("//")
    if len(tokens) == 1:
        # git@github.com:reyzheng/test.git
        tokens = url.split(":")
        ret.append(tokens[0])
        ret.append(tokens[1])
    else:
        protocol = tokens[0] # https: or ssh:
        addr = tokens[1][:tokens[1].index('/')] # psp.sdlc.rd.realtek.com:29418
        path = tokens[1][tokens[1].index('/') + 1:] # test/test
        ret.append('{}//{}'.format(protocol, addr))
        ret.append(path)

    return ret

def delRW(action, name, exc):
    os.chmod(name, stat.S_IWRITE)
    os.remove(name)

def loadConfigs(configFile):
    fpConfig = open(configFile, encoding='utf-8')

    global configs
    configs = json.load(fpConfig)
    fpConfig.close()

    return configs

def checkLicense(baseDir, configs, action):
    rsnetwork = False
    if 'PF_STAGES' in os.environ:
        # pipeline framework, skip
        return
    cmdEnv = dict(os.environ)
    if 'BUILD_URL' in os.environ:
        # jenkins job, but not pipeline framework
        cmdEnv['BUILD_URL'] = os.getenv('BUILD_URL')
        if os.getenv('BUILD_URL').startswith('https://rs'):
            rsnetwork = True
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
    if rsnetwork == True:
        cmdEnv['PSP_LICENSE_SERVER'] = '5679@172.29.82.1'
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

def popenBackground(cmds, envs):
    cmdShell = sb.Popen(cmds, stdout=sb.PIPE, env=envs)
    print('popenBackground: {}'.format(cmdShell.args), flush=True)

def popenWithStdout(cmds, envs, verbose=True):
    cmdShell = sb.Popen(cmds, stdout=sb.PIPE, env=envs)
    if verbose == True:
        #print('popenWithStdout: {}'.format(cmdShell.args), flush=True)
        print('popenWithStdout: {}'.format([x.encode('utf-8') for x in cmdShell.args]), flush=True)
    while True:
        line = cmdShell.stdout.readline()
        if not line:
            break
        try:
            print(line.decode('utf-8').strip(), flush=True)
        except:
            print(line.strip(), flush=True)
    cmdShell.communicate()
    return cmdShell.returncode

def popenWithStdoutTimeout(cmds, timeout_s, retry, envs):
    try:
        cmdShell = sb.Popen(cmds, stdout=sb.PIPE, env=envs)
        print('popenWithStdoutTimeout: {}'.format(cmdShell.args), flush=True)
        cmdShell.wait(timeout=timeout_s)
    except sb.TimeoutExpired:
        cmdShell.kill()
        heavyLogging('popenWithStdoutTimeout: {}({}) expired'.format(cmdShell.pid, timeout_s))
        # try again
        if retry == True:
            time.sleep(1)
            heavyLogging('popenWithStdoutTimeout: retry')
            return popenWithStdoutTimeout(cmds, timeout_s, False, envs)
        else:
            return POPEN_TIMEOUT
    while True:
        line = cmdShell.stdout.readline()
        if not line:
            break
        try:
            print(line.decode('utf-8').strip(), flush=True)
        except:
            print(line.strip(), flush=True)
    return cmdShell.returncode

def system(cmds):
    print('system: {}'.format(cmds), flush=True)
    return os.system(cmds)
    #result = sb.run(cmds, shell=True)
    #return result.returncode

def popenToFile(cmds, envs, fileStdout, fileStderr):
    with open(fileStdout, 'wb') as fpOut, open(fileStderr, 'wb') as fpErr:
        cmdShell = sb.Popen(cmds, stdout=fpOut, stderr=fpErr, env=envs, universal_newlines=True)
        print('popenToFile: {} ({}, {})'.format([x.encode('utf-8') for x in cmdShell.args], fileStdout, fileStderr), flush=True)
        while cmdShell.poll() is None:
            time.sleep(1)
    return cmdShell.returncode

def popenReturnStdout(cmds, envs, strip=True):
    print('popenReturnStdout: {}'.format(' '.join(cmds), flush=True))
    cmdShell = sb.Popen(cmds, stdout=sb.PIPE, env=envs)
    lines = []
    while True:
        line = cmdShell.stdout.readline()
        if not line:
            break
        if strip == True:
            lines.append(line.strip())
        else:
            lines.append(line)
    cmdShell.communicate()
    ret = dict()
    ret['code'] = cmdShell.returncode
    ret['lines'] = lines
    return ret

def popenReturnStderr(cmds, envs):
    cmdShell = sb.Popen(cmds, stdout=sb.PIPE, stderr=sb.PIPE, env=envs)
    print('popenReturnStderr: {}'.format(cmdShell.args), flush=True)
    lines = []
    while True:
        line = cmdShell.stderr.readline()
        if not line:
            break
        lines.append(line.strip())
    cmdShell.communicate()
    ret = dict()
    ret['code'] = cmdShell.returncode
    ret['lines'] = lines
    return ret

def popenReturnStdoutStderr(cmds, envs):
    cmdShell = sb.Popen(cmds, stdout=sb.PIPE, stderr=sb.PIPE, env=envs)
    print('popenReturnStdouterr: {}'.format(cmdShell.args), flush=True)
    lines = []
    while True:
        line = cmdShell.stderr.readline()
        if not line:
            break
        lines.append(line.strip())
    while True:
        line = cmdShell.stdout.readline()
        if not line:
            break
        lines.append(line.strip())
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
    try:
        print(message, flush=True)
    except:
        print(message.encode('utf-8'), flush=True)

def lightLogging(message):
    logging.debug(message)

def getEnv(var, branch=None):
    if var.startswith('PIPELINEGLOBAL_'):
        # prefix PIPELINEGLOBAL_ is global, dont care BUILD_BRANCH
        pass
    elif branch is not None:
        if branch != 'PF_NONE':
            var = 'BR{}_{}'.format(branch, var)
        else:
            pass
    else:
        if 'BUILD_BRANCH' in os.environ:
            var = 'BR{}_{}'.format(os.getenv('BUILD_BRANCH'), var)
        else:
            pass

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
    gadgets = ['.artifacts', 'archives', 'env', 'pf-htmlreport.html', '.coverity-diff']
    for gadget in gadgets:
        if os.path.isfile(os.path.join(workDir, gadget)):
            os.remove(os.path.join(workDir, gadget))
            heavyLogging('cleanEnvAndArchives: remove {}'.format(os.path.join(workDir, gadget)))

def cleanAll(workDir):
    for filename in os.listdir(workDir):
        file_path = os.path.join(workDir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
            heavyLogging('cleanAll: delete {}'.format(filename))
        except Exception as e:
            heavyLogging('cleanAll: failed to delete %s. Reason: %s' % (file_path, e))

def makeEmptyDirectory(dir):
    if os.path.exists(dir):
        shutil.rmtree(dir, onerror=delRW)
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
    # errors='ignore' to avoid encoding issue on windows
    with open('.pf-urfrecord.json', errors='ignore') as f:
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

def isScriptedParameter(parameter):
    if parameter is None or parameter == "":
        return False

    if isinstance(parameter, str):
        dynamicPrefixes = ["sh", "bat", "bash", "python", "python3"]
        tokens = parameter.split()
        if tokens[0] in dynamicPrefixes and len(tokens) > 1:
            # check len(tokens) > 1 to avoid the case like
            # "coverity_comptype_platform": [ "python" ],
            return True
        else:
            return False

    return False

def extractShellParameter(parameter, paramName):
    pfRoot = ''
    if 'PF_ROOT' in os.environ:
        pfRoot = os.getenv('PF_ROOT')
    elif 'PF_PATH' in os.environ:
        pfRoot = os.getenv('PF_PATH')
    print("utils: extractShellParameter param '{}'({})".format(parameter, pfRoot), flush=True)
    tokens = parameter.split()
    nonBatches = ['sh', 'bash', 'python', 'python3']
    if tokens[0] in nonBatches:
        cmdPieces = [tokens[0], os.path.join(pfRoot, 'scripts', tokens[1])]
    else:
        cmdPieces = [os.path.join(pfRoot, 'scripts', tokens[1])]
    if paramName is not None:
        cmdPieces.append(paramName)
    cmd = sb.Popen(cmdPieces, stdout=sb.PIPE)
    cmd.wait()
    while True:
        extractedParam = cmd.stdout.readline()
        extractedParam = str(extractedParam.strip(), 'utf-8')
        break
    print("utils: extractShellParameter value '{}'".format(extractedParam), flush=True)
    return extractedParam

def extractScriptedParameter(param, stashName, paramName=None):
    extractedParam = ""

    if param is None:
        extractedParam = ""
    elif isScriptedParameter(param) == True:
        extractedParam = extractShellParameter(param, paramName)
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
        if os.name == "posix":
            f.write("echo \"{}\"".format(param))
        else:
            f.write("echo {}".format(param))
        f.close()
        cmdEnv = dict(os.environ)
        if os.name == "posix":
            cmd = sb.Popen(['sh', '{}.bat'.format(stashName)], stdout=sb.PIPE, env=cmdEnv)
        else:
            cmd = sb.Popen(['{}.bat'.format(stashName)], stdout=sb.PIPE, env=cmdEnv)
        cmd.wait()

        params = []
        while True:
            line = cmd.stdout.readline()
            if not line:
                break
            line = str(line.strip(), 'utf-8', errors='ignore')
            if line == 'ECHO is off.':
                line = ''
            params.append(line)
            if line == '':
                break
        if len(params) == 1:
            extractedParam = params[0]
        else:
            extractedParam = ' '.join(params)
        os.chdir(pwd)
    else:
        if isinstance(param, str):
            extractedParam = param.strip()
        else:
            extractedParam = param

    return extractedParam

def translateConfig(configFile):
    heavyLogging('translateConfig: {}'.format(configFile))
    stageName = os.path.splitext(os.path.basename(configFile))[0]
    plainStageName = stageName.replace("@", "at")

    with open(os.path.join(configFile), encoding='utf-8') as f:
        stageConfigs = json.load(f)
    staticParams = []
    if 'staticParams' in stageConfigs:
        staticParams = stageConfigs['staticParams']
    for key in stageConfigs:
        if key in staticParams:
            # skip staticParams
            lightLogging('translateConfig: skip staticParam {}'.format(key))
            continue
        if key.startswith('//'):
            # skip comment params, like "//scm_refspecs" : [ "$GERRIT_REFSPEC:$GERRIT_REFSPEC" ],
            continue
        # scripted params may be.
        if isinstance(stageConfigs[key], list):
            # like scm_branchs: ["master"]
            lightLogging('translateConfig: key {}(list)'.format(key))
            for i in range(len(stageConfigs[key])):
                stageConfigs[key][i] = extractScriptedParameter(stageConfigs[key][i], "{}-params-{}-{}".format(plainStageName, key, i), paramName=key)
            if key == 'parallel_excludes' and len(stageConfigs[key]) == 1:
                stageConfigs[key] = stageConfigs[key][0].split()
        elif isinstance(stageConfigs[key], dict):
            # like parallel_parameters: { "os": ["linux", "windows", "macos"] },
            # key: parallel_parameters
            # paramKey: os
            lightLogging('translateConfig: key {}(dict)'.format(key))
            for paramKey in stageConfigs[key]:
                if isinstance(stageConfigs[key][paramKey], list):
                    for i in range(len(stageConfigs[key][paramKey])):
                        stageConfigs[key][paramKey][i] = extractScriptedParameter(stageConfigs[key][paramKey][i], "{}-params-{}-{}-{}".format(plainStageName, key, paramKey, i), paramName=key)
                elif isinstance(stageConfigs[key][paramKey], str):
                    stageConfigs[key][paramKey] = extractScriptedParameter(stageConfigs[key][paramKey], "{}-params-{}-{}".format(plainStageName, key, paramKey), paramName=key)
                if key == 'parallel_parameters' and len(stageConfigs[key][paramKey]) == 1:
                    stageConfigs[key][paramKey] = stageConfigs[key][paramKey][0].split()
        else:
            # scalar variables: like string, boolean
            # ex. repo_path: "repo"
            lightLogging('translateConfig: key {}(scalar)'.format(key))
            stageConfigs[key] = extractScriptedParameter(stageConfigs[key], "{}-params-{}".format(plainStageName, key), paramName=key)
    with open(os.path.join(configFile), 'w', encoding='utf-8') as outfile:
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
