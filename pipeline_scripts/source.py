import os, getopt, sys, logging, json
import git, repo
import utils

def revisionInfo(configs, sourceIndex):
    sourceIndex = int(sourceIndex)
    utils.heavyLogging('revisionInfo: {}({})'.format(configs['scm_types'][sourceIndex], sourceIndex))
    if configs['scm_types'][sourceIndex] == 'git':
        git.revisionInfo(configs, sourceIndex)
    elif configs['scm_types'][sourceIndex] == 'repo':
        repo.revisionInfo(configs, sourceIndex)

def diffFiles(configs, sourceIndex):
    sourceIndex = int(sourceIndex)
    if 'GERRIT_EVENT_TYPE' in os.environ and (os.getenv('GERRIT_EVENT_TYPE') == 'patchset-created' or os.getenv('GERRIT_EVENT_TYPE') == 'comment-added'):
        utils.heavyLogging('diffFiles: {}({})'.format(configs['scm_types'][sourceIndex], sourceIndex))

        diffFile = os.path.join(configs['WORK_DIR'], '.pf-diff-files-{}'.format(sourceIndex))
        patchFilePrefix = os.path.join(configs['WORK_DIR'], '.pf-patches-{}'.format(sourceIndex))
        if 'WORKSPACE' in os.environ:
            diffFile = os.path.join(os.getenv('WORKSPACE'), diffFile)
            patchFilePrefix = os.path.join(os.getenv('WORKSPACE'), patchFilePrefix)
        if configs['scm_types'][sourceIndex] == 'git':
            git.diffFiles(configs['scm_dsts'][sourceIndex], diffFile, patchFilePrefix)
        elif configs['scm_types'][sourceIndex] == 'repo':
            repo.diffFiles(configs['scm_dsts'][sourceIndex], diffFile, patchFilePrefix, configs['WORK_DIR'])
        # export diff files to env.PF_SOURCE_DIFFS_{i}
        diffs = []
        fpDiffs = open(diffFile, 'r')
        while True:
            line = fpDiffs.readline()
            if not line:
                break
            diffs.append(line.strip())
        fpDiffs.close()
        utils.saveEnv(configs['WORK_DIR'], 'PF_GERRIT_PATCHSET_DIFF_FILES_{}'.format(sourceIndex), ','.join(diffs))

        hasSource = False
        extensionsToCheck = ['.c', '.cpp', '.java']
        fpDiff = open(diffFile, 'r')
        while True:
            line = fpDiff.readline()
            if not line:
                break
            if any(ext in line for ext in extensionsToCheck):
                hasSource = True
                break
        fpDiff.close()
        if hasSource == True:
            utils.saveEnv(configs['WORK_DIR'], 'PF_GERRIT_PATCHSET_WITH_SOURCECODE', 1)
        else:
            utils.saveEnv(configs['WORK_DIR'], 'PF_GERRIT_PATCHSET_WITH_SOURCECODE', 0)
    else:
        utils.heavyLogging('diffFiles: skip')

def saveEnv(configs):
    for i in range(len(configs['scm_dsts'])):
        utils.saveEnv(configs['WORK_DIR'], 'PF_SOURCE_TYPE_{}'.format(i), configs['scm_types'][i])
        utils.saveEnv(configs['WORK_DIR'], 'PF_SOURCE_DST_{}'.format(i), configs['scm_dsts'][i])

