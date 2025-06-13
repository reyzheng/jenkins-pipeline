import sys, getopt
import os, logging
import utils

def gitPureSync(configs):
    cmdEnv = dict(os.environ)

    utils.heavyLogging('gitPureSync: branches {}'.format(configs['branches']))
    utils.heavyLogging('gitPureSync: include tags {}'.format(configs['include_tags']))
    dst = 'ssh://{}:29418/{}'.format(configs['dst_remote'], configs['dst_project'])
    cmdGit = ['git', 'remote', 'add', 'protect', dst]
    utils.popenWithStdout(cmdGit, cmdEnv)
    if len(configs['branches']) == 0 or configs['branches'][0] == '':
        cmdGit = ['git', 'push', '--prune', 'protect', 'refs/remotes/origin/*:refs/heads/*']
        utils.popenWithStdout(cmdGit, cmdEnv)
        if configs["include_tags"] == True:
            cmdGit = ['git', 'push', '--tags', '--prune', 'protect']
            utils.popenWithStdout(cmdGit, cmdEnv)
    else:
        for branch in configs['branches']:
            #cmdGit = ['git', 'checkout', '-f', branch]
            #utils.popenWithStdout(cmdGit, cmdEnv)
            #cmdGit = ['git', 'push', 'protect', branch]
            #utils.popenWithStdout(cmdGit, cmdEnv)
            cmdGit = ['git', 'push', '--prune', 'protect', 'refs/remotes/origin/{}:refs/heads/{}'.format(branch, branch)]
            utils.popenWithStdout(cmdGit, cmdEnv)

    cmdGit = ['git', 'remote', 'remove', 'protect']
    utils.popenWithStdout(cmdGit, cmdEnv)

def gitBranchSync(configs):
    cmdEnv = dict(os.environ)
    branches = []

    if len(configs['branches']) == 0 or configs['branches'][0] == '':
        cmdGit = ['git', 'branch', '-r']
        ret = utils.popenReturnStdout(cmdGit, cmdEnv)
        if ret['code'] == 0:
            for line in ret['lines']:
                line = bytes.decode(line, 'utf-8').strip()
                # remove prefix ending in "/"
                if 'HEAD' in line or line == '':
                    utils.heavyLogging('gitBranchSync: skip HEAD')
                    continue
                line = line[line.index('/') + 1:]
                branches.append(line)
    else:
        for branch in configs['branches']:
            branches.append(branch)

    cmdGit = ['ssh', '-p', '29418', configs['dst_remote'], 'gerrit', 'ls-project']
    ret = utils.popenReturnStdout(cmdGit, cmdEnv)
    existedProjects = ret['lines']
    for branch in branches:
        dst = 'ssh://{}:29418/{}'.format(configs['dst_remote'], branch)
        cmdGit = ['git', 'remote', 'add', 'protect', dst]
        utils.popenWithStdout(cmdGit, cmdEnv)
        cmdGit = ['git', 'checkout', branch]
        utils.popenWithStdout(cmdGit, cmdEnv)
        cmdGit = ['git', 'pull', 'origin', branch]
        utils.popenWithStdout(cmdGit, cmdEnv)

        if branch not in existedProjects:
            utils.heavyLogging('gitBranchSync: create project {}'.format(branch))
            cmdGit = ['ssh', '-p', '29418', configs['dst_remote'], 'gerrit', 'create-project', branch]
            utils.popenWithStdout(cmdGit, cmdEnv)

        if configs['squash_commits'] == True:
            # trick, squash all commits
            cmdGit = ['git', 'checkout', '--orphan', 'init-{}'.format(branch), branch]
            utils.popenWithStdout(cmdGit, cmdEnv)
            cmdGit = ['git', 'commit', '-m', 'initial commit']
            utils.popenWithStdout(cmdGit, cmdEnv)
            cmdGit = ['git', 'push', '-u', 'protect', 'init-{}:master'.format(branch)]
            utils.popenWithStdout(cmdGit, cmdEnv)
        else:
            cmdGit = ['git', 'push', '-u', 'protect', '{}:master'.format(branch)]
            utils.popenWithStdout(cmdGit, cmdEnv)

        cmdGit = ['git', 'remote', 'remove', 'protect']
        utils.popenWithStdout(cmdGit, cmdEnv)

def gitSync(configs):
    pwd = os.getcwd()
    pfSourceDst = utils.getEnv('PF_SOURCE_DST_0')
    if pfSourceDst != '':
        os.chdir(pfSourceDst)
    if configs['sync_mode'] == 'pure':
        gitPureSync(configs)
    else:
        gitBranchSync(configs)
    os.chdir(pwd)

def main(argv):
    workDir = ''
    configFile = ''
    skipTranslate = False
    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:f:vs', ["command=", "work_dir=", "config=", "version", "skip_translate"])
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
        elif name in ('-c', '--command'):
            command = value

    logging.basicConfig(filename=os.path.join(workDir, '{}.log'.format(os.path.basename(__file__))), \
                            format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    if skipTranslate == False:
        utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)

    if configs['enable'] == False:
        utils.heavyLogging('Stage {} cancelled manually'.format(configs['stageName']))
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    gitSync(configs)

if __name__ == '__main__':
    main(sys.argv)