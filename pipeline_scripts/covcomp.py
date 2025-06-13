import json, datetime, glob
import sys, getopt
import os, logging
import utils, git, coverityapi
from string import Template
from datetime import datetime as dt

def getCoverityProject(secret, configs, stream):
    if configs['coverity_project'] == '':
        output = os.path.join(configs['WORK_DIR'], 'covProject.json')
        #utils.heavyLogging("debug coverityapi 10 reviewed")
        coverityapi.queryCoverityStream(secret['username'], secret['key'], 'http://{}:{}'.format(configs['host'], configs['port']), stream, output)
        fpProject = open(output)
        projectObj = json.load(fpProject)
        fpProject.close()
        configs['coverity_project'] = projectObj['streams'][0]['primaryProjectName']

def coveritySnapshotIssues(configs, secret, parentProject, snapshotid):
    matcher = dict()
    matcher['class'] = 'Project'
    matcher['name'] = parentProject
    matcher['type'] = 'nameMatcher'
    filter = dict()
    filter['columnKey'] = 'project'
    filter['matchMode'] = 'oneOrMoreMatch'
    filter['matchers'] = [matcher]
    input = dict()
    input['filters'] = [filter]
    input['columns'] = ["cid", "classification", "action"]
    input['snapshotScope'] = dict()
    input['snapshotScope']['show'] = dict()
    input['snapshotScope']['show']['scope'] = snapshotid
    with open(os.path.join(configs['WORK_DIR'], 'input-{}.json'.format(snapshotid)), 'w') as outfile:
        json.dump(input, outfile)

    offset = 0
    totalRows = 1000000
    while totalRows > 0:
        outputResult = os.path.join(configs['WORK_DIR'], 'snapshot-{}.json'.format(snapshotid))
        #utils.heavyLogging("debug coverityapi reviewed")
        coverityapi.queryCoverityIssues(secret['username'], secret['key'], \
                                        'http://{}:{}'.format(configs['host'], configs['port']), \
                                        offset, '{}'.format(os.path.join(configs['WORK_DIR'], 'input-{}.json'.format(snapshotid))), outputResult)
        fpSnapshot = open(outputResult)
        jsonSnapShot = json.load(fpSnapshot)
        fpSnapshot.close()
        if offset == 0:
            totalRows = jsonSnapShot['totalRows']
            retRows = jsonSnapShot['rows']
        else:
            retRows = retRows + jsonSnapShot['rows']
        offset = offset + 200
        totalRows = totalRows - 200
    return retRows

def coveritySnapshot(configs, secret, snapshotid):
    output = os.path.join(configs['WORK_DIR'], 'snapshotInfo-{}.json'.format(snapshotid))
    #utils.heavyLogging("debug coverityapi 58 reviewed")
    coverityapi.queryCoveritySnapshot(secret['username'], secret['key'], \
                                        'http://{}:{}'.format(configs['host'], configs['port']), \
                                        snapshotid, output)
    fpSnapshot = open(output)
    jsonSnapShot = json.load(fpSnapshot)
    fpSnapshot.close()
    return jsonSnapShot

def coverityStreamSnapshots(configs, secret, stream):
    output = os.path.join(configs['WORK_DIR'], 'streamSnapshots.json')
    coverityapi.queryCoverityStreamSnapshots(secret['username'], secret['key'], \
                                                'http://{}:{}'.format(configs['host'], configs['port']), \
                                                stream, output)
    fpSnapshot = open(output)
    jsonSnapShot = json.load(fpSnapshot)
    fpSnapshot.close()
    return jsonSnapShot

def parseSnapshot(rows):
    # re-construct
    cids = dict()
    for row in rows:
        for parameter in row:
            if parameter['key'] == 'cid':
                cid = parameter['value']
                cids[cid] = dict()
            if parameter['key'] == 'classification':
                cids[cid]['classification'] = parameter['value']
            if parameter['key'] == 'action':
                cids[cid]['action'] = parameter['value']
    #utils.heavyLogging('parseSnapshot: debug0 {}'.format(cids))
    validCids = dict()
    for key in cids:
        if cids[key]['action'] == 'Ignore' or cids[key]['classification'] == 'Intentional' or cids[key]['classification'] == 'False Positive':
            pass
        else:
            validCids[key] = 1
    #utils.heavyLogging('parseSnapshot: debug1 {}'.format(validCids))
    return validCids

