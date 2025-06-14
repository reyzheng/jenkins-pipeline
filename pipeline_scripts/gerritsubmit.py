import os, logging, json, getopt, sys, re
import subprocess as sb
from string import Template
import utils, git, coverityapi

def getSSHCommand():
    if 'GERRIT_USER' in os.environ:
        cmdPieces = ['ssh', '-l', os.getenv('GERRIT_USER'), '-i', os.getenv('GERRIT_KEY')]
    else:
        cmdPieces = ['ssh']
    return cmdPieces

def retrievePreviewReport(configs):
    pwd = os.getcwd()
    os.chdir(configs['coverity_build_root'])

    cids = []
    if os.path.isfile('preview_report_v2.json'):
        fpIssues = open('preview_report_v2.json', 'r')
        while True:
            # Get next line from file
            line = fpIssues.readline()
            # if line is empty
            # end of file is reached
            if not line:
                break
            elif line.strip().startswith('"cid" : '):
                tokens = line.split()
                if len(tokens) > 2:
                    cids.append(tokens[2][:-1])
        fpIssues.close()
    else:
        utils.heavyLogging('retrievePreviewReport: failure cov-analyze')

    os.chdir(pwd)
    return cids

def retrieveProjectInfo(configs, covuser, covkey, stream):
    utils.lightLogging('retrieveProjectInfo: stream, {}'.format(stream))
    # get coverity project
    output = os.path.join(configs['WORK_DIR'], 'covProjectInfo.json')
    try:
        #utils.heavyLogging("debug coverityapi 36 reviewed")
        coverityapi.queryCoverityStream(covuser, covkey, \
                                        'http://{}:{}'.format(configs["coverity_host"], configs["coverity_port"]), \
                                        stream, output)
    except Exception as e:
        print(e, flush=True)
        return ''
    if os.path.isfile(output):
        fpInfo = open(output)
        jsonInfo = json.load(fpInfo)
        fpInfo.close()
        if 'streams' in jsonInfo:
            utils.heavyLogging('retrieveProjectInfo: coverity project {}'.format(jsonInfo["streams"][0]["primaryProjectName"]))
            return jsonInfo["streams"][0]["primaryProjectName"]
        else:
            if 'message' in jsonInfo:
                utils.heavyLogging('retrieveProjectInfo: error {}'.format(jsonInfo['message']))
            sys.exit(-1)
    else:
        return ''

def deHTML(txt):
    CLEANR = re.compile('<.*?>')
    rets = []
    lines = txt.splitlines()
    for i in range(len(lines)):
        if lines[i].lstrip().startswith('<pre>'):
            lines[i] = lines[i].lstrip().replace('<pre>', '')
        elif lines[i].lstrip().startswith('</pre>'):
            continue
        elif lines[i].lstrip().startswith('<b>') or lines[i].lstrip().startswith('<td>'):
            lines[i] = '    **{}**'.format(re.sub(CLEANR, '', lines[i]).lstrip())
        elif lines[i].lstrip().startswith('<'):
            continue
        rets.append('{}\n'.format(lines[i]))
    return ''.join(rets)