def parseConfig(configs):
    for i in range(configs['scm_counts']):
        if configs['scm_types'][i] == 'git':
            if configs['scm_branchs'][i] == '':
                if configs['scm_refspecs'][i] == '':
                    configs['scm_branchs'][i] = 'master'
                else:
                    configs['scm_branchs'][i] = 'FETCH_HEAD'
            gitConfigs = dict()
            gitConfigs['dst'] = configs['scm_dsts'][i]
            gitConfigs['preserve'] = os.getenv('PF_PRESERVE_SOURCE')
            gitConfigs['url'] = configs['scm_urls'][i]
            gitConfigs['branch'] = configs['scm_branchs'][i]
            gitConfigs['credentials'] = configs['scm_credentials'][i]
            if gitConfigs['credentials'] == '':
                if 'PF_GERRIT_CREDENTIALS' in os.environ:
                    gitConfigs['credentials'] = os.getenv('PF_GERRIT_CREDENTIALS')
            utils.saveEnv(configs['WORK_DIR'], 'PF_GERRIT_CREDENTIALS_MAIN', gitConfigs['credentials'])
            gitConfigs['refspecs'] = configs['scm_refspecs'][i]
            try:
                gitConfigs['honor_refspec'] = configs['scm_git_honor_refspec'][i]
            except:
                gitConfigs['honor_refspec'] = False
            try:
                gitConfigs['clone_reference'] = configs['scm_git_reference'][i]
            except:
                gitConfigs['clone_reference'] = ''
            try:
                gitConfigs['clone_depth'] = configs['scm_git_clone_depth'][i]
            except:
                gitConfigs['clone_depth'] = 0
            try:
                gitConfigs['submodules'] = configs['scm_git_submodules'][i]
            except:
                gitConfigs['submodules'] = False
            try:
                gitConfigs['recursivesubmodules'] = configs['scm_git_recursivesubmodules'][i]
            except:
                gitConfigs['recursivesubmodules'] = False
            with open(os.path.join(configs['WORK_DIR'], 'source-{}-config.json'.format(i)), 'w', encoding='utf-8') as fp:
                json.dump(gitConfigs, fp, indent=2)
        elif configs['scm_types'][i] == 'repo':
            if configs['scm_branchs'][i] == '':
                configs['scm_branchs'][i] = 'master'
            repoConfig = dict()
            repoConfig['repo_path'] = configs['repo_path']
            repoConfig['scm_credentials'] = configs['scm_credentials'][i]
            utils.saveEnv(configs['WORK_DIR'], 'PF_GERRIT_CREDENTIALS_MAIN', repoConfig['scm_credentials'])
            repoConfig['scm_repo_manifest_platforms'] = configs['scm_repo_manifest_platforms'][i]
            repoConfig['scm_branchs'] = configs['scm_branchs'][i]
            repoConfig['scm_repo_manifest_files'] = configs['scm_repo_manifest_files'][i]
            repoConfig['scm_urls'] = configs['scm_urls'][i]
            repoConfig['scm_repo_manifest_notags'] = configs['scm_repo_manifest_notags'][i]
            repoConfig['scm_repo_manifest_currentbranchs'] = configs['scm_repo_manifest_currentbranchs'][i]
            repoConfig['scm_repo_manifest_depths'] = configs['scm_repo_manifest_depths'][i]
            repoConfig['scm_dst'] = configs['scm_dsts'][i]
            repoConfig['preserve'] = os.getenv('PF_PRESERVE_SOURCE')
            try:
                repoConfig['scm_repo_manifest_groups'] = configs['scm_repo_manifest_groups'][i]
            except:
                repoConfig['scm_repo_manifest_groups'] = ''
            try:
                repoConfig['scm_repo_reference'] = configs['scm_repo_reference'][i]
            except:
                repoConfig['scm_repo_reference'] = ''
            try:
                repoConfig['scm_repo_mirror'] = configs['scm_repo_mirror'][i]
            except:
                repoConfig['scm_repo_mirror'] = ''
            with open(os.path.join(configs['WORK_DIR'], 'source-{}-config.json'.format(i)), 'w', encoding='utf-8') as fp:
                json.dump(repoConfig, fp, indent=2)
        elif configs['scm_types'][i] == 'svn':
            pass
        else:
            utils.heavyLogging('parseConfig: unknown type {}'.format(configs['scm_types'][i]))

def checkOut(configs, sourceIndex):
    configFile = 'source-{}-config.json'.format(sourceIndex)
    git.checkOut(configs['WORK_DIR'], configFile)

def main(argv):
    configFile = ''
    workDir = ''
    configs = dict()
    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:f:i:v', ["command=", "work_dir=", "config=", "index=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-i', '--index'):
            sourceIndex = value
        elif name in ('-w', '--work_dir'):
            workDir = value
        elif name in ('-c', '--command'):
            command = value
            
    if os.path.isdir(workDir) == False and workDir != '':
        os.makedirs(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'source.log'), level=logging.DEBUG, filemode='w')
    # step 1
    #     Load configurations
    #     Get coverity project name if necessary
    #     Generate .coverity.license.config
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir
    utils.checkLicense(os.path.dirname(sys.argv[0]), configs, 'source')
    if command == 'REVISION_INFO':
        revisionInfo(configs, sourceIndex)
    elif command == 'DIFF_FILES':
        diffFiles(configs, sourceIndex)
    elif command == 'TRANSLATE_CONFIG':
        utils.translateConfig(configFile)
    elif command == 'INIT_WORKDIR':
        utils.cleanAll(configs['WORK_DIR'])
    elif command == 'PARSE_CONFIG':
        parseConfig(configs)
    elif command == 'CHECK_OUT':
        checkOut(configs, sourceIndex)
    elif command == 'SAVE_ENV':
        saveEnv(configs)
    #elif os.name == 'posix' and command == 'KNOWN_HOSTS':
    #    knownHostsCheck(configs)

if __name__ == "__main__":
    main(sys.argv)