def queryReviewers(workDir):
    git.gerritQueryReviewers(workDir, os.path.join(workDir, 'reviewers'))

def formatLine(issueURL, cid, checker, filePath, mainEventLineNumber):
    return '<a href="{}">CID: {}</a>, CHECKER: {}, file: {}, line: {}'.format(issueURL, cid, checker, filePath, mainEventLineNumber)

def queryGerritChangeByCommit(customization, commit):
    ret = dict()
    # ssh -p 29418 ctcsoc.rtkbf.com gerrit query --format JSON commit:15c9fd680174a26e3ac938b5971d1b15cc6acad0
    if 'GERRIT_PROJECT' in os.environ:
        if 'GERRIT_USER' in os.environ:
            cmdPieces = ['ssh', '-l', os.getenv('GERRIT_USER'), '-i', os.getenv('GERRIT_KEY')]
        else:
            cmdPieces = ['ssh']
        cmdPieces += ['-p', os.getenv('GERRIT_PORT'), os.getenv('GERRIT_HOST'), \
                        'gerrit', 'query', '--format', 'JSON', \
                        'commit:{}'.format(commit)]
        utils.heavyLogging('queryGerritChangeByCommit: {}'.format(cmdPieces))
        ret = utils.popenReturnStdout(cmdPieces, dict(os.environ))
        try:
            gerritQuery = json.loads(ret['lines'][0])
            utils.lightLogging('queryGerritChangeURL: gerritQuery, {}'.format(gerritQuery))
            if customization.startswith('DATE_COMP_'):
                changeDate = datetime.datetime.fromtimestamp(gerritQuery['createdOn']).date()
                today = datetime.datetime.now().date()
                diff = today - changeDate
                tokens = customization.split('_')
                d = int(tokens[2])
                utils.heavyLogging('queryGerritChangeURL: DATE_COMP {}'.format(d))
                if diff.days <= d:
                    ret['url'] = gerritQuery['url']
                    ret['change'] = gerritQuery['number']
                    ret['owner'] = gerritQuery['owner']['username']
                    ret['date'] = datetime.datetime.fromtimestamp(gerritQuery['createdOn']).strftime('%Y-%m-%d')
                else:
                    utils.heavyLogging('queryGerritChangeURL: skip change {}({})'.format(gerritQuery['number'], changeDate))
                    pass
            else:
                ret['url'] = gerritQuery['url']
                ret['change'] = gerritQuery['number']
                ret['owner'] = gerritQuery['owner']['username']
                ret['date'] = datetime.datetime.fromtimestamp(gerritQuery['createdOn']).strftime('%Y-%m-%d')
        except:
            pass
    return ret

def queryGerritChangeFileList():
    ret = dict()
    ret['files'] = []
    # ssh -p 29418 ctcsoc.rtkbf.com gerrit query --current-patch-set --files --format JSON change:21340
    if 'GERRIT_PROJECT' in os.environ:
        if 'GERRIT_USER' in os.environ:
            cmdPieces = ['ssh', '-l', os.getenv('GERRIT_USER'), '-i', os.getenv('GERRIT_KEY')]
        else:
            cmdPieces = ['ssh']
        cmdPieces += ['-p', os.getenv('GERRIT_PORT'), os.getenv('GERRIT_HOST'), \
                        'gerrit', 'query', '--format', 'JSON', \
                        '--current-patch-set', '--files', \
                        'change:{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'))]
        utils.heavyLogging('queryGerritChangeFileList: {}'.format(cmdPieces))
        retQuery = utils.popenReturnStdout(cmdPieces, dict(os.environ))
        try:
            gerritQuery = json.loads(retQuery['lines'][0])
            utils.lightLogging('queryGerritChangeFileList: gerritQuery, {}'.format(gerritQuery))
            for fileInfo in gerritQuery['currentPatchSet']['files']:
                ret['files'].append(fileInfo['file'])
        except Exception as e:
            utils.heavyLogging('queryGerritChangeFileList: exception {}'.format(e))
            pass
    return ret

