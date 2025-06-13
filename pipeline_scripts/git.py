import os, json, re, sys, time, shutil
import subprocess as sb
import utils
import fnmatch

def getSourceFiles(sourceDir):
    files = []
    for root, dirnames, filenames in os.walk(sourceDir):
        for filename in fnmatch.filter(filenames, '*.c'):
            files.append(os.path.join(root, filename))
        for filename in fnmatch.filter(filenames, '*.cpp'):
            files.append(os.path.join(root, filename))
    for i in range(len(files)):
        files[i] = os.path.relpath(files[i], sourceDir)

    return files

def gerritQueryCommitComments(workDir):
    commitMessage = ''
    # ssh -p 29418 ctcsoc.rtkbf.com gerrit query --format JSON --all-reviewers status:open project:test/test change:20115
    if 'GERRIT_PROJECT' in os.environ:
        if 'GERRIT_USER' in os.environ:
            cmdPieces = ['ssh', '-l', os.getenv('GERRIT_USER'), '-i', os.getenv('GERRIT_KEY')]
        else:
            cmdPieces = ['ssh']
        cmdPieces += ['-p', os.getenv('GERRIT_PORT'), os.getenv('GERRIT_HOST'), \
                        'gerrit', 'query', '--format', 'JSON', '--current-patch-set', '--commit-message', \
                        'project:{}'.format(os.getenv('GERRIT_PROJECT')), \
                        'change:{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'))]
        logFile = os.path.join(workDir, 'gerritQueryCommitComments.json')
        utils.heavyLogging('gerritQueryCommitComments: {}'.format(cmdPieces))
        utils.popenToFile(cmdPieces, dict(os.environ), logFile, logFile)
        with open(logFile) as fpLog:
            # read first line
            line = fpLog.readline()
            try:
                jsonLog = json.loads(line)
                if 'project' in jsonLog and 'commitMessage' in jsonLog:
                    commitMessage = jsonLog['commitMessage']
            except:
                utils.heavyLogging('gerritQueryCommitComments: invalid commit message({})'.format(line))
                sys.exit(-1)
    return commitMessage

def gerritQueryReviewers(workDir, outputFile):
    # ssh -p 29418 ctcsoc.rtkbf.com gerrit query --format JSON --all-reviewers status:open project:test/test change:20115
    if 'GERRIT_PROJECT' in os.environ:
        if 'GERRIT_USER' in os.environ:
            cmdPieces = ['ssh', '-l', os.getenv('GERRIT_USER'), '-i', os.getenv('GERRIT_KEY')]
        else:
            cmdPieces = ['ssh']
        cmdPieces += ['-p', os.getenv('GERRIT_PORT'), os.getenv('GERRIT_HOST'), \
                        'gerrit', 'query', '--format', 'JSON', '--all-reviewers', \
                        'project:{}'.format(os.getenv('GERRIT_PROJECT')), \
                        'change:{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'))]
        logFile = os.path.join(workDir, 'gerritQueryReviewers.json')
        utils.heavyLogging('gerritQueryReviewers: {}'.format(cmdPieces))
        utils.popenToFile(cmdPieces, dict(os.environ), logFile, logFile)
        with open(logFile) as fpLog:
            # read first line
            line = fpLog.readline()
            try:
                jsonLog = json.loads(line)
                if 'project' in jsonLog and 'allReviewers' in jsonLog:
                    fpReviewers = open(outputFile, 'w')
                    reviewers = []
                    for reviewer in jsonLog['allReviewers']:
                        reviewers.append(reviewer['email'])
                    fpReviewers.write(','.join(reviewers))
                    fpReviewers.close()
            except:
                pass

def updateFile(file, patch):
    shutil.copyfile(patch, file)
    utils.heavyLogging('updateFile: {} to {}'.format(patch, file))

