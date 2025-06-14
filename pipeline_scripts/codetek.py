import sys, getopt, os, glob, logging, json, re, zipfile
from string import Template
import utils, git

MAX_INTPUT_LINES=200

def loadCodeAnalysisRules(configs):
    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'code-analysis-rules'), 'r') as fpTemplate:
        tRules = fpTemplate.read()
    if 'CODING_STYLE_TAB_4SPACE' in configs['customization']:
        tRules = tRules + '\n  - **Coding style issues:** Replace all **tab characters with 4 spaces** for consistency.'
    return tRules

def checkUserDefinedOutputFormat(configs, subFunction=None):
    prefix = configs['function']
    if subFunction is not None:
        prefix = '{}_{}'.format(prefix, subFunction)
    if os.path.isfile(os.path.join(os.getenv('PF_ROOT'), 'scripts', '{}-output.hbs'.format(prefix))):
        utils.heavyLogging('checkUserDefinedOutputFormat: take users output format prompt')
        with open(os.path.join(os.getenv('PF_ROOT'), 'scripts', '{}-output.hbs'.format(prefix)), 'r') as fpOutputFormat:
            tOutputFormat = fpOutputFormat.read()
    else:
        utils.heavyLogging('checkUserDefinedOutputFormat: general output format prompt')
        with open(os.path.join(os.getenv('PF_ROOT'), 'templates', '{}-output.hbs'.format(prefix)), 'r') as fpOutputFormat:
            tOutputFormat = fpOutputFormat.read()
    return tOutputFormat

def gitCommitMessageReview(configs):
    ret = dict()
    commitMessage = git.gerritQueryCommitComments(configs['WORK_DIR'])
    utils.heavyLogging('gitCommitMessageReview: commitMessage, {}'.format(commitMessage))
    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-message-review.hbs'), 'r') as fpTemplate:
        t = fpTemplate.read()
    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'gerrit-patch.hbs'), 'r') as fpTemplate:
        tPatch = fpTemplate.read()
    tOutputFormat = checkUserDefinedOutputFormat(configs)

    allPatches = []
    for diffFile in glob.glob(os.path.join(utils.getEnv('PF_SOURCE_WORKDIR'), '.pf-patches-0-*')):
        utils.heavyLogging('gitCommitMessageReview: diffFile, {}'.format(diffFile))
        filePaths = extractFilenamesFromPatch(diffFile)
        if len(filePaths) == 0:
            utils.heavyLogging('gitCommitMessageReview: skip patch {}'.format(diffFile))
            continue
        with open(diffFile, 'r') as file:
            data = file.read()
            if 'GIT binary patch' in data:
                utils.heavyLogging('gitCommitMessageReview: skip binary {}'.format(diffFile))
            else:
                allPatches.append(Template(tPatch).safe_substitute(file_path=filePaths[0], patch_content=data))
    #utils.heavyLogging('gitCommitMessageReview: allPatches, {}'.format(allPatches))
    tRules = loadCodeAnalysisRules(configs)
    #utils.lightLogging('gitCommitMessageReview: hash {}'.format(commitMessage.strip()))
    ret['commitMessageHash'] = hash(commitMessage.strip())
    ret['count'] = 1
    ret['prompts'] = []
    ret['prompts'].append(Template(t).safe_substitute(patches=('').join(allPatches), \
                                                        commit_message=commitMessage, \
                                                        CODE_ANALYSIS_RULES=tRules,
                                                        GPT_OUTPUT_FORMAT=tOutputFormat))
    return ret

def parsePatch(file_path):
    """
    Parse a Git patch file to extract line numbers for additions and deletions.

    Args:
        file_path (str): Path to the patch file.

    Returns:
        dict: A dictionary with added and removed line numbers.
    """
    addedLines = []
    # Regular expression to match hunk headers (e.g., @@ -10,5 +20,7 @@)
    hunk_regex = re.compile(r'^@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@')
    with open(file_path, 'r') as patch_file:
        for line in patch_file:
            # Check for hunk header
            hunk_match = hunk_regex.match(line)
            if hunk_match:
                # hunk_match.group(1) -> line number before path applied
                addedLines.append(int(hunk_match.group(1)))

    return addedLines

def extractFilenamesFromPatch(file_path):
    """
    Extracts filenames from a Git patch file.

    Args:
        file_path (str): Path to the patch file.

    Returns:
        dict: A dictionary containing old and new filenames.
    """
    filenames = []

    # Regular expression to match diff lines (e.g., diff --git a/file.txt b/file.txt)
    diff_regex = re.compile(r'^diff --git a/(.+?) b/(.+)$')

    with open(file_path, 'r') as patch_file:
        for line in patch_file:
            match = diff_regex.match(line)
            if match:
                filenames.append(match.group(1))

    return filenames