# input: previewReportPath, newCIDs, configs
# output: report, skipCIDs
def advancedAnalysis(report, skipCIDs, previewReportPath, cidDates, newCIDs, configs):
    with open(previewReportPath) as fpDefects:
        jsonDefects = json.load(fpDefects)
        defects = jsonDefects['defects']
    # pretty format
    for newCID in newCIDs:
        if newCID in defects:
            author = defects[newCID]['events'][0]['author']
            if author == '':
                if 'SKIP_UNKNOWN' in configs['customization']:
                    continue
                else:
                    author = 'UNKNOWN'
            if author not in report:
                report[author] = dict()
                report[author]['CIDs'] = []
                report[author]['rowspan'] = 0
                report[author]['defectscount'] = 0
                report[author]['changes'] = dict()
            # to avoid duplicate counts of different previewReportPaths
            if newCID in report[author]['CIDs']:
                continue
            else:
                report[author]['CIDs'].append(newCID)
            gerritChange = dict()
            if defects[newCID]['events'][0]['commithash'] != '':
                gerritChange = queryGerritChangeByCommit('', defects[newCID]['events'][0]['commithash'])

            if 'change' in gerritChange:
                if 'STRICT_PATCH' in configs['customization'] and gerritChange['change'] != os.getenv('GERRIT_CHANGE_NUMBER'):
                    skipCIDs.append(newCID)
                    utils.heavyLogging('covComp: skip CID {}(STRICT_PATCH)'.format(newCID))
                changeDate = dt.strptime(gerritChange['date'], '%Y-%m-%d')
                cidDate = dt.strptime(cidDates[newCID], '%Y-%m-%d')
                if 'NEW_ONLY' in configs['customization'] and changeDate < cidDate:
                    skipCIDs.append(newCID)
                    utils.heavyLogging('covComp: skip CID {}(NEW_ONLY, {})'.format(newCID, gerritChange['date']))
                gerritChangeNumber = gerritChange['change']
                gerritChangeUrl = gerritChange['url']
                gerritChangeDate = gerritChange['date']
            else:
                gerritChangeNumber = 'UNKNOWN'
                gerritChangeUrl = '-'
                gerritChangeDate = '-'

            if gerritChangeNumber not in report[author]['changes']:
                report[author]['rowspan'] = report[author]['rowspan'] + 1
                report[author]['changes'][gerritChangeNumber] = dict()
                report[author]['changes'][gerritChangeNumber]['url'] = gerritChangeUrl
                report[author]['changes'][gerritChangeNumber]['date'] = gerritChangeDate
                report[author]['changes'][gerritChangeNumber]['defects'] = []
            defect = dict()
            defect['CID'] = newCID
            defect['CHECKER'] = defects[newCID]['checkerName']
            defect['file'] = defects[newCID]['events'][0]['filePathname']
            defect['line'] = defects[newCID]['events'][0]['lineNumber']
            report[author]['defectscount'] = report[author]['defectscount'] + 1
            report[author]['changes'][gerritChangeNumber]['defects'].append(defect)