def updateFunction(file, patch, identifier):
    block = None
    import parser
    functions = parser.getSourceFileMap('', file)
    for function in functions:
        lineToGet = function['identifier_start_point'][0]
        idx = 0
        with open(file) as fp:
            while True:
                line = fp.readline()
                if not line:
                    break
                if idx == lineToGet:
                    identifierToCompare = line[function['identifier_start_point'][1]:function['identifier_end_point'][1]]
                    if identifier == identifierToCompare:
                        block = parser.Point(function['start_point'][0], function['end_point'][0])
                        break
                idx = idx + 1
    utils.heavyLogging('updateFunction: apply')
    utils.popenWithStdout(['cat', '-n', patch], dict(os.environ))
    utils.heavyLogging('updateFunction: before')
    utils.popenWithStdout(['cat', '-n', file], dict(os.environ))
    if block is not None:
        utils.heavyLogging('updateFunction: replace {}, {}'.format(block.x, block.y))
        patchApplied = False
        temporal = '{}_{}.tmp'.format(patch, identifier)
        fpTemporal = open(temporal, 'w')
        idx = 0
        with open(file) as fp:
            while True:
                line = fp.readline()
                if not line:
                    break
                if idx < block.x:
                    # upper part
                    fpTemporal.write(line)
                elif idx >= block.x and idx <= block.y:
                    # patch part
                    if patchApplied == False:
                        with open(patch) as fpPatch:
                            while True:
                                line = fpPatch.readline()
                                if not line:
                                    break
                                fpTemporal.write(line)
                            # NOTICE: an extra empty line required (from real test, i dont know why)
                            fpTemporal.write('\n')
                        patchApplied = True
                else:
                    # bottom part
                    fpTemporal.write(line)
                idx = idx + 1
        fpTemporal.close()
        shutil.copyfile(temporal, file)
        utils.heavyLogging('updateFunction: move {}({}) to {}'.format(patch, identifier, file))
        utils.popenWithStdout(['cat', '-n', file], dict(os.environ))

def commitRepatch(sourceDir, comment, changeId):
    # re-upload patchset with same changeId
    pwd = os.getcwd()

    os.chdir(sourceDir)
    envs = dict(os.environ)

    utils.heavyLogging('commitAndPush: git status')
    cmds = ['git', 'status']
    utils.popenWithStdout(cmds, envs)

    utils.heavyLogging('commitAndPush: git commit')
    commitMessage = '{}\n{}\n\n{}'.format(comment, os.getenv('BUILD_URL'), changeId)
    cmds = ['git', 'commit', '-s', '-a', '--amend', '--no-edit', '-m', commitMessage]
    utils.popenWithStdout(cmds, envs)

    utils.heavyLogging('commitAndPush: git commit message {}, branch {}'.format(commitMessage, os.getenv('GERRIT_BRANCH')))
    cmds = ['git', 'push', 'origin', 'HEAD:refs/for/{}'.format(os.getenv('GERRIT_BRANCH'))]
    utils.popenWithStdout(cmds, envs)

    os.chdir(pwd)

def commitReview(sourceDir, comment):
    # upload a whole new change
    pwd = os.getcwd()

    os.chdir(sourceDir)
    envs = dict(os.environ)

    utils.heavyLogging('commitAndPush: git status')
    cmds = ['git', 'status']
    utils.popenWithStdout(cmds, envs)

    utils.heavyLogging('commitAndPush: git commit')
    commitMessage = '{}\n{}'.format(comment, os.getenv('BUILD_URL'))
    cmds = ['git', 'commit', '-s', '-m', commitMessage]
    utils.popenWithStdout(cmds, envs)
    # compute new change Id
    cmds = ['git', 'rev-parse', 'HEAD']
    ret = utils.popenReturnStdout(cmds, envs)
    fpRevision = open('.pf-revision-info', 'w')
    fpRevision.write(ret['lines'][0].decode('utf-8'))
    fpRevision.close()
    cmds = ['git', 'hash-object', '.pf-revision-info']
    ret = utils.popenReturnStdout(cmds, envs)
    changeId = ret['lines'][0].decode('utf-8')
    # Change Id starts with 'I'
    commitMessage = '{}\n{}\n\nChange-Id: I{}\n'.format(comment, os.getenv('BUILD_URL'), changeId)
    cmds = ['git', 'commit', '-s', '-a', '--amend', '--no-edit', '-m', commitMessage]
    utils.popenWithStdout(cmds, envs)

    utils.heavyLogging('commitAndPush: git commit message {}, branch {}'.format(commitMessage, os.getenv('GERRIT_BRANCH')))
    cmds = ['git', 'push', 'origin', 'HEAD:refs/for/{}'.format(os.getenv('GERRIT_BRANCH'))]
    patchUrl = ''
    ret = utils.popenReturnStderr(cmds, envs)
    pattern = re.compile("^remote:\s+https:")
    for line in ret['lines']:
        line = line.decode('utf-8')
        utils.heavyLogging('commitReview: {}'.format(line))
        if pattern.match(line):
            patchUrl = line.split()[1]

    os.chdir(pwd)
    return patchUrl