# from ChatGPT
def isFileAddOperation(patch_file_path):
    """
    Detects newly added files in a Git patch, including binary files.

    Args:
        patch_file_path (str): Path to the Git patch file.

    Returns:
        list: List of newly added filenames.
    """
    added_files = set()

    # Regex patterns
    diff_regex = re.compile(r'^diff --git a/(.*?) b/(.*?)$')
    new_file_mode_regex = re.compile(r'^new file mode')
    old_file_devnull_regex = re.compile(r'^--- /dev/null')
    binary_diff_regex = re.compile(r'^Binary files /dev/null and b/(.+) differ$')
    git_binary_patch_regex = re.compile(r'^GIT binary patch$')

    current_file = None
    is_new_file = False

    with open(patch_file_path, 'r', encoding='utf-8', errors='ignore') as patch_file:
        for line in patch_file:
            line = line.rstrip()

            # Detect binary diff
            binary_match = binary_diff_regex.match(line)
            if binary_match:
                added_files.add('PF_BINARY')
                continue

            # Detect start of a new file diff block
            diff_match = diff_regex.match(line)
            if diff_match:
                current_file = diff_match.group(2)
                is_new_file = False
                continue

            # Detect a new file being added
            if new_file_mode_regex.match(line):
                is_new_file = True
                continue

            if is_new_file and current_file:
                if old_file_devnull_regex.match(line):
                    added_files.add(current_file)
                elif git_binary_patch_regex.match(line):
                    added_files.add('PF_BINARY')

    return list(added_files)

def extractFile(filepath, block=None, identifier=None, displaylineNumber=True):
    import parser
    idx = 1
    ret = dict()
    ret['content'] = ''
    if identifier is not None:
        functions = parser.getSourceFileMap('', filepath)
        for function in functions:
            if function['identifier'] == identifier:
                block = parser.Point(function['start_point'][0] + 1, function['end_point'][0] + 1)
                break
    if block is not None:
        start = block.x
        end = block.y
        with open(filepath, 'r', encoding='utf-8') as file:
            # Read each line in the file
            for line in file:
                if idx >= start and idx <= end:
                    # idx: line number
                    if displaylineNumber == True:
                        ret['content'] = ret['content'] + '{}\t{}'.format(idx, line)
                    else:
                        ret['content'] = ret['content'] + '{}'.format(line)
                    if idx == end:
                        break
                idx = idx + 1

    return ret

def checkoutBeforePatchApplied(sourceDir, pwd):
    if sourceDir != '':
        os.chdir(sourceDir)
    # checkout to the revision before patch applied
    cmds = ['git', 'reset', '--hard', 'HEAD~1']
    utils.popenWithStdout(cmds, dict(os.environ))
    cmds = ['git', 'status']
    utils.popenWithStdout(cmds, dict(os.environ))
    os.chdir(pwd)

def checkoutPatchApplied(sourceDir, pwd, currentRevision):
    # back to the state "patch applied"
    if sourceDir != '':
        os.chdir(sourceDir)
    cmds = ['git', 'reset', '--hard', currentRevision]
    utils.popenWithStdout(cmds, dict(os.environ))
    cmds = ['git', 'status']
    utils.popenWithStdout(cmds, dict(os.environ))
    os.chdir(pwd)

def extractFunctionParts(patch, sourceDir, lineNumber):
    ret = dict()
    ret['identifiers'] = []
    ret['contents'] = []
    dupLines = []
    if 'blocks' in patch:
        for i in range(len(patch['blocks'])):
            p = patch['blocks'][i]
            utils.heavyLogging("extractFunctionParts: {},{}".format(p.x, p.y))
            if p.x not in dupLines:
                function = extractFile(os.path.join(sourceDir, patch['file']), block=p, displaylineNumber=lineNumber)
                #ret['identifiers'].append(function['identifier'])
                ret['contents'].append(function['content'])
                dupLines.append(p.x)

    return ret

