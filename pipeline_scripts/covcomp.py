import json
import sys, getopt
import os, logging
import utils

def getCoverityProject(secret, configs, stream):
    if configs['project'] == '':
        cmdEnv = dict(os.environ)
        utils.popenWithStdout(['curl', '-s', '-X', 'GET', '-u', '{}:{}'.format(secret['username'], secret['key']), \
                                '--url', 'http://{}:{}/api/v2/streams/{}?locale=en_us'.format(configs['host'], configs['port'], stream), \
                                '-H', 'Content-Type: application/json', \
                                '-H', 'Accept: application/json', \
                                '-o', os.path.join(configs['WORK_DIR'], 'covProject.json')], cmdEnv)
        fpProject = open(os.path.join(configs['WORK_DIR'], 'covProject.json'))
        projectObj = json.load(fpProject)
        fpProject.close()
        return projectObj['streams'][0]['primaryProjectName']
    else:
        return configs['project']

def coveritySnapshot(configs, secret, parentProject, snapshotid):
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
    input['columns'] = ["cid"]
    input['snapshotScope'] = dict()
    input['snapshotScope']['show'] = dict()
    input['snapshotScope']['show']['scope'] = snapshotid
    with open(os.path.join(configs['WORK_DIR'], 'input.json'), 'w') as outfile:
        json.dump(input, outfile)

    cmdEnv = dict(os.environ)
    offset = 0
    totalRows = 1000000
    while totalRows > 0:
        utils.popenWithStdout(['curl', '-s', '-X', 'POST', '-u', '{}:{}'.format(secret['username'], secret['key']), \
                                '--url', 'http://{}:{}/api/v2/issues/search?offset={}&includeColumnLabels=true&locale=en_us&queryType=bySnapshot&rowCount=200'.format(configs['host'], configs['port'], offset), \
                                '-H', 'Content-Type: application/json', \
                                '-H', 'Accept: application/json', \
                                '-o', os.path.join(configs['WORK_DIR'], 'snapshot.json'), '-d', \
                                '@{}'.format(os.path.join(configs['WORK_DIR'], 'input.json'))], cmdEnv)
        fpSnapshot = open(os.path.join(configs['WORK_DIR'], 'snapshot.json'))
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

def covComp(configs):
    fpSecret = open(os.getenv('COV_AUTH_KEY'))
    secret = json.load(fpSecret)
    fpSecret.close()

    # snapshot0: previous cov-analysis snapshot id
    # snapshot1: latest cov-analysis snapshot id
    if len(configs['snaphots']) == 0:
        if 'BUILD_BRANCH' in os.environ:
            snapshotid = os.getenv('{}_COV_SNAPSHOT_PARENT'.format(os.getenv('BUILD_BRANCH')))
        else:
            snapshotid = os.getenv('COV_SNAPSHOT_PARENT')
    else:
        snapshotid = configs['snaphots'][0]
    if snapshotid == None:
        utils.heavyLogging('covComp: invalid snapshot id')
        return
    utils.heavyLogging('covComp: previous snapshot {}'.format(snapshotid))
    if 'BUILD_BRANCH' in os.environ:
        parentStream = os.getenv('{}_COV_STREAM_PARENT'.format(os.getenv('BUILD_BRANCH')))
    else:
        parentStream = os.getenv('COV_STREAM_PARENT')
    parentProject = getCoverityProject(secret, configs, parentStream)
    snapshot0rows = coveritySnapshot(configs, secret, parentProject, snapshotid)

    if len(configs['snaphots']) < 2:
        if 'BUILD_BRANCH' in os.environ:
            snapshotid = os.getenv('{}_COV_SNAPSHOT'.format(os.getenv('BUILD_BRANCH')))
        else:
            snapshotid = os.getenv('COV_SNAPSHOT')
    else:
        snapshotid = configs['snaphots'][1]
    utils.heavyLogging('covComp: latest snapshot {}'.format(snapshotid))
    if 'BUILD_BRANCH' in os.environ:
        currentStream = os.getenv('{}_COV_STREAM'.format(os.getenv('BUILD_BRANCH')))
    else:
        currentStream = os.getenv('COV_STREAM')
    currentProject = getCoverityProject(secret, configs, currentStream)
    snapshot1rows = coveritySnapshot(configs, secret, currentProject, snapshotid)

    snapshot0CIDs = dict()
    snapshot1CIDs = dict()
    for row in snapshot0rows:
        for parameter in row:
            if parameter['key'] == 'cid':
                snapshot0CIDs[parameter['value']] = 1
    for row in snapshot1rows:
        for parameter in row:
            if parameter['key'] == 'cid':
                snapshot1CIDs[parameter['value']] = 1

    eliminatedCIDs = []
    newCIDs = []
    for key in snapshot0CIDs:
        if key not in snapshot1CIDs:
            eliminatedCIDs.append(key)
    for key in snapshot1CIDs:
        if key not in snapshot0CIDs:
            newCIDs.append(key)

    utils.initEnv(configs['WORK_DIR'])
    if utils.hasEnv('BUILD_BRANCH'):
        buildBranch = utils.getEnv('BUILD_BRANCH')
        utils.saveEnv(configs['WORK_DIR'], '{}_COVCOMP_NEW_DEFECTS'.format(buildBranch), ','.join(newCIDs))
        utils.saveEnv(configs['WORK_DIR'], '{}_COVCOMP_ELIMINATED_DEFECTS'.format(buildBranch), ','.join(eliminatedCIDs))
    else:
        utils.saveEnv(configs['WORK_DIR'], 'COVCOMP_NEW_DEFECTS', ','.join(newCIDs))
        utils.saveEnv(configs['WORK_DIR'], 'COVCOMP_ELIMINATED_DEFECTS', ','.join(eliminatedCIDs))
    if configs['html_report'] == True:
        html = '<html>'
        html += '<body>'
        html += 'New Defects:'
        html += '<ul>'
        for newCID in newCIDs:
            # TODO: parentProject, currentProject
            issueURL = 'http://{}:{}/query/defects.htm?project={}&cid={}\n'.format(configs['host'], configs['port'], currentProject, newCID)
            html += '<li><a href="{}">{}</a></li>'.format(issueURL, newCID)
        html += '</ul>'
        html += 'Eliminated Defects:'
        html += '<ul>'
        for eliminatedCID in eliminatedCIDs:
            issueURL = 'http://{}:{}/query/defects.htm?project={}&cid={}\n'.format(configs['host'], configs['port'], currentProject, eliminatedCID)
            html += '<li><a href="{}">{}</a></li>'.format(issueURL, eliminatedCID)
        html += '</ul>'
        html += '</body>'
        html += '</html>'

        if os.path.isdir(os.path.join(configs['WORK_DIR'], 'covcomp-reports')) == False:
            os.makedirs(os.path.join(configs['WORK_DIR'], 'covcomp-reports'))
        fp = open(os.path.join(configs['WORK_DIR'], 'covcomp-reports', 'myreport.html'), "w")
        fp.write(html)
        fp.close()

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
    logging.basicConfig(filename=os.path.join(workDir, 'covcomp.log'), level=logging.DEBUG, filemode='w')
    utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir
    covComp(configs)

if __name__ == '__main__':
    main(sys.argv)