def getLastModifiedDate(fullPath):
    pwd = os.getcwd()
    lastModifiedDate = time.strptime('1970-01-01', '%Y-%m-%d')
    try:
        dirName = os.path.dirname(fullPath)
        baseName = os.path.basename(fullPath)
        os.chdir(dirName)
        stdout = utils.popenReturnStdout(['git', 'log', '-1', '--format=%ci', '--', baseName], dict(os.environ))
        line = stdout['lines'][0]
        try:
            line = line.decode('utf-8')
        except:
            pass
        tokens = line.split()
        lastModifiedDate = time.strptime(tokens[0], '%Y-%m-%d')
    except Exception as e:
        print(e)
        pass
    os.chdir(pwd)
    return lastModifiedDate

def findAuthor(lineNumber, fileName):
    ret = dict()
    ret['author'] = ''
    ret['authorfull'] = ''
    # git blame -e -L ${lineNumber},${lineNumber} \"${filePathname}\"
    author = sb.Popen(['git', 'blame' , '-e', '-L', '{},{}'.format(lineNumber, lineNumber), fileName], stdout=sb.PIPE)
    line = author.stdout.readline()
    line = line.decode("utf-8") .strip()
    #if "realtek/realsil/apowertec" in line:
    if "@" in line:
        line = re.split('[>< ]', line)
        if '@' in line[2]:
            line = line[2]
        else:
            line = line[3]
        tokens = line.split('@')
        ret['author'] = tokens[0]
        ret['authorfull'] = line
        utils.heavyLogging('findAuthor: valid author, {}'.format(ret['authorfull']))
    else:
        utils.heavyLogging('findAuthor: invlid author, {}'.format(fileName))
    return ret

def recursiveRevision(dir):
    pwd = os.getcwd()
    utils.heavyLogging('recursiveRevision: pwd {}'.format(pwd))

    if dir != '':
        os.chdir(dir)
    cmdEnv = dict(os.environ)
    cmdPieces = ['git', 'rev-parse', 'HEAD']
    utils.popenWithStdout(cmdPieces, cmdEnv)
    cmdPieces = ['git', 'submodule', 'foreach', '--recursive', 'git', 'rev-parse', 'HEAD']
    utils.popenWithStdout(cmdPieces, cmdEnv)

    os.chdir(pwd)

def getFileLineRevision(dir, file, line):
    ret = dict()
    ret['revision'] = ''
    ret['committer'] = ''
    ret['committerfull'] = ''
    #git log -1 --pretty=format:%h -u -L 1221,1221:utility.c
    pwd = os.getcwd()

    if dir != '':
        os.chdir(dir)
    utils.heavyLogging('getFileLineRevision: pwd {}, fileName, {}'.format(os.getcwd(), file))
    cmdPieces = ['git', 'log', '-1', '--pretty=format:%h,%ce', '-L', '{},{}:{}'.format(line, line, file)]
    try:
        stdout = sb.check_output(cmdPieces, timeout=15)
        line = stdout.decode('utf-8').splitlines()
        line = line[0].strip()
        if "@" in line and "," in line:
            tokens = line.split(',')
            ret['revision'] = tokens[0]
            committerTokens = tokens[1].split('@')
            ret['committer'] = committerTokens[0]
            ret['committerfull'] = tokens[1]
            utils.heavyLogging('getFileLineRevision: {}, {}'.format(ret['revision'], ret['committer']))
    except Exception as e:
        utils.heavyLogging('getFileLineRevision: invlid committer, revision')
        utils.heavyLogging(e)
        pass

    os.chdir(pwd)
    return ret

def getRevision(dir):
    pwd = os.getcwd()

    if dir != '':
        os.chdir(dir)
    cmdEnv = dict(os.environ)
    cmdPieces = ['git', 'rev-parse', 'HEAD']
    stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
    revision = bytes.decode(stdout['lines'][0], 'utf-8')

    os.chdir(pwd)
    return revision