def getPatchInfo(sourceDir, domination):
    import parser
    allPatches = []
    for diffFile in glob.glob(os.path.join(utils.getEnv('PF_SOURCE_WORKDIR'), '.pf-patches-0-*')):
        utils.heavyLogging('gitPatchCoverityCheck: diffFile, {}'.format(diffFile))
        addFiles = isFileAddOperation(diffFile)
        if len(addFiles) > 0:
            if addFiles[0] == 'PF_BINARY':
                # skip binary file add
                pass
            else:
                patch = dict()
                patch['mode'] = 'whole'
                patch['file'] = addFiles[0]
                patch['patch'] = diffFile
                allPatches.append(patch)
        else:
            diffFiles = extractFilenamesFromPatch(diffFile)
            if len(diffFiles) == 0:
                utils.heavyLogging('getPatchInfo: skip patch {}'.format(diffFile))
                continue
            patchLines = parsePatch(diffFile)
            utils.heavyLogging('gitPatchCoverityCheck: patchLines, {}'.format(patchLines))
            functions = parser.getSourceFileMap(sourceDir, diffFiles[0])
            if domination == 'patch':
                patch = dict()
                patch['mode'] = 'general'
                patch['file'] = diffFiles[0]
                patch['patch'] = diffFile
                patch['blocks'] = []
                # dominate by patch file, one patch file on entry in allPatches
                for line in patchLines:
                    for function in functions:
                        utils.lightLogging('gitPatchCoverityCheck: function, {}'.format(function))
                        if line >= function['start_point'][0] + 1 and line <= function['end_point'][0] + 1:
                                p = parser.Point(function['start_point'][0] + 1, function['end_point'][0] + 1)
                                utils.heavyLogging('gitPatchCoverityCheck: p, {}'.format(p))
                                patch['blocks'].append(p)
                allPatches.append(patch)
            elif domination == 'function':
                # dominate by function, for "git-commit-coverity-check-indiv" with smaller input
                for function in functions:
                    p = None
                    for line in patchLines:
                        if line >= function['start_point'][0] + 1 and line <= function['end_point'][0] + 1:
                            p = parser.Point(function['start_point'][0] + 1, function['end_point'][0] + 1)
                            #identifier_start = parser.Point(function['identifier_start_point'][0] + 1, function['identifier_start_point'][1])
                            #identifier_end = parser.Point(function['identifier_end_point'][0] + 1, function['identifier_end_point'][1])
                            break
                    if p is not None:
                        patch = dict()
                        patch['mode'] = 'general'
                        patch['file'] = diffFiles[0]
                        patch['patch'] = diffFile
                        patch['identifier'] = function['identifier']
                        #patch['blocks'] = [p]
                        #patch['function_identifiers_start'] = [identifier_start]
                        #patch['function_identifiers_end'] = [identifier_end]
                        allPatches.append(patch)
    for allPatch in allPatches:
        utils.heavyLogging('gitPatchCoverityCheck: allPatch mode, {}'.format(allPatch['mode']))
        utils.heavyLogging('gitPatchCoverityCheck: allPatch file, {}'.format(allPatch['file']))
        if 'identifier' in allPatch:
            utils.heavyLogging('gitPatchCoverityCheck: allPatch identifier, {}'.format(allPatch['identifier']))
        if 'blocks' in allPatch:
            for block in allPatch['blocks']:
                utils.heavyLogging('gitPatchCoverityCheck: allPatch block, {}/{}'.format(block.x, block.y))
    return allPatches