def getCoverityStream(buildBranch, mode):
    if mode == 'base':
        if buildBranch is not None:
            var = 'BR{}_COV_STREAM_PARENT'.format(buildBranch)
            if var not in os.environ:
                var = 'BR{}_COV_STREAM'.format(buildBranch)
        elif 'BUILD_BRANCH' in os.environ:
            var = 'BR{}_COV_STREAM_PARENT'.format(os.getenv('BUILD_BRANCH'))
            if var not in os.environ:
                var = 'BR{}_COV_STREAM'.format(os.getenv('BUILD_BRANCH'))
        else:
            var = 'COV_STREAM_PARENT'
            if var not in os.environ:
                var = 'COV_STREAM'
    else:
        if buildBranch is not None:
            var = 'BR{}_COV_STREAM'.format(buildBranch)
        elif 'BUILD_BRANCH' in os.environ:
            var = 'BR{}_COV_STREAM'.format(os.getenv('BUILD_BRANCH'))
        else:
            var = 'COV_STREAM'

    return os.getenv(var)

def getCIDsFromCoverityConnect(configs, stream, snapshot, secret):
    if stream not in configs['snapshotsInfo']:
        configs['snapshotsInfo'][stream] = dict()
        configs['snapshotsInfo'][stream]['snapshots'] = []
        configs['snapshotsInfo'][stream]['snapshotDates'] = []
    getCoverityProject(secret, configs, stream)
    snapshotInfo = coveritySnapshot(configs, secret, snapshot)
    configs['snapshotsInfo'][stream]['snapshots'].append(snapshot)
    configs['snapshotsInfo'][stream]['snapshotDates'].append(snapshotInfo['dateCreated'])
    snapshot0rows = coveritySnapshotIssues(configs, secret, configs['coverity_project'], snapshot)
    return parseSnapshot(snapshot0rows)

def getCIDsFromLocalReport(phase):
    defects = dict()

    pfGerritPatchsetWithSourcecode = utils.getEnv('PF_GERRIT_PATCHSET_WITH_SOURCECODE')
    if phase == 'base':
        report = 'coverity_report_base.json'
    else:
        report = 'coverity_report.json'
    if os.path.isfile(report):
        with open(report, encoding='utf-8') as fpReport:
            jsonReport = json.load(fpReport)
    elif pfGerritPatchsetWithSourcecode == '' or pfGerritPatchsetWithSourcecode == '0':
    #elif 'PF_GERRIT_PATCHSET_WITH_SOURCECODE' in os.environ and os.getenv('PF_GERRIT_PATCHSET_WITH_SOURCECODE') == '0':
        utils.heavyLogging('getCIDsFromLocalReport: skip patch without source code')
        return defects

    for issue in jsonReport['issues']:
        mergeKey = issue['mergeKey']
        if mergeKey not in defects:
            defects[mergeKey] = dict()
            defects[mergeKey]['events'] = issue['events']
    return defects