def listRevisions(dir, startRevision, endRevision):
    pwd = os.getcwd()

    if dir != '':
        os.chdir(dir)

    cmdRemote = sb.Popen(['git', 'remote', '-v'], stdout=sb.PIPE)
    if os.name == "posix":
        remoteFetch = sb.check_output(('grep', 'fetch'), stdin=cmdRemote.stdout)
    else:
        remoteFetch = sb.check_output(('findstr', '/l', 'fetch'), stdin=cmdRemote.stdout)
    cmdRemote.wait()
    lines = remoteFetch.decode("utf-8").splitlines()
    for line in lines:
        tokens = line.split()
        gitRemote = tokens[0]
        utils.heavyLogging('listRevisions: get remote name {}'.format(gitRemote))
        break

    cmdEnv = dict(os.environ)
    cmdPieces = ['git', 'pull', gitRemote, '--unshallow']
    try:
        utils.popenWithStdout(cmdPieces, cmdEnv)
    except:
        pass
    cmdPieces = ['git', 'rev-list', '{}^..{}'.format(startRevision, endRevision)]
    stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
    ret = []
    for i in range(len(stdout['lines'])):
        idx = len(stdout['lines']) - i - 1
        ret.append(bytes.decode(stdout['lines'][idx], 'utf-8'))

    os.chdir(pwd)
    return ret

def getSubmodulesInfo(dir):
    pwd = os.getcwd()

    if dir != '':
        os.chdir(dir)
    # get remote
    cmdEnv = dict(os.environ)
    cmdPieces = ['git', 'submodule', 'foreach', '--recursive', 'git', 'remote', 'get-url', 'origin']
    stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
    remotes = dict()
    # TODO: handle exception
    for line in stdout['lines']:
            line = bytes.decode(line, 'utf-8').strip()
            if line.startswith('Entering '):
                tokens = line.split()
                index = tokens[1][1:-1]
            else:
                if index is not None:
                    remotes[index] = line
    # get revision, path
    jsonSources = []
    cmdPieces = ['git', 'submodule', 'status', '--recursive']
    stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
    for line in stdout['lines']:
        line = bytes.decode(line, 'utf-8').strip()
        tokens = line.split()
        jsonSource = dict()
        jsonSource['revision'] = tokens[0]
        jsonSource['path'] = tokens[1]
        if tokens[1] in remotes:
            urlTokens = utils.parseUrl(remotes[tokens[1]])
            jsonSource['addr'] = urlTokens[0]
            jsonSource['name'] = urlTokens[1]
            jsonSources.append(jsonSource)

    os.chdir(pwd)
    return jsonSources

def revisionInfo(configs, idx):
    revisionFile = os.path.join(configs['WORK_DIR'], '.pf-revision-info')
    if os.path.isfile(revisionFile):
        try:
            with open(revisionFile) as fpRevisionInfo:
                jsonGitInfo = json.load(fpRevisionInfo)
        except:
            # existed .pf-revision-info is xml REPO manifest, skip
            utils.heavyLogging('revisionInfo: skip existed REPO manifest')
            return
    else:
        jsonGitInfo = dict()
        jsonGitInfo['sources'] = []

    jsonSource = dict()
    urlTokens = utils.parseUrl(configs['scm_urls'][idx])
    jsonSource['addr'] = urlTokens[0]
    jsonSource['name'] = urlTokens[1]
    jsonSource['path'] = configs['scm_dsts'][idx]
    revision = getRevision(configs['scm_dsts'][idx])
    jsonSource['revision'] = revision
    jsonSource['upstream'] = configs['scm_branchs'][idx]
    utils.heavyLogging('revisionInfo: git, {}'.format(jsonSource))
    jsonGitInfo['sources'].append(jsonSource)
    # TODO: git submodules revision info.
    #submoduleSources = getSubmodulesInfo(configs['scm_dsts'][idx])
    #jsonGitInfo['sources'].extend(submoduleSources)

    with open(revisionFile, 'w') as fpRevisionInfo:
        json.dump(jsonGitInfo, fpRevisionInfo, indent=2)