def gitPatchCoverityCheck(configs):
    import parser
    ret = dict()
    ret['prompts'] = []
    pwd = os.getcwd()
    if 'PF_SOURCE_DST_0' in os.environ:
        sourceDir = os.getenv('PF_SOURCE_DST_0')
    else:
        # WORKSPACE
        sourceDir = ''
    utils.heavyLogging('gitPatchCoverityCheck: sourceDir {}'.format(sourceDir))

    currentRevision = git.getRevision(sourceDir)
    if configs['function'] == 'git-commit-coverity-check':
        checkoutBeforePatchApplied(sourceDir, pwd)
        allPatches = getPatchInfo(sourceDir, 'patch')
        with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-coverity-check-PATCH'), 'r') as fpTemplate:
            tPATCH = fpTemplate.read()
        patchTemplates = ''
        for allPatch in allPatches:
            with open(allPatch['patch'], 'r') as fpPatch:
                patchContent = fpPatch.read()
            functions = extractFunctionParts(allPatch, sourceDir, True)
            functionContent = ''.join(functions['contents'])
            # general patch + function -> accept
            # general patch + non-function -> reject
            # added(whole) patch -> accept
            if functionContent == '' and allPatch['mode'] != 'whole':
                # reject general patch + non-function
                pass
            else:
                patchTemplates = patchTemplates + Template(tPATCH).safe_substitute(
                                                    file_path=allPatch['file'], \
                                                    function=functionContent, \
                                                    patch=patchContent)
        if patchTemplates == '':
            ret['count'] = 0
            ret['prompts'] = []
        else:
            with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-coverity-check.hbs'), 'r') as fpTemplate:
                t = fpTemplate.read()
            tRules = loadCodeAnalysisRules(configs)
            tOutputFormat = checkUserDefinedOutputFormat(configs)
            ret['count'] = 1
            ret['prompts'].append(Template(t).safe_substitute(PATCHES=patchTemplates, \
                                                                GPT_OUTPUT_FORMAT=tOutputFormat, \
                                                                CODE_ANALYSIS_RULES=tRules))
        # back to the state "patch applied"
        checkoutPatchApplied(sourceDir, pwd, currentRevision)
    elif configs['function'] == 'git-commit-coverity-check-indiv':
        checkoutBeforePatchApplied(sourceDir, pwd)
        allPatches = getPatchInfo(sourceDir, 'function')
        checkoutPatchApplied(sourceDir, pwd, currentRevision)
        ret['count'] = 0
        ret['files'] = []
        tRules = loadCodeAnalysisRules(configs)
        # to avoid duplicate file, function check
        filesReviewed = []
        functionsReviewed = []
        for allPatch in allPatches:
            if sourceDir != '':
                os.chdir(sourceDir)
            numLines = sum(1 for _ in open(allPatch['file']))
            os.chdir(pwd)
            if numLines > MAX_INTPUT_LINES:
                # to the state "patch not applied"
                if allPatch['mode'] == 'whole':
                    utils.heavyLogging('gitPatchCoverityCheck: skip large file(file add) review')
                    continue
                key = '{}-{}'.format(allPatch['file'], allPatch['identifier'])
                if key in functionsReviewed:
                    continue
                else:
                    functionsReviewed.append(key)
                functions = dict()
                functions['files'] = []
                functions['identifiers'] = []
                functions['contents'] = []
                functions['files'].append(allPatch['file'])
                functions['identifiers'].append(allPatch['identifier'])
                identifierBlock = extractFile(os.path.join(sourceDir, allPatch['file']), identifier=allPatch['identifier'], displaylineNumber=False)
                functions['contents'].append(''.join(identifierBlock['content']))
            else:
                if allPatch['file'] in filesReviewed:
                    continue
                else:
                    filesReviewed.append(allPatch['file'])
                # back to the state "patch applied"
                checkoutPatchApplied(sourceDir, pwd, currentRevision)
                functions = extractFile(os.path.join(sourceDir, allPatch['file']), block=parser.Point(0, 9999), displaylineNumber=False)
                fileContent = ''.join(functions['content'])

            if allPatch['mode'] == 'whole' or numLines > MAX_INTPUT_LINES:
                patchContent = ''
            else:
                with open(allPatch['patch'], 'r') as fpPatch:
                    patchContent = fpPatch.read()

            ret['count'] = ret['count'] + 1
            if numLines > MAX_INTPUT_LINES:
                with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-coverity-check-indiv_function.hbs'), 'r') as fpTemplate:
                    t = fpTemplate.read()
                tOutputFormat = checkUserDefinedOutputFormat(configs, subFunction='function')
                ret['files'].append(allPatch['file'])
                ret['prompts'].append(Template(t).safe_substitute(file_path=allPatch['file'], \
                                                                    file_name=functions['files'][0], \
                                                                    function_name=functions['identifiers'][0], \
                                                                    function_content=functions['contents'][0], \
                                                                    CODE_ANALYSIS_RULES=tRules, \
                                                                    GPT_OUTPUT_FORMAT=tOutputFormat))
            else:
                with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'git-commit-coverity-check-indiv.hbs'), 'r') as fpTemplate:
                    t = fpTemplate.read()
                tOutputFormat = checkUserDefinedOutputFormat(configs)
                ret['files'].append(allPatch['file'])
                ret['prompts'].append(Template(t).safe_substitute(file_path=allPatch['file'], \
                                                                        file_content=fileContent, \
                                                                        patch=patchContent, \
                                                                        CODE_ANALYSIS_RULES=tRules, \
                                                                        GPT_OUTPUT_FORMAT=tOutputFormat))

    return ret

def reIndent(input):
    lines = input.splitlines()
    ret = []
    startIndent = False
    for line in lines:
        if line.strip() == '':
            # skip empty line
            pass
        elif startIndent == True and line.startswith(' ') == False:
            utils.heavyLogging('reIndent: {}'.format(line))
            line = '    {}'.format(line)
        ret.append(line)
        if line.rstrip() == '  content: |':
            startIndent = True
    return '\n'.join(ret)

def getSourceFiles():
    if 'PF_GERRIT_PATCHSET_DIFF_FILES_0' in os.environ:
        files = os.getenv('PF_GERRIT_PATCHSET_DIFF_FILES_0').split(',')
    else:
        files = git.getSourceFiles(os.getenv('PF_SOURCE_DST_0'))
    return files

#def retrieveEvents(issue):
#    events = []
#    if issue['events'] is not None:
#        for event in issue['events']:
#            events.append(event)
#            events.extend(retrieveEvents(event))
#    return events

def normalizeCoverityAnalysisAdvise(data):
    ret = dict()
    ret['prompts'] = []
    ret['mergeKeys'] = []
    ret['count'] = 0
    for mergeKey in data:
        for prompt in data[mergeKey]:
            ret['prompts'].append(prompt['prompt'])
            ret['mergeKeys'].append(mergeKey)
            ret['count'] = ret['count'] + 1
    return ret

