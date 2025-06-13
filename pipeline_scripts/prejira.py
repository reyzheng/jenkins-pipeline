import sys, glob, os, re, zipfile, getopt
import utils

def errorPreJIRA(json_files, zip_files):
    utils.heavyLogging('errorPreJIRA: unexcepted condition')
    utils.heavyLogging('errorPreJIRA: json_files {}'.format(json_files))
    utils.heavyLogging('errorPreJIRA: zip_files {}'.format(zip_files))
    sys.exit(-1)

def unzipCoverityDetailedHtmlReport(branches, workDir):
    utils.saveEnv(workDir, 'PF_CODEPROMPT_RESULT', 'PF_CODEPROMPT_RESULTS')
    utils.saveEnv(workDir, 'PF_CODETEK_COV_ANALYSIS_ADVISE', '1')
    if len(branches) == 0:
        with zipfile.ZipFile('coverityDetailedHtmlReport.zip', 'r') as zip_ref:
            zip_ref.extractall(os.path.join(workDir, 'coverityDetailedHtmlReport'))
        utils.saveEnv(workDir, 'PF_COV_DETAILED_HTML_REPORT_DIR', os.path.join(os.getenv('WORKSPACE'), workDir, 'coverityDetailedHtmlReport'))
    else:
        for branch in branches:
            with zipfile.ZipFile('coverityDetailedHtmlReport-{}.zip'.format(branch), 'r') as zip_ref:
                zip_ref.extractall(os.path.join(workDir, 'coverityDetailedHtmlReport-{}'.format(branch)))
        utils.saveEnv(workDir, 'BR{}_PF_COV_DETAILED_HTML_REPORT_DIR'.format(branch), os.path.join(os.getenv('WORKSPACE'), workDir, 'coverityDetailedHtmlReport-{}'.format(branch)))

def find_specific_files(root_dir, workDir):
    """
    Find all files matching:
    - "preview-report-committer*.json"
    - "coverityDetailedHtmlReport*.zip"
    Returns list of full file paths.
    """
    json_files = glob.glob(os.path.join(root_dir, "preview-report-committer*.json"), recursive=True)
    zip_files = glob.glob(os.path.join(root_dir, "coverityDetailedHtmlReport*.zip"), recursive=True)

    codetekCheck = False
    if len(zip_files) > 0:
        codetekCheck = True
        if len(zip_files) != len(json_files):
            errorPreJIRA(json_files, zip_files)

    if len(json_files) == 1 and json_files[0] == 'preview-report-committer.json':
        fpArtifacts = open(os.path.join(workDir, '.artifacts'), 'a')
        fpArtifacts.write('WORKSPACE:preview-report-committer.json,')
        fpArtifacts.close()
        if codetekCheck == True:
            unzipCoverityDetailedHtmlReport([], workDir)
    elif len(json_files) > 0:
        branches = []
        fpArtifacts = open(os.path.join(workDir, '.artifacts'), 'a')
        for json_file in json_files:
            fpArtifacts.write('WORKSPACE:{},'.format(os.path.basename(json_file)))
            match = re.search(r'preview-report-committer-(.*?)\.json', json_file)
            if match:
                branch = match.group(1)
                branches.append(branch)
        fpArtifacts.close()
        utils.saveEnv(workDir, 'PF_GLOBAL_PARALLELINFO', '1')
        utils.saveEnv(workDir, 'UPSTREAM_BRANCHES', ','.join(branches))
        if codetekCheck == True:
            codetekBranches = []
            for zip_file in zip_files:
                match = re.search(r'coverityDetailedHtmlReport-(.*?)\.zip', zip_file)
                if match:
                    branch = match.group(1)
                    codetekBranches.append(branch)
            if sorted(codetekBranches) != sorted(branches):
                errorPreJIRA(json_files, zip_files)
            unzipCoverityDetailedHtmlReport(codetekBranches, workDir)
    else:
        errorPreJIRA(json_files, zip_files)

    return

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'w:f:v', ["work_dir=", "config=", "version"])
    except getopt.GetoptError:
        print('Invalid options')
        sys.exit()

    configFile = ''
    workDir = os.getcwd()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            if os.path.exists(value) == False:
                os.mkdir(value)
            workDir = value

    utils.cleanEnvAndArchives(workDir)
    find_specific_files('.', workDir)

if __name__ == "__main__":
    main(sys.argv)