def diffRecursiveSubmodules(patchFilePrefix=''):
    diffFiles = []
    cmdEnv = dict(os.environ)

    # git log --format="%H" -n 2 -> get latest two commit id
    cmdPieces = ['git', 'log', '--format=%H', '-n', '2']
    ret = utils.popenReturnStdout(cmdPieces, cmdEnv)
    if ret['code'] == 0:
        commitIds = ret['lines']
        utils.heavyLogging('diffRecursiveSubmodules: commitIds {}'.format(commitIds))
        try:
            commitIds[0] = bytes.decode(commitIds[0], 'utf-8')
            commitIds[1] = bytes.decode(commitIds[1], 'utf-8')
            # TODO: recursive submodules meaningful?
            cmdPieces = ['git', 'diff', '--name-only', 'HEAD..{}'.format(commitIds[1])]
            stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
            idx = 0
            for line in stdout['lines']:
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                diffFiles.append(line.strip())
                if patchFilePrefix != '':
                    # gen diff
                    try:
                        #cmdPieces = ['git', 'diff', '{}..HEAD'.format(commitIds[1]), line]
                        #stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
                        cmdPieces = ['git', 'format-patch', '--ignore-cr-at-eol', '{}..HEAD'.format(commitIds[1]), line, '--stdout']
                        #cmdPieces = ['git', 'format-patch', '{}..HEAD'.format(commitIds[1]), line, '--stdout']
                        stdout = utils.popenReturnStdout(cmdPieces, cmdEnv, strip=False)
                        if stdout['code'] == 0:
                            fpPatch = open('{}-{}'.format(patchFilePrefix, idx), 'w')
                            for line in stdout['lines']:
                                try:
                                    fpPatch.write('{}'.format(bytes.decode(line, 'utf-8')))
                                except:
                                    fpPatch.write('{}'.format(line))
                            fpPatch.close()
                    except:
                        # exception, file removed maybe
                        utils.heavyLogging('diffRecursiveSubmodules: error {}({})'.format(line, commitIds[1]))
                        pass
                idx = idx + 1
        except sb.CalledProcessError as grepexc:
            utils.heavyLogging('diffRecursiveSubmodules: error {}'.format(grepexc.output))

    return diffFiles

def diffFiles(srcDir, outputFile, patchFilePrefix):
    pwd = os.getcwd()

    if srcDir != '':
        os.chdir(srcDir)
    lines = diffRecursiveSubmodules(patchFilePrefix)
    fpRevision = open(outputFile, 'w')
    for line in lines:
        fpRevision.write('{}\n'.format(line))
    fpRevision.close()

    os.chdir(pwd)

#def labelSubmodules(sourcePath):
#    pwd = os.getcwd()
#
#    if sourcePath != '':
#        os.chdir(sourcePath)
#    cmdEnv = dict(os.environ)
#    cmdPieces = ['git', 'config', '--file', '.gitmodules', '--get-regexp', 'path']
#    submodulesOutput = utils.popenReturnStdout(cmdPieces, cmdEnv)
#    submodules = submodulesOutput['lines']
#    utils.heavyLogging('labelSubmodules: submodules {}'.format(submodules))
#    for submodule in submodules:
#        submodule = bytes.decode(submodule, 'utf-8')
#        tokens = submodule.split()
#        if len(tokens) > 0:
#            submoduleDir = tokens[1]
#            utils.heavyLogging('labelSubmodules: enter {}'.format(submoduleDir))
#            os.chdir(submoduleDir)
#            cmdPieces = ['git', 'checkout', '-b', 'PFtest-branch']
#            utils.popenWithStdout(cmdPieces, cmdEnv)
#            os.chdir(sourcePath)
#    os.chdir(pwd)

def checkoutPrev(dir, workDir):
    cmdEnv = dict(os.environ)
    pwd = os.getcwd()

    utils.heavyLogging('checkoutPrev: enter {}'.format(dir))
    if dir != '':
        os.chdir(dir)
    cmdPieces = ['git', 'rev-parse', 'HEAD']
    stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
    currentCommit = bytes.decode(stdout['lines'][0], 'utf-8')
    cmdPieces = ['git', 'log', '--pretty=%P', '-n', '1', currentCommit]
    stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
    parentCommit = bytes.decode(stdout['lines'][0], 'utf-8')
    utils.heavyLogging('checkoutPrev: checkout commit {}'.format(parentCommit))

    cmdPieces = ['git', 'diff', parentCommit, currentCommit]
    stdoutDiff = utils.popenReturnStdout(cmdPieces, cmdEnv)

    cmdPieces = ['git', 'branch', '--list', 'prev-branch']
    stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
    if len(stdout['lines']) > 0:
        cmdPieces = ['git', 'branch', '-D', 'prev-branch']
        utils.popenWithStdout(cmdPieces, cmdEnv)
    cmdPieces = ['git', 'checkout', '-b', 'prev-branch', parentCommit]
    utils.popenWithStdout(cmdPieces, cmdEnv)

    os.chdir(pwd)