# ret = dict()
# ret[mergeKey] = [
# {
#     "prompt": "...",
#     "hash": "",
# },
# {
#     "prompt": "...",
#     "hash": "",
# }
# ]
def generateCoverityAnalysisAdvisePrompt(ret, workDir, mergeKeyToAdd, events, branch):
    utils.heavyLogging('generateCoverityAnalysisAdvisePrompt: mergeKey {}, events {}, branch {}'.format(mergeKeyToAdd, events, branch))
    pfCovDetailedHTMLReportDir = utils.getEnv('PF_COV_DETAILED_HTML_REPORT_DIR', branch)
    utils.heavyLogging('generateCoverityAnalysisAdvisePrompt: pfCovDetailedHTMLReportDir {}'.format(pfCovDetailedHTMLReportDir))
    htmlDir = os.path.join(pfCovDetailedHTMLReportDir, mergeKeyToAdd, '1')
    trainingDir = os.path.join(workDir, 'prune', mergeKeyToAdd)
    utils.makeEmptyDirectory(trainingDir)

    with open(os.path.join(os.getenv('WORKSPACE'), os.getenv('PF_ROOT'), 'templates', 'coverity-analysis-advise'), 'r') as fpTemplate:
        tMainPrompt = fpTemplate.read()
    import covhtmlparser
    covhtmlparser.pruneHtmlReport(htmlDir, trainingDir, events)
    for htmlFile in glob.glob('{}/*'.format(trainingDir)):
        htmlFileBasename = os.path.basename(htmlFile)
        # -5: truncate ".html"
        newPrompt = Template(tMainPrompt).safe_substitute(FUNCTION_WITH_COVERITY_REPORT=open(htmlFile, 'r').read().replace('\t', '    '), \
                                                    FILENAME=htmlFileBasename[htmlFileBasename.index('_') + 1:-5])
        duplicate = False
        hashOfNewPrompt = hash(newPrompt)
        for existedMergeKey in ret:
            if existedMergeKey == mergeKeyToAdd:
                for prompt in ret[existedMergeKey]:
                    if prompt['hash'] == hashOfNewPrompt:
                        duplicate = True
                        break
                else:
                    continue # Continue if the inner loop wasn't broken.
                break # Inner loop was broken, break the outer.
        if duplicate == True:
            utils.heavyLogging('generateCoverityAnalysisAdvisePrompt: duplicate')
        else:
            if mergeKeyToAdd not in ret:
                ret[mergeKeyToAdd] = []
            prompt = dict()
            prompt['prompt'] = newPrompt
            prompt['hash'] = hashOfNewPrompt
            ret[mergeKeyToAdd].append(prompt)

def coverityAnalysisAdvise(configs):
    # coverity-analysis-advise-full: all mergeKeys in preview-report-committer.json
    # coverity-analysis-advise-commit: new mergeKeys added to preview-report-committer.json (vs. preview-report-committer_parent.json).
    #promptTemplate = 'coverity-analysis-advise'
    ret = dict()
    if configs['function'] == 'coverity-analysis-advise-commit':
        # preview-report-committer-${BUILD_BRANCH}.json
        pfPreviewReport = utils.getPFPreviewReport()
        # analyze new defects only
        mergeKeysBase = dict()
        mergeKeysHead = dict()
        pfPreviewReportBase = utils.getPFPreviewReport(basePhase=True)
        with open(pfPreviewReportBase) as fpPreviewReport:
            jsonReport = json.load(fpPreviewReport)
            for cid in jsonReport['defects']:
                mergeKeysBase[jsonReport['defects'][cid]['mergeKey']] = []
                for event in jsonReport['defects'][cid]['events']:
                    mergeKeysBase[jsonReport['defects'][cid]['mergeKey']].append(int(event['lineNumber']))
        with open(pfPreviewReport) as fpPreviewReport:
            jsonReport = json.load(fpPreviewReport)
            for cid in jsonReport['defects']:
                mergeKeysHead[jsonReport['defects'][cid]['mergeKey']] = []
                for event in jsonReport['defects'][cid]['events']:
                    mergeKeysHead[jsonReport['defects'][cid]['mergeKey']].append(int(event['lineNumber']))
        if 'BUILD_BRANCH' in os.environ:
            branch = os.getenv('BUILD_BRANCH')
        else:
            branch = 'PF_NONE'
        for mergeKeyHead in mergeKeysHead:
            if mergeKeyHead not in mergeKeysBase:
                generateCoverityAnalysisAdvisePrompt(ret, configs['WORK_DIR'], mergeKeyHead, mergeKeysHead[mergeKeyHead], branch)
    else:
        # coverity-analysis-advise-full
        # Pipeline design:
        #     The pipeline framework supports using the same source code across different build branches 
        #     (i.e., identical source with varying build configurations). For cases involving different source code, 
        #     we recommend splitting parallel builds into separate pipelines.
        pass # For better performance, batch/queue this operation and process it later in checkRealGPTComment() (covjira.py).

    return ret