# output: newCIDs, eliminatedCIDs
def queryDefects(cidDates, newCIDs, eliminatedCIDs, configs, buildBranch):
    utils.heavyLogging('queryDefects: buildBranch {}'.format(buildBranch))
    fpSecret = open(os.getenv('COV_AUTH_KEY'))
    secret = json.load(fpSecret)
    fpSecret.close()

    # snapshot0: previous cov-analysis snapshot id
    # snapshot1: latest cov-analysis snapshot id
    parentStream = getCoverityStream(buildBranch, 'base')
    utils.heavyLogging('covComp: base stream {}'.format(parentStream))
    if len(configs['snaphots']) > 0:
        baseSnapshot = configs['snaphots'][0]
        if baseSnapshot == 'ROOT' or baseSnapshot == 'COV_STREAM_ROOT':
            # query the oldest snapshot
            snapshotsInfo = coverityStreamSnapshots(configs, secret, parentStream)
            if 'snapshotsForStream' in snapshotsInfo and len(snapshotsInfo['snapshotsForStream']) > 0:
                baseSnapshot = snapshotsInfo['snapshotsForStream'][0]['id']
            else:
                baseSnapshot = None
    else:
        if buildBranch is not None:
            # covcomp after composition
            baseSnapshot = os.getenv('BR{}_COV_SNAPSHOT_PARENT'.format(buildBranch))
        elif 'BUILD_BRANCH' in os.environ:
            # covcomp in composition
            baseSnapshot = os.getenv('BR{}_COV_SNAPSHOT_PARENT'.format(os.getenv('BUILD_BRANCH')))
        else:
            # covcomp in single build
            baseSnapshot = os.getenv('COV_SNAPSHOT_PARENT')
    if baseSnapshot is None:
        utils.heavyLogging('covComp: invalid snapshot id')
        return
    utils.heavyLogging('covComp: previous snapshot {}'.format(baseSnapshot))
    if baseSnapshot == 'LOCAL':
        # dict from getCIDsFromLocalReport
        snapshot0CIDs = getCIDsFromLocalReport('base')
    else:
        # array from getCIDsFromCoverityConnect
        snapshot0CIDs = getCIDsFromCoverityConnect(configs, parentStream, baseSnapshot, secret)

    if len(configs['snaphots']) > 1:
        buildSnapshot = configs['snaphots'][1]
    else:
        if buildBranch is not None:
            # covcomp after composition
            buildSnapshot = os.getenv('BR{}_COV_SNAPSHOT'.format(buildBranch))
        elif 'BUILD_BRANCH' in os.environ:
            # covcomp in composition
            buildSnapshot = os.getenv('BR{}_COV_SNAPSHOT'.format(os.getenv('BUILD_BRANCH')))
        else:
            # covcomp in single build
            buildSnapshot = os.getenv('COV_SNAPSHOT')
    utils.heavyLogging('covComp: latest snapshot {}'.format(buildSnapshot))
    currentStream = getCoverityStream(buildBranch, 'build')
    utils.heavyLogging('covComp: build stream {}'.format(currentStream))
    if buildSnapshot == 'LOCAL':
        snapshot1CIDs = getCIDsFromLocalReport('build')
    else:
        snapshot1CIDs = getCIDsFromCoverityConnect(configs, currentStream, buildSnapshot, secret)

    localMode = False
    if baseSnapshot == 'LOCAL' and buildSnapshot == 'LOCAL':
        localMode = True
    # key not in eliminatedCIDs, key not in newCIDs
    # to avoid duplicate counts of different streams
    for key in snapshot0CIDs:
        if key not in snapshot1CIDs and key not in eliminatedCIDs:
            if localMode == True:
                defect = dict()
                defect['mergeKey'] = key
                defect['events'] = snapshot0CIDs[key]['events']
                eliminatedCIDs.append(defect)
            else:
                eliminatedCIDs.append(key)
    for key in snapshot1CIDs:
        if key not in snapshot0CIDs and key not in newCIDs:
            if localMode == True:
                defect = dict()
                defect['mergeKey'] = key
                defect['events'] = snapshot1CIDs[key]['events']
                newCIDs.append(defect)
            else:
                newCIDs.append(key)
            # For CN3SD7, date comparison, all defects's change date should late than base snapshot's
            # something like "dateCreated": "2025-02-27T03:08:50.306Z"
            if parentStream in configs['snapshotsInfo']:
                cidDates[key] = configs['snapshotsInfo'][parentStream]['snapshotDates'][0][:10]
    return localMode

def formatNewly(configs, CIDs, localMode):
    if 'STRICT_PATCH' in configs['customization']:
        ret = queryGerritChangeFileList()
        utils.heavyLogging('deubg: {}'.format(ret))
    CIDTexts = []
    # general format
    for newCID in CIDs[:]:
        if localMode == True:
            descs = []
            CIDInGerritChange = False
            for event in newCID['events']:
                descs.append('<li>file {}, line {}, description {}</li>'.format(event['strippedFilePathname'], event['lineNumber'], event['eventDescription']))
                if 'STRICT_PATCH' in configs['customization']:
                    eventFilename = os.path.basename(event['strippedFilePathname'])
                    utils.heavyLogging('formatNewly: compare {}/{}'.format(eventFilename, ret['files']))
                    for fileChanged in ret['files']:
                        if eventFilename in fileChanged:
                            CIDInGerritChange = True
                            break
            if 'STRICT_PATCH' in configs['customization'] and CIDInGerritChange == False:
                utils.heavyLogging('formatNewly: skip {}'.format(newCID['mergeKey']))
                CIDs.remove(newCID)
                continue
            cidText = '<li>{}<ul>{}</ul></li>'.format(newCID['mergeKey'], '\n'.join(descs))
            CIDTexts.append(cidText)
        else:
            # TODO: parentProject, currentProject
            issueURL = 'http://{}:{}/query/defects.htm?project={}&cid={}'.format(configs['host'], configs['port'], configs['coverity_project'], newCID)
            cidText = '<li><a href="{}">{}</a></li>'.format(issueURL, newCID)
            CIDTexts.append(cidText)
    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'covcomp_report_newly.html'), 'r') as fpTemplate:
        tNewly = fpTemplate.read()
    return Template(tNewly).safe_substitute(NEW_DEFECTS=('\n').join(CIDTexts))