def checkoutGerritChangeParent(dir, workDir):
    if 'GERRIT_PROJECT' not in os.environ and 'GERRIT_PATCHSET_REVISION' not in os.environ:
        utils.heavyLogging('checkoutGerritChangeParent: invalid gerrit trigger')
        sys.exit(-1)

    # ssh -l mis190 -p 29418 pcgit1.rtkbf.com gerrit query --format=JSON commit:17594133ce2588332f8acb8db78f111dc64ba97d --dependencies
    cmdEnv = dict(os.environ)
    cmdPieces = ['ssh', '-p', os.getenv('GERRIT_PORT'), os.getenv('GERRIT_HOST'), \
                    'gerrit', 'query', '--format=JSON', 'commit:{}'.format(os.getenv('GERRIT_PATCHSET_REVISION')), '--dependencies']
    try:
        stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
        dependency = json.loads(stdout['lines'][0])
        utils.lightLogging('checkoutGerritChangeParent: dependency {}'.format(dependency))
        parentCommit = dependency['dependsOn'][0]['revision']
        checkoutRevision(dir, parentCommit)
    except Exception as e: 
        utils.heavyLogging('checkoutGerritChangeParent: gerrit query failure')
        print(e)
        sys.exit(-1)

def checkoutBranch(dir, workDir):
    cmdEnv = dict(os.environ)
    pwd = os.getcwd()

    utils.heavyLogging('checkoutBranch: enter {}'.format(dir))
    if dir != '':
        os.chdir(dir)
    cmdPieces = ['git', 'rev-parse', 'HEAD']
    stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
    currentCommit = bytes.decode(stdout['lines'][0], 'utf-8')
    utils.heavyLogging('checkoutBranch: find branch by commit{}'.format(currentCommit))
    cmdPieces = ['git', 'branch', '--format=\'%(refname:short)\'', '-r', '--contains', currentCommit]
    stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
    if len(stdout['lines']) == 0:
        # CURRENT_COMMIT not merged, cannot be found at remote
        # get last 10 parent commits
        cmdPieces = ['git', 'log', '--pretty=%P', '-n', '10', currentCommit]
        stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
        for line in stdout['lines']:
            utils.heavyLogging('checkoutBranch: find branch by parent commit {}'.format(line))
            cmdPieces = ['git', 'branch', '--format=\'%(refname:short)\'', '-r', '--contains', line]
            stdout = utils.popenReturnStdout(cmdPieces, cmdEnv)
            if len(stdout['lines']) > 0:
                remoteBranch = stdout['lines'][0]
                remoteBranch = remoteBranch[remoteBranch.index('/') + 1:]
                break
    else:
        remoteBranch = bytes.decode(stdout['lines'][0], 'utf-8')
        remoteBranch = remoteBranch[remoteBranch.index('/') + 1:]
    utils.heavyLogging('checkoutBranch: checkout to branch {}'.format(remoteBranch))
    cmdPieces = ['git', 'checkout', remoteBranch]
    utils.popenWithStdout(cmdPieces, cmdEnv)

    os.chdir(pwd)

def cherryPick(dir):
    cmdEnv = dict(os.environ)
    pwd = os.getcwd()

    utils.heavyLogging('cherryPick: enter {}'.format(dir))
    if dir != '':
        os.chdir(dir)
    cmdPieces = ['git', 'cherry-pick', 'FETCH_HEAD']
    utils.popenWithStdout(cmdPieces, cmdEnv)

    os.chdir(pwd)