def codetekCorrection(configs):
    files = getSourceFiles()
    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', configs['function']), 'r', encoding='utf-8', errors='ignore') as fpTemplate:
        t = fpTemplate.read()
    ret = dict()
    ret['prompts'] = []
    for file in files:
        fullPath = file
        if 'PF_SOURCE_DST_0' in os.environ:
            fullPath = os.path.join(os.path.join(os.getenv('PF_SOURCE_DST_0')), fullPath)
        utils.heavyLogging('codetekCorrection: fullPath {}'.format(fullPath))
        try:
            with open(fullPath, 'r') as f:
                sourceCode = f.read()
        except:
            with open(fullPath, 'r', encoding='utf-8', errors='ignore') as f:
                sourceCode = f.read()
        ret['prompts'].append(Template(t).safe_substitute(SOURCE_CODE=sourceCode, \
                                                            FILE_NAME=file))
    ret['count'] = len(ret['prompts'])
    ret['assistantPrompt'] = 'assistant\nFixed Code:\n'

    return ret

def codetekRanking(function, workDir):
    files = getSourceFiles()

    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', function), 'r') as fpTemplate:
        t = fpTemplate.read()
    ret = dict()
    ret['prompts'] = []
    for file in files:
        fullPath = file
        if 'PF_SOURCE_DST_0' in os.environ:
            fullPath = os.path.join(os.path.join(os.getenv('PF_SOURCE_DST_0')), fullPath)
        with open(fullPath, 'r', encoding='utf-8') as f:
            sourceCode = f.read()
        with open(os.path.join(workDir, 'tempYaml'), 'r') as fpYaml:
            import yaml
            temporalYamlTxt = fpYaml.read()
            temporalYaml = yaml.safe_load(temporalYamlTxt)
        ret['prompts'].append(Template(t).safe_substitute(ORIGIN_CODE=sourceCode, \
                                                            GENERATED_CODE=temporalYaml['output']['output_code']))
    ret['count'] = len(ret['prompts'])
    ret['assistantPrompt'] = 'assistant\nFixed Code:\n'

    return ret

def generatePrompts(function, configs, workDir=None):
    # data['count']: total number of prompts returned
    # data['prompts']: user prompts
    # data['assistantPrompt'](optional): assistant prompt
    # data['mergeKeys'](optional): for coverity-analysis-advise-full, coverity-analysis-advise-commit
    if function == 'git-commit-message-review':
        data = gitCommitMessageReview(configs)
    elif function == 'git-commit-coverity-check':
        data = gitPatchCoverityCheck(configs)
    elif function == 'git-commit-coverity-check-indiv':
        data = gitPatchCoverityCheck(configs)
    elif function == 'coverity-analysis-advise-full' or function == 'coverity-analysis-advise-commit':
        utils.saveEnv(configs['WORK_DIR'], 'PF_CODETEK_COV_ANALYSIS_ADVISE', '1')
        tmpData = coverityAnalysisAdvise(configs)
        data = normalizeCoverityAnalysisAdvise(tmpData)
    elif function in ['codetek-correction', 'codetek-optimization', 'codetek-code-comment', 'codetek-coding-style']:
        data = codetekCorrection(configs)
    elif function in ['codetek-correction-ranker', 'codetek-optimization-ranker']:
        data = codetekRanking(function, workDir)

    return data

def codetekYamlParser(input):
    ret = dict()

    captureCode = False
    patternOfFile = re.compile(r'^  file: "(.*?)"')
    patternOfCode = re.compile(r'^  output_code: \|')
    fpInput = open(input, 'r', encoding='utf-8')
    while True:
        line = fpInput.readline()
        if not line:
            break
        if captureCode == True:
            if line.startswith('    '):
                ret['output_code'].append(line[4:])
            else:
                ret['output_code'].append(line)
        else:
            matchFile = patternOfFile.search(line)
            matchCode = patternOfCode.search(line)
            if matchFile:
                ret['file'] = matchFile.group(1)
            elif matchCode:
                captureCode = True
                ret['output_code'] = []
    fpInput.close()
    if 'output_code' in ret:
        ret['output_code'] = ''.join(ret['output_code'])

    return ret

def indentYaml(inputTxt):
    indents = []
    patternOfCommitMessage = re.compile(r'^  final_commit_message: \|')
    patternOfPatches = re.compile(r'^patches:')

    startIndent = False
    lines = inputTxt.splitlines(True)
    for line in lines:
        matchCommitMessage = patternOfCommitMessage.search(line)
        matchPatches = patternOfPatches.search(line)
        if matchPatches:
            startIndent = False
            indents.append(line)
        elif matchCommitMessage:
            startIndent = True
            indents.append(line)
        elif startIndent == True:
            if line.startswith('    '):
                indents.append(line)
            else:
                indents.append('    {}'.format(line))
        else:
            indents.append(line)

    return ''.join(indents)