def gptCommitMessageReview():
    cmdEnv = dict(os.environ)
    if 'PF_CODEPROMPT_FUNCTION' not in os.environ:
        utils.heavyLogging('gptCommitMessageReview: unknown PF_CODEPROMPT_FUNCTION')
        sys.exit(-1)
    # TODO: support gerrit submit in parallel build?
    if 'PF_CODEPROMPT_RESULT' in os.environ:
        import yaml
        comments = []
        results = utils.getCodetekPrompts(os.getenv('PF_CODEPROMPT_RESULT'))
        for resultFile in results:
            utils.heavyLogging('gptCommitMessageReview: parse {}'.format(resultFile))
            if os.getenv('PF_CODEPROMPT_FUNCTION') == 'git-commit-message-review' or os.getenv('PF_CODEPROMPT_FUNCTION') == 'git-commit-coverity-check':
                with open(resultFile, 'r') as fpInput:
                    resultYaml = yaml.safe_load(fpInput)
                with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-message-review-result.hbs'), 'r') as fpTemplate:
                    tComment = fpTemplate.read()
                with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-message-review-result-patch.hbs'), 'r') as fpTemplate:
                    tPatch = fpTemplate.read()

                summary = ''
                patches = []
                if os.getenv('PF_CODEPROMPT_FUNCTION') == 'git-commit-message-review':
                    summary = '- summary: {}'.format(resultYaml['commit_message']['summary'])
                    if 'patches' in resultYaml and resultYaml['patches']['refined_patches'] is not None:
                        for refinedPatch in resultYaml['patches']['refined_patches']:
                            if resultYaml['patches']['refined_patches'][refinedPatch].strip() == 'No changes needed.':
                                continue
                            patches.append(Template(tPatch).safe_substitute(FILE=refinedPatch, \
                                                                            PATCH=resultYaml['patches']['refined_patches'][refinedPatch]))
                    else:
                        # exception
                        pass
                else:
                    # git-commit-coverity-check
                    summaryList = []
                    for i in range(len(resultYaml['analysis']['introduce_new_defects'])):
                        summaryList.append('  {}. {}'.format(i + 1, resultYaml['analysis']['introduce_new_defects'][i]['description']))
                    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-message-review-result-summary.hbs'), 'r') as fpTemplate:
                        tSummary = fpTemplate.read()
                    summary = Template(tSummary).safe_substitute(SUMMARY_LIST='\n'.join(summaryList), \
                                                                NOTES=resultYaml['analysis']['notes'])
                    if 'final_patch' in resultYaml:
                        for patch in resultYaml['final_patch']:
                            patches.append(Template(tPatch).safe_substitute(FILE=patch['file'], \
                                                                            PATCH=patch['diff']))
                if len(patches) == 0:
                    patchesTxt = 'No changes needed.'
                else:
                    patchesTxt = ''.join(patches)

                buildURL = ''
                if 'BUILD_URL' in os.environ:
                    buildURL = os.getenv('BUILD_URL')
                commitMessage = ''
                if os.getenv('PF_CODEPROMPT_FUNCTION') == 'git-commit-message-review':
                    commitMessage = '- refined commit message: {}'.format(resultYaml['commit_message']['final_commit_message'].replace('"', '\''))
                comment = Template(tComment).safe_substitute(SUMMARY=summary, \
                                                                COMMIT_MESSAGE=commitMessage, \
                                                                PATCHES=patchesTxt.replace('"', '\''),
                                                                BUILD_URL=buildURL)
                comments.append(comment)
            elif os.getenv('PF_CODEPROMPT_FUNCTION') == 'coverity-analysis-advise-commit':
                import covhtmlparser
                resultYaml = covhtmlparser.coverityAnalysisAdviseParser(resultFile)
                with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'gerrit-comment-coverity-advise'), 'r') as fpTemplate:
                    tComment = fpTemplate.read()
                comment = Template(tComment).safe_substitute(FILE=resultYaml['filename'].replace('"', '\''), \
                                                                COVERITY_ANALYSIS_RESULT=deHTML(resultYaml['coverityAnalysis'].replace('"', '\'')), \
                                                                REALGPT_ADVISE=resultYaml['advise'].replace('"', '\''), \
                                                                COMMENT=resultYaml['reasoning'].replace('"', '\''))
                comments.append(comment)
        sshCmds = getSSHCommand()
        utils.heavyLogging("DEBUG {}".format('\n'.join(comments)))
        utils.popenWithStdout(sshCmds + ['-p', '29418', os.getenv('GERRIT_HOST'), 'gerrit', 'review', \
                                '-m', '"{}"'.format('\n'.join(comments)), \
                                '{},{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_PATCHSET_NUMBER'))], cmdEnv)
    else:
        utils.heavyLogging('gerritSubmit: PF_CODEPROMPT_RESULT not in os.environ:')
        sys.exit(1)