def formatEliminated(configs, eliminatedCIDs, localMode):
    eliminatedCIDTexts = []
    jsonPreviewReport = dict()
    if os.path.isfile('preview_report_v2_parent.json'):
        with open('preview_report_v2_parent.json') as fpPreviewReport:
            jsonPreviewReport = json.load(fpPreviewReport)
    for eliminatedCID in eliminatedCIDs:
        if localMode == True:
            descs = []
            for event in eliminatedCID['events']:
                descs.append('<li>file {}, line {}, description {}</li>'.format(event['strippedFilePathname'], event['lineNumber'], event['eventDescription']))
            cidText = '<li>{}<ul>{}</ul></li>'.format(eliminatedCID['mergeKey'], '\n'.join(descs))
            eliminatedCIDTexts.append(cidText)
        else:
            issueURL = 'http://{}:{}/query/defects.htm?project={}&cid={}'.format(configs['host'], configs['port'], configs['coverity_project'], eliminatedCID)
            cidText = '<a href="{}">{}</a>'.format(issueURL, eliminatedCID)
            if 'issueInfo' in jsonPreviewReport:
                for issue in jsonPreviewReport['issueInfo']:
                    if str(issue['cid']) == eliminatedCID:
                        cidText = formatLine(issueURL, eliminatedCID, \
                                                issue['occurrences'][0]['checker'], issue['occurrences'][0]['file'], issue['occurrences'][0]['mainEventLineNumber'])
                        break
            eliminatedCIDTexts.append('<li>{}</li>'.format(cidText))
    with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'covcomp_report_eliminated.html'), 'r') as fpTemplate:
        tEliminated = fpTemplate.read()
    return Template(tEliminated).safe_substitute(ELIMINATED_DEFECTS=('\n').join(eliminatedCIDTexts))