def archiveToZip(configs, results):
    utils.makeEmptyDirectory(os.path.join(configs['WORK_DIR'], '.ziparchive'))
    with zipfile.ZipFile(os.path.join(configs['WORK_DIR'], '{}.zip'.format(configs['display_name'])), mode='w') as zf:
        for result in results:
            utils.heavyLogging('archiveToZip: add {}'.format(result))
            resultYaml = codetekYamlParser(result)
            if 'file' in resultYaml and 'output_code' in resultYaml:
                filepath = resultYaml['file']
                tmpPath = os.path.join(configs['WORK_DIR'], '.ziparchive', filepath)
                tmpDir = os.path.dirname(tmpPath)
                utils.makeEmptyDirectory(tmpDir)
                fpOutput = open(tmpPath, 'w', encoding='utf-8')
                fpOutput.write(resultYaml['output_code'])
                fpOutput.close()
                zf.write(tmpPath, arcname=filepath)
            else:
                utils.heavyLogging('archiveToZip: failure {}'.format(result))
    return '{}.zip'.format(configs['display_name'])

def extractYaml(input):
    # extract conent in ```yaml ... ```
    if '```yaml' in input:
        startIndex = input.index('```yaml') + len('```yaml')
        endIndex = input.rfind('```')
        input = input[startIndex:endIndex].strip()
        input = reIndent(input)
    # RealGPT output yaml content ends with '```' and no '```yaml' header
    # especially function == 'codetek-optimization':
    if input.endswith('```'):
        input = input[:-3]
    return input

def codeprompt(configs):
    data = generatePrompts(configs['function'], configs)
    # data['count']: total number of prompts returned
    # data['prompts']: user prompts
    # data['assistantPrompt'](optional): assistant prompt
    utils.heavyLogging('codeprompt: got prompts {}'.format(data['count']))

    results = []
    resultsFilenameOnly = []
    idx = 0
    for prompt in data['prompts']:
        writeOutputFile = True
        outputFile = os.path.join(configs['WORK_DIR'], 'codetek-result-{}'.format(idx))
        #if configs['function'] == 'coverity-analysis-advise-full':
        #    outputFile = os.path.join(configs['WORK_DIR'], 'codetek-result-{}-{}'.format(data['mergeKeys'][idx], idx))
        #    f = open(outputFile, 'w')
        #    f.write(prompt)
        #    f.close()
        #else:
        utils.heavyLogging('codeprompt: GPT input {}'.format(prompt))
        ret = realgpt(prompt, configs['customization'], configs['function'], configs['WORK_DIR'])
        utils.lightLogging('codeprompt: GPT raw output {}'.format(ret))
        ret = extractYaml(ret)
        #utils.heavyLogging('codeprompt: GPT output debug\n{}'.format(ret))
        if configs['function'] == 'git-commit-message-review':
            ret = indentYaml(ret)
        utils.heavyLogging('codeprompt: GPT output\n{}'.format(ret))
        # TODO: ugly, to avoid repeated commit messages in RealGPT's output
        if configs['function'] == 'git-commit-message-review':
            import yaml
            retYaml = yaml.safe_load(ret)
            try:
                #utils.lightLogging('codeprompt: hash {}'.format(retYaml['commit_message']['final_commit_message'].strip()))
                commitMessageHash = hash(retYaml['commit_message']['final_commit_message'].strip())
                utils.heavyLogging('codeprompt: origin commit message {}'.format(data['commitMessageHash']))
                utils.heavyLogging('codeprompt: refine commit message {}'.format(commitMessageHash))
                if data['commitMessageHash'] == commitMessageHash:
                    utils.heavyLogging('codeprompt: repeated commit message')
                    retYaml['commit_message']['final_commit_message'] = 'The original commit message is sufficient.'
                    with open(outputFile, 'w', encoding='utf-8') as yaml_file:
                        yaml.dump(retYaml, yaml_file, default_flow_style=False)
                    writeOutputFile = False
            except:
                pass
        if writeOutputFile == True:
            f = open(outputFile, 'w', encoding='utf-8')
            f.write(ret)
            f.close()

        results.append(outputFile)
        resultsFilenameOnly.append('WORKSPACE:{}'.format(outputFile))
        idx = idx + 1
    if configs['function'].startswith('codetek-'):
        zipFile = archiveToZip(configs, results)
        resultsFilenameOnly = [zipFile]
    utils.saveEnv(configs['WORK_DIR'], 'PF_CODEPROMPT_FUNCTION', configs['function'])

    with open(os.path.join(os.getenv('WORKSPACE'), configs['WORK_DIR'], 'PF_CODEPROMPT_RESULTS'), 'w', encoding='utf-8') as f:
        for result in results:
            f.write('{}\n'.format(result))
    utils.saveEnv(configs['WORK_DIR'], 'PF_CODEPROMPT_RESULT', os.path.join(os.getenv('WORKSPACE'), configs['WORK_DIR'], 'PF_CODEPROMPT_RESULTS'))
    # archive the Codetek configuration as Jenkins artifacts for RJIRA integration
    with open(os.path.join(configs['WORK_DIR'], 'codetekInfo.json'), 'w', encoding='utf-8') as fpRevisionInfo:
        json.dump(configs, fpRevisionInfo, indent=2)
    resultsFilenameOnly.append('codetekInfo.json')
    fpArtifacts = open(os.path.join(configs['WORK_DIR'], '.artifacts'), 'w', encoding='utf-8')
    fpArtifacts.write(','.join(resultsFilenameOnly))
    fpArtifacts.close()

