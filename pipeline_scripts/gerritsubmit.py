import os, logging, shutil
import json
import getopt, sys
import subprocess as sb
import utils

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
    # get coverity project
    try:
        url = "http://{}:{}/api/v2/streams/{}?locale=en_us".format(configs["coverity_host"], configs["coverity_port"], stream)
        cmdCurl = sb.Popen(['curl', '-X', 'GET', url, '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--user', '{}:{}'.format(covuser, covkey), \
                        '-o', os.path.join(configs['WORK_DIR'], 'covProjectInfo.json')], stdout=sb.PIPE)
        cmdCurl.wait()
    except:
        return ''
    if os.path.isfile(os.path.join(configs['WORK_DIR'], 'covProjectInfo.json')):
        fpInfo = open(os.path.join(configs['WORK_DIR'], 'covProjectInfo.json'))
        jsonInfo = json.load(fpInfo)
        fpInfo.close()
        return jsonInfo["streams"][0]["primaryProjectName"]
    else:
        return ''

def gerritSubmit(configs):
    cmdEnv = dict(os.environ)
    if configs['comment'] == 'COV_INFO':
        if 'BUILD_BRANCH' in os.environ:
            defectsCount = os.getenv('{}_COV_COUNT'.format(os.getenv('BUILD_BRANCH')))
        else:
            defectsCount = os.getenv('COV_COUNT')

        if defectsCount == '0':
            #cmd = "ssh -p 29418 $GERRIT_HOST gerrit review -m '\"Pass\"' $GERRIT_CHANGE_NUMBER,$GERRIT_PATCHSET_NUMBER"
            utils.popenReturnStdout(['ssh', '-p', '29418', os.getenv('GERRIT_HOST'), \
                                     'gerrit', 'review', '-m', 'Pass', \
                                     '{},{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_PATCHSET_NUMBER'))], cmdEnv)
        else:
            if "COV_AUTH_KEY" not in os.environ:
                sys.exit("Environment variable COV_AUTH_KEY not defined")
            with open(os.getenv('COV_AUTH_KEY')) as f:
                keyObj = json.load(f)
            if 'BUILD_BRANCH' in os.environ:
                stream = os.getenv('{}_COV_STREAM'.format(os.getenv('BUILD_BRANCH')))
            else:
                stream = os.getenv('COV_STREAM')
            # python gerritsubmit.py -c COV_INFO -s $SNAPSHOT_ID

            covProject = retrieveProjectInfo(configs, keyObj['username'], keyObj['key'], stream)
            cids = retrievePreviewReport(configs)
            covInfo = dict()
            if len(cids) == 0:
                covInfo["message"] = "Pass"
            else:
                if covProject == '':
                    covInfo["message"] = "Total defects: {}, CIDs: {}, http://{}:{}".format(len(cids), ','.join(cids), configs["coverity_host"], configs["coverity_port"])
                else:
                    covInfo["message"] = "Total defects: {}, CIDs: {}\n".format(len(cids), ','.join(cids))
                    for cid in cids:
                        covInfo["message"] += "http://{}:{}/query/defects.htm?project={}&cid={}\n".format(configs["coverity_host"], configs["coverity_port"], covProject, cid)
            with open(os.path.join(configs['WORK_DIR'], '.covinfo'), "w") as fp:
                json.dump(covInfo, fp)

            if os.name == 'posix':
                catProcess = sb.Popen(['cat', os.path.join(configs['WORK_DIR'], '.covinfo')], stdout=sb.PIPE)
            else:
                catProcess = sb.Popen(['type', os.path.join(configs['WORK_DIR'], '.covinfo')], stdout=sb.PIPE)
            sshProcess = sb.Popen(['ssh', '-p', '29418', os.getenv('GERRIT_HOST'), 'gerrit', 'review', \
                                    '-j', '{},{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_PATCHSET_NUMBER'))], \
                                    stdin=catProcess.stdout, stdout=sb.PIPE)
            catProcess.stdout.close() # enable write error in dd if ssh dies
            out, err = sshProcess.communicate()
            if sshProcess.returncode != 0:
                sys.exit(sshProcess.returncode)
    else:
        # user defined comments
        utils.popenWithStdout(['ssh', '-p', '29418', os.getenv('GERRIT_HOST'), 'gerrit', 'review', \
                                '-m', configs['comment'], \
                                '{}:{}'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_PATCHSET_NUMBER'))], cmdEnv)

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
    
    if os.path.isdir(workDir) == True:
        shutil.rmtree(workDir)
    os.makedirs(workDir)
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
    gerritSubmit(configs)

if __name__ == "__main__":
    main(sys.argv)