def covComp(configs):
    # check PF_COVERITY_EMPTY_ANALYSIS from coverity stage
    if 'BUILD_BRANCH' in os.environ:
        varCovAnalysis = 'BR{}_COVERITY_EMPTY_ANALYSIS'.format(os.getenv('BUILD_BRANCH'))
    else:
        varCovAnalysis = 'COVERITY_EMPTY_ANALYSIS'

    if varCovAnalysis in os.environ:
        utils.heavyLogging('covComp: skip({})'.format(varCovAnalysis))
        newDefects = []
        eliminatedDefects = []
    else:
        newCIDs = []
        skipCIDs = []
        eliminatedCIDs = []
        # a CID -> DATE map (For CN3SD7, new defects should newer than DATE)
        # CID: discovered in new snapshot(build snapshot)
        # DATE: date of old snapshot(base snapshot)
        cidDates = dict()
        configs['snapshotsInfo'] = dict()
        if 'PF_GLOBAL_PARALLELINFO' in os.environ and 'BUILD_BRANCH' not in os.environ:
            for branch in configs['buildBranches']:
                localMode = queryDefects(cidDates, newCIDs, eliminatedCIDs, configs, branch)
        else:
            localMode = queryDefects(cidDates, newCIDs, eliminatedCIDs, configs, None)
        utils.heavyLogging('newCIDs: {}'.format(newCIDs))
        utils.heavyLogging('eliminatedCIDs: {}'.format(eliminatedCIDs))

        if configs['html_report'] == True:
            # STRICT_PATCH works in advancedAnalysis(for build with advanced coverity analysis)
            # or formatNewly(for build with local coverity analysis)
            if 'GERRIT_PROJECT' in os.environ:
                if 'GERRIT_CHANGE_NUMBER' in os.environ:
                    gerritURL = 'https://{}/gerrit/c/{}/+/{}'.format(os.getenv('GERRIT_HOST'), os.getenv('GERRIT_PROJECT'), os.getenv('GERRIT_CHANGE_NUMBER'))
                else:
                    gerritURL = 'https://{}/gerrit/admin/repos/{}'.format(os.getenv('GERRIT_HOST'), os.getenv('GERRIT_PROJECT'))
            else:
                gerritURL = 'NONE'
            gerritBranch = ''
            if 'GERRIT_BRANCH' in os.environ:
                gerritBranch = 'Gerrit branch: {}'.format(os.getenv('GERRIT_BRANCH'))

            # consider the data from preview-report-committer.json in addition to the information obtained from Coverity Connect, 
            # the file scripts/excludeCIDs influences the final results.
            advancedCoverityReports = glob.glob('preview-report-committer*.json')
            if len(advancedCoverityReports) > 0:
                report = dict()
                for advancedCoverityReport in advancedCoverityReports:
                    advancedAnalysis(report, skipCIDs, advancedCoverityReport, cidDates, newCIDs, configs)
                utils.lightLogging('report(before): {}'.format(report))
                for user, details in report.items():
                    sorted_changes = dict(sorted(details['changes'].items(), key=lambda item: item[1]['date'], reverse=True))
                    details['changes'] = sorted_changes
                utils.lightLogging('report(sort date): {}'.format(report))
                report = dict(sorted(report.items(), key=lambda item: item[1]['defectscount'], reverse=True))
                utils.lightLogging('report(sort count): {}'.format(report))

                with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'covcomp_report_td.html'), 'r') as fpTemplate:
                    tTD = fpTemplate.read()
                with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'covcomp_report_tr.html'), 'r') as fpTemplate:
                    tTR = fpTemplate.read()
                with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'covcomp_report_table.html'), 'r') as fpTemplate:
                    tTABLE = fpTemplate.read()

                rows = []
                for author in report:
                    tdAuthor = Template(tTD).safe_substitute(content=author, rowspan=report[author]['rowspan'])
                    tdCount = Template(tTD).safe_substitute(content=report[author]['defectscount'], rowspan=report[author]['rowspan'])
                    idx = 0
                    for changeCID in report[author]['changes']:
                        change = report[author]['changes'][changeCID]
                        tdDate = Template(tTD).safe_substitute(content=change['date'], rowspan=1)
                        tdGerritLink = Template(tTD).safe_substitute(content=change['url'], rowspan=1)
                        cidTexts = []
                        tdDetail = []
                        for defect in change['defects']:
                            issueURL = 'http://{}:{}/query/defects.htm?project={}&cid={}'.format(configs['host'], configs['port'], configs['coverity_project'], defect['CID'])
                            cidText = '<li>{}</li>'.format(formatLine(issueURL, defect['CID'], defect['CHECKER'], defect['file'], defect['line']))
                            cidTexts.append(cidText)
                        tdDetail.append(Template(tTD).safe_substitute(content='<ul>{}</ul>'.format(('\n').join(cidTexts)), rowspan=1))
                        if idx == 0:
                            rows.append(Template(tTR).safe_substitute(author=tdAuthor, count=tdCount, \
                                                            date=tdDate, \
                                                            gerrit_link=tdGerritLink, \
                                                            detail=('\n').join(tdDetail)))
                        else:
                            rows.append(Template(tTR).safe_substitute(author='', count='', \
                                                            date=tdDate, \
                                                            gerrit_link=tdGerritLink, \
                                                            detail=('\n').join(tdDetail)))
                        idx = idx + 1
                    utils.lightLogging('covComp: rows {}'.format(rows))
                newly = Template(tTABLE).safe_substitute(ROWS=('\n').join(rows))
            else:
                newly = formatNewly(configs, newCIDs, localMode)

            if 'NEW_ONLY' in configs['customization']:
                eliminated = ''
            else:
                eliminated = formatEliminated(configs, eliminatedCIDs, localMode)

            if os.path.isdir(os.path.join(configs['WORK_DIR'], 'covcomp-reports')) == False:
                os.makedirs(os.path.join(configs['WORK_DIR'], 'covcomp-reports'))
            with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'covcomp_report.html'), 'r') as fpTemplate:
                tReport = fpTemplate.read()
            utils.heavyLogging('covComp: output covcomp_report.html')

            with open(os.path.join(os.getenv('PF_ROOT'), 'templates', 'covcomp_report_snapshot.html'), 'r') as fpTemplate:
                tSnapshot = fpTemplate.read()
            snpshots = ''
            for stream in configs['snapshotsInfo']:
                snpshots = snpshots + Template(tSnapshot).safe_substitute(COV_STREAM=stream, \
                                                                            BASE_SNAPSHOT=configs['snapshotsInfo'][stream]['snapshots'][0], \
                                                                            BASE_SNAPSHOT_INFO=configs['snapshotsInfo'][stream]['snapshotDates'][0], \
                                                                            BUILD_SNAPSHOT=configs['snapshotsInfo'][stream]['snapshots'][1], \
                                                                            BUILD_SNAPSHOT_INFO=configs['snapshotsInfo'][stream]['snapshotDates'][1])

            fp = open(os.path.join(configs['WORK_DIR'], 'covcomp-reports', 'covcomp_report.html'), 'w')
            fp.write(Template(tReport).safe_substitute(GERRIT_URL=gerritURL, \
                                                    GERRIT_BRANCH=gerritBranch, \
                                                    JENKINS_JOB=os.getenv('JOB_NAME'), \
                                                    SNAP_SHOTS=snpshots, \
                                                    NEWLY=newly, \
                                                    ELIMINATED=eliminated))
            fp.close()

        # for STRICT_PATCH
        if localMode == True:
            newDefects = []
            eliminatedDefects = []
            for newCID in newCIDs:
                newDefects.append(newCID['mergeKey'])
            for eliminatedCID in eliminatedCIDs:
                eliminatedDefects.append(eliminatedCID['mergeKey'])
        else:
            newDefects = list(set(newCIDs) - set(skipCIDs))
            eliminatedDefects = eliminatedCIDs

    utils.initEnv(configs['WORK_DIR'])
    utils.saveEnv(configs['WORK_DIR'], 'COVCOMP_NEW_DEFECTS', ','.join(newDefects))
    utils.saveEnv(configs['WORK_DIR'], 'COVCOMP_ELIMINATED_DEFECTS', ','.join(eliminatedDefects))
    if configs['email_nofity'] == True and 'GERRIT_PROJECT' in os.environ:
        queryReviewers(configs['WORK_DIR'])

def main(argv):
    if "COV_AUTH_KEY" not in os.environ:
        sys.exit("Environment variable COV_AUTH_KEY not defined")

    workDir = ''
    configFile = ''
    try:
        opts, args = getopt.getopt(argv[1:], 'w:f:vs', ["work_dir=", "config=", "version", "skip_translate"])
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
            workDir = value

    if os.path.isdir(workDir) == False:
        os.makedirs(workDir)
    logging.basicConfig(filename=os.path.join(workDir, 'covcomp.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    utils.cleanEnvAndArchives(workDir)
    if configs['enable'] == 'false' or configs['enable'] == False:
        utils.heavyLogging('main: skip covcomp')
        sys.exit(0)
    configs['WORK_DIR'] = workDir
    covComp(configs)

if __name__ == '__main__':
    main(sys.argv)