def gptSelfRanking(results, function, workDir):
    for i in range(len(results)):
        temporalYamlTxt = extractYaml(results[i]['output'])
        fpOutput = open(os.path.join(workDir, 'tempYaml'), 'w', encoding='utf-8')
        fpOutput.write(temporalYamlTxt)
        fpOutput.close()
        data = generatePrompts('{}-ranker'.format(function), None, workDir=workDir)
        for prompt in data['prompts']:
            utils.lightLogging('gptSelfRanking: GPT input(ranking) {}'.format(prompt))
            ret = realgpt(prompt, '', '{}-ranker'.format(function), workDir)
            utils.lightLogging('gptSelfRanking: GPT raw output(ranking) {}'.format(ret))
            import yaml
            scoreYaml = yaml.safe_load(extractYaml(ret))
            results[i]['score'] = scoreYaml['score']
            #ret = extractYaml(ret)
    sortedByScore = sorted(results, key=lambda x: x['score'], reverse=True)
    utils.lightLogging('gptSelfRanking: ranking result\n{}'.format(results))
    utils.lightLogging('gptSelfRanking: ranking result(sorted)\n{}'.format(sortedByScore))

def stupidMultiLineOptimization(input):
    # RealGPT does not output "output_code: |"
    # especially function == 'codetek-optimization':
    if 'output_code:' in input and 'output_code: |' not in input:
        input = input.replace('output_code:', 'output_code: |')
    return input

def realgpt(data, customizations, function, workDir):
    utils.heavyLogging('codeprompt: input counted {} chars.'.format(len(data)))

    # openai api-key
    from openai import OpenAI
    model = 'realtek/Meta-Llama-Default'
    base_url = 'https://devops.realtek.com/realgpt-api/codetek/v1'
    if 'JENKINS_URL' in os.environ and '-infra' in os.getenv('JENKINS_URL') or 'apiproxy' in os.getenv('JENKINS_URL'):
        base_url = 'https://devops-infra.rtkbf.com/realgpt-api/codetek/v1'

    # vscode autocomplete
    if 'REALGPT_KEY' in os.environ:
        apiKey = os.getenv('REALGPT_KEY')
    else:
        apiKey = os.getenv('PF_REALGPT_KEY')
    client = OpenAI(
        base_url=base_url,
        api_key=apiKey,
    )

    system_prompt = 'You are the embedding system and ic software programmer. Respond to the following questions based on the code block. Think about it step by step to generate these answers. These answers are very important to my career.'
    retries = 1
    results = []
    if 'SELF_RANKING' in customizations and \
        (function == 'codetek-correction' or function == 'codetek-optimization'):
        # ask 5 times
        retries = 5
        utils.heavyLogging('realgpt: SELF_RANKING enabled')
    for retry in range(retries):
        for i in range(3):
            timeout = False
            try:
                utils.heavyLogging('realgpt: {}th api call'.format(i))
                completion = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": ''.join(data)},
                    ],
                    stream=False,
                )
                gptOutput = completion.choices[0].message.content
            except Exception as e:
                # timeout
                timeout = True
                gptOutput = 'exception:\n  error timeout'
                utils.heavyLogging(e)
            if timeout == False:
                break
        if function == 'codetek-optimization':
            gptOutput = stupidMultiLineOptimization(gptOutput)

        result = dict()
        result['output'] = gptOutput
        result['score'] = 10
        results.append(result)
    if len(results) > 1:
        gptSelfRanking(results, function, workDir)

    return results[0]['output']

def main(argv):
    #configs = utils.actionMain(argv)
    workDir = ''
    configFile = ''
    command = ''
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
        elif name in ('-c', '--command'):
            command = value
        elif name in ('-w', '--work_dir'):
            workDir = value

    if os.path.isdir(workDir) == False:
        os.makedirs(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'codeprompt.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    utils.cleanEnvAndArchives(workDir)
    if configs['enable'] == 'false' or configs['enable'] == False:
        utils.heavyLogging('main: skip codeprompt')
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    utils.cleanEnvAndArchives(workDir)
    if command == 'CHECK_ENV':
        utils.checkSingularity(workDir)
    else:
        codeprompt(configs)

if __name__ == '__main__':
    main(sys.argv)