def checkoutToCurrentRevison(dir):
    cmdEnv = dict(os.environ)
    pwd = os.getcwd()

    utils.heavyLogging('checkoutToCurrentRevison: enter {}'.format(dir))
    if dir != '':
        os.chdir(dir)
    cmdPieces = ['git', 'reset', '--hard']
    utils.popenWithStdout(cmdPieces, cmdEnv)
    # for gerrit triggered job, PFtest-branch would be labeled
    cmdPieces = ['git', 'checkout', 'PFtest-branch']
    ret = utils.popenWithStdout(cmdPieces, cmdEnv)
    if ret != 0:
        # for other cases
        revisionFile = os.path.join(os.getenv('WORKSPACE'), utils.getEnv('PF_SOURCE_WORKDIR'), '.pf-revision-info')
        if os.path.isfile(revisionFile):
            with open(revisionFile) as fpRevisionInfo:
                jsonRevisionInfo = json.load(fpRevisionInfo)
                for source in jsonRevisionInfo['sources']:
                    cmdPieces = ['git', 'checkout', source['revision']]
                    ret = utils.popenWithStdout(cmdPieces, cmdEnv)
                    break
    os.chdir(pwd)

def checkoutRevision(dir, revision):
    cmdEnv = dict(os.environ)
    pwd = os.getcwd()

    utils.heavyLogging('checkoutRevision: enter {}, checkout {}'.format(dir, revision))
    if dir != '':
        os.chdir(dir)
    cmdPieces = ['git', 'checkout', '-f', revision]
    utils.popenWithStdout(cmdPieces, cmdEnv)

    try:
        utils.heavyLogging('checkoutRevision: git_submodule_sync')
        cmdPieces = ['git', 'submodule', 'sync', '--recursive']
        utils.popenWithStdout(cmdPieces, cmdEnv)
        utils.heavyLogging('checkoutRevision: git_submodule_update')
        cmdPieces = ['git', 'submodule', 'update', '--init', '--recursive', '--force']
        utils.popenWithStdout(cmdPieces, cmdEnv)
    except:
        utils.heavyLogging('checkoutRevision: git submodule failure')
        pass

    # git clean to remove untracked files
    # untracked files results build error sometimes
    #cmdPieces = ['git', 'clean', '-ffdx']
    #utils.popenWithStdout(cmdPieces, cmdEnv)
    #try:
    #    utils.heavyLogging('checkoutRevision: git_submodule_clean')
    #    cmdPieces = ['git', 'submodule', 'foreach', '--recursive', 'git', 'clean', '-ffdx']
    #    utils.popenWithStdout(cmdPieces, cmdEnv)
    #except:
    #    utils.heavyLogging('checkoutRevision: git submodule clean failure')
    #    pass

    os.chdir(pwd)

def checkoutParent(sourcePath, workDir, mode):
    pwd = os.getcwd()

    if sourcePath != '':
        os.chdir(sourcePath)
    #cmdEnv = dict(os.environ)
    #cmdPieces = ['git', 'config', '--file', '.gitmodules', '--get-regexp', 'path']
    #submodulesOutput = utils.popenReturnStdout(cmdPieces, cmdEnv)
    os.chdir(pwd)
    if mode == 'prev':
        checkoutPrev(sourcePath, workDir)
    elif mode == 'parent':
        checkoutGerritChangeParent(sourcePath, workDir)
    elif mode == 'branch':
        checkoutBranch(sourcePath, workDir)
    elif mode == 'cherry-pick':
        cherryPick(sourcePath)
    else:
        # forward, back to PFtest-branch
        checkoutToCurrentRevison(sourcePath)
    os.chdir(pwd)

def checkOut(workDir, configFile):
    pwd = os.getcwd()

    with open(os.path.join(workDir, configFile), encoding='utf-8') as fpReport:
        gitConfig = json.load(fpReport)
    print(gitConfig, flush=True)
    if gitConfig['dst'] == '':
        gitConfig['dst'] = '.'
    else:
        os.makedirs(gitConfig['dst'], exist_ok=True)
        os.chdir(gitConfig['dst'])

    cmdEnv = dict(os.environ)
    cmdPieces = ['git', 'init']
    utils.popenWithStdout(cmdPieces, cmdEnv)
    cmdPieces = ['git', 'remote', 'add', 'origin', gitConfig['url']]
    utils.popenWithStdout(cmdPieces, cmdEnv)
    cmdPieces = ['git', 'fetch', 'origin', gitConfig['refspecs']]
    utils.popenWithStdout(cmdPieces, cmdEnv)
    cmdPieces = ['git', 'checkout', 'FETCH_HEAD']
    utils.popenWithStdout(cmdPieces, cmdEnv)

    os.chdir(pwd)