def gerritSubmit(configs):
    cmdEnv = dict(os.environ)
    hasParentAnalysis = False
    if configs['comment'] == 'COV_INFO':
        if 'BUILD_BRANCH' in os.environ:
            if 'BR{}_COVCOMP_NEW_DEFECTS'.format(os.getenv('BUILD_BRANCH')) in os.environ:
                hasParentAnalysis = True
                if os.getenv('BR{}_COVCOMP_NEW_DEFECTS'.format(os.getenv('BUILD_BRANCH'))) == 'PF_NONE':
                    cids = []
                else:
                    cids = os.getenv('BR{}_COVCOMP_NEW_DEFECTS'.format(os.getenv('BUILD_BRANCH')))
                    cids = cids.split(',')
                defectsCount = str(len(cids))
            else:
                defectsCount = os.getenv('BR{}_COV_COUNT'.format(os.getenv('BUILD_BRANCH')))
        else:
            if 'COVCOMP_NEW_DEFECTS' in os.environ:
                hasParentAnalysis = True
                if os.getenv('COVCOMP_NEW_DEFECTS') == 'PF_NONE':
                    cids = []
                else:
                    cids = os.getenv('COVCOMP_NEW_DEFECTS')
                    cids = cids.split(',')
                defectsCount = str(len(cids))
            else:
                defectsCount = os.getenv('COV_COUNT')
        if defectsCount is None:
            utils.heavyLogging('gerritSubmit: invalid defectsCount')
            sys.exit(-1)

        if defectsCount == '0':
            #cmd = "ssh -p 29418 $GERRIT_HOST gerrit review -m '\"Pass\"' $GERRIT_CHANGE_NUMBER,$GERRIT_PATCHSET_NUMBER"
            sshCmds = getSSHCommand()
            utils.popenReturnStdout(sshCmds + ['-p', '29418', os.getenv('GERRIT_HOST'), \
                                     'gerrit', 'review', '-m', 'Pass', \
                                     '{},{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_PATCHSET_NUMBER'))], cmdEnv)
        else:
            if "COV_AUTH_KEY" not in os.environ:
                sys.exit("Environment variable COV_AUTH_KEY not defined")
            with open(os.getenv('COV_AUTH_KEY')) as f:
                keyObj = json.load(f)
            if 'BUILD_BRANCH' in os.environ:
                stream = os.getenv('BR{}_COV_STREAM'.format(os.getenv('BUILD_BRANCH')))
            else:
                stream = os.getenv('COV_STREAM')
            # python gerritsubmit.py -c COV_INFO -s $SNAPSHOT_ID
            covProject = retrieveProjectInfo(configs, keyObj['username'], keyObj['key'], stream)

            if hasParentAnalysis == True:
                # cids got from os.getenv('COVCOMP_NEW_DEFECTS')
                utils.heavyLogging('gerritSubmit: hasParentAnalysis, cids {}'.format(cids))
                pass
            else:
                cids = retrievePreviewReport(configs)
                utils.heavyLogging('gerritSubmit: cids {}'.format(cids))

            covInfo = dict()
            if len(cids) == 0:
                covInfo["message"] = "Pass"
            else:
                if covProject == '' or len(cids) > 30 :
                    covInfo["message"] = "Total defects: {}, CIDs: {}, http://{}:{}".format(len(cids), ','.join(cids), configs["coverity_host"], configs["coverity_port"])
                else:
                    covInfo["message"] = "Total defects: {}, CIDs: {}\n".format(len(cids), ','.join(cids))
                    for cid in cids:
                        covInfo["message"] += "http://{}:{}/query/defects.htm?project={}&cid={}\n".format(configs["coverity_host"], configs["coverity_port"], covProject, cid)
            with open(os.path.join(configs['WORK_DIR'], '.covinfo'), "w") as fp:
                json.dump(covInfo, fp)

            utils.heavyLogging('gerritSubmit: cat {}({})'.format(os.path.join(configs['WORK_DIR'], '.covinfo'), os.getcwd()))
            if os.name == 'posix':
                catProcess = sb.Popen(['cat', os.path.join(configs['WORK_DIR'], '.covinfo')], stdout=sb.PIPE)
            else:
                # shell=True for RTK windows agent
                catProcess = sb.Popen(['type', os.path.join(configs['WORK_DIR'], '.covinfo')], shell=True, stdout=sb.PIPE)
            sshCmds = getSSHCommand()
            sshProcess = sb.Popen(sshCmds + ['-p', '29418', os.getenv('GERRIT_HOST'), 'gerrit', 'review', \
                                    '-j', '{},{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_PATCHSET_NUMBER'))], \
                                    stdin=catProcess.stdout, stdout=sb.PIPE)
            catProcess.stdout.close() # enable write error in dd if ssh dies
            out, err = sshProcess.communicate()
            if sshProcess.returncode != 0:
                sys.exit(sshProcess.returncode)
    elif configs['comment'] == 'GPT_COMMIT_MESSAGE_REVIEW':
        gptCommitMessageReview()
    elif configs['comment'] == 'GPT_UPLOAD_PATCH':
        if 'PF_CODEPROMPT_FUNCTION' not in os.environ:
            utils.heavyLogging('gerritSubmit: unknown PF_CODEPROMPT_FUNCTION')
            sys.exit(-1)
        if 'PF_CODEPROMPT_RESULT' in os.environ:
            inputFiles = utils.getCodetekPrompts(os.getenv('PF_CODEPROMPT_RESULT'))
            hasToCommit = False
            comments = []
            idx = 1
            if 'PF_SOURCE_DST_0' in os.environ:
                sourceDir = os.getenv('PF_SOURCE_DST_0')
            else:
                sourceDir = os.getenv('WORKSPACE')
            for inputFile in inputFiles:
                import yaml
                with open(inputFile, 'r') as fpInput:
                    commentYaml = yaml.safe_load(fpInput)
                utils.heavyLogging('gerritSubmit: parse input {}'.format(inputFile))
                if os.getenv('PF_CODEPROMPT_FUNCTION') == 'git-commit-coverity-check-indiv':
                    if 'exception' in commentYaml:
                        comments.append('{}. {}: {}'.format(idx, commentYaml['corrected_file']['file'], commentYaml['exception']))
                        utils.heavyLogging('gerritSubmit: GPT_UPLOAD_PATCH - {}, exception'.format(commentYaml['corrected_file']['file']))
                    else:
                        if 'corrected_file' in commentYaml:
                            mainKey = 'corrected_file'
                            identifierKey = 'file'
                            blockKey = 'content'
                        else:
                            mainKey = 'corrected_function'
                            identifierKey = 'function'
                            blockKey = 'content'
                        patchContent = commentYaml[mainKey][blockKey]
                        lines = patchContent.splitlines()
                        linesCounts = len(lines)
                        if linesCounts <=3 and 'No changes necessary' in patchContent:
                            utils.heavyLogging('gerritSubmit: GPT_UPLOAD_PATCH - {}, {}'.format(commentYaml['corrected_file']['file'], patchContent))
                        else:
                            if 'corrected_file' in commentYaml:
                                # whole file replace
                                fileToPatch = os.path.join(sourceDir, commentYaml[mainKey][identifierKey])
                                patchFile = os.path.join(os.getenv('WORKSPACE'), configs['WORK_DIR'], 'full.patch')
                                fpPatch = open(patchFile, 'w')
                                fpPatch.write(patchContent)
                                fpPatch.close()
                                utils.heavyLogging('gerritSubmit: GPT_UPLOAD_PATCH - fileToPatch({}), patchFile({})'.format(fileToPatch, patchFile))
                                #comment = 'Refined comment by GPT: {}'.format(commentYaml['final_patch'])
                                git.updateFile(fileToPatch, patchFile)
                                comments.append('{}. {}: {}'.format(idx, commentYaml[mainKey][identifierKey], commentYaml['analysis']['notes']))
                            else:
                                # function replace
                                fileToPatch = os.path.join(sourceDir, commentYaml[mainKey]['file'])
                                patchFile = os.path.join(os.getenv('WORKSPACE'), configs['WORK_DIR'], 'function.patch')
                                fpPatch = open(patchFile, 'w')
                                fpPatch.write(patchContent)
                                fpPatch.close()
                                git.updateFunction(fileToPatch, patchFile, commentYaml[mainKey][identifierKey])
                                comments.append('{}. {}({}): {}'.format(idx, commentYaml[mainKey]['file'], commentYaml[mainKey][identifierKey], \
                                                                            commentYaml['analysis']['notes']))
                            hasToCommit = True
                idx = idx + 1
            if hasToCommit == True:
                # get current Change-ID
                #commitMessage = git.gerritQueryCommitComments(configs['WORK_DIR'])
                #lines = commitMessage.splitlines()
                #utils.heavyLogging('lines {}'.format(lines))
                #changeId = ''
                #for line in lines:
                #    if line.startswith('Change-Id:'):
                #        changeId = line
                #        break
                #utils.heavyLogging('changeId {}'.format(changeId))
                patchUrl = git.commitReview(sourceDir, 'RealGPT review:\n{}'.format('\n'.join(comments)))
                comment = 'Refined patch by GPT: {}'.format(patchUrl)
                sshCmds = getSSHCommand()
                utils.popenWithStdout(sshCmds + ['-p', '29418', os.getenv('GERRIT_HOST'), 'gerrit', 'review', \
                                        '-m', '"{}"'.format(comment), \
                                        '{},{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_PATCHSET_NUMBER'))], cmdEnv)
        else:
            utils.heavyLogging('gerritSubmit: PF_CODEPROMPT_RESULT not in os.environ:')
            sys.exit(1)
    else:
        # user defined comments
        sshCmds = getSSHCommand()
        utils.popenWithStdout(sshCmds + ['-p', '29418', os.getenv('GERRIT_HOST'), 'gerrit', 'review', \
                                '-m', '"{}"'.format(configs['comment']), \
                                '{},{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_PATCHSET_NUMBER'))], cmdEnv)

def main(argv):
    workDir = ''
    try:
        opts, args = getopt.getopt(argv[1:], 'w:f:c:v', ["work_dir=", "config=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            workDir = value
    
    utils.makeEmptyDirectory(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'gerritsubmit.log'), level=logging.DEBUG, filemode='w')
    utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir

    if os.path.exists('.pf-coverity.json'):
        fpCoverityConfig = open('.pf-coverity.json')
        coverityConfig = json.load(fpCoverityConfig)
        configs['coverity_build_root'] = coverityConfig['coverity_build_root']
        configs['coverity_host'] = coverityConfig['coverity_host']
        configs['coverity_port'] = coverityConfig['coverity_port']
        fpCoverityConfig.close()

    if configs['enable'] == False:
        print('main: skip')
        sys.exit(0)
    if 'GERRIT_HOST' not in os.environ:
        print('main: invalid gerrit event')
        sys.exit(0)
    gerritSubmit(configs)

if __name__ == "__main__":
    main(sys.argv)