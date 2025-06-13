import os, logging, fnmatch, shutil
import json
import urllib.parse
import getopt, sys
import utils

def getAuthPieces():
    authPieces = []
    if 'WIKI_TOKEN' in os.environ:
        authPieces = ['-H', 'Authorization: Bearer {}'.format(os.getenv('WIKI_TOKEN'))]
    elif 'WIKI_USER' in os.environ:
        authPieces = ['--user', '{}:{}'.format(os.getenv('WIKI_USER'), os.getenv('WIKI_PASSWORD'))]
    return authPieces

def downloadAttachment(configs):
    authPieces = getAuthPieces()
    #cql=type=page and title~"Confluence API" and space="RDCPSP"
    cql = 'type=page'
    if configs['title'] != '':
        cql += ' and title~"{}"'.format(configs['title'])
    if configs['space'] != '':
        cql += ' and space="{}"'.format(configs['space'])
    utils.popenWithStdout(['curl', '-k', '-s', '--url', \
                        'https://{}/rest/api/content/search?cql={}'.format(configs['wiki_site'], urllib.parse.quote(cql)), \
                        '-H', 'Accept: application/json', '-o', os.path.join(configs['WORK_DIR'], 'contents.json')] + authPieces, dict(os.environ))
    with open(os.path.join(configs['WORK_DIR'], 'contents.json'), 'r', encoding='utf-8') as fpContents:
        contents = json.load(fpContents)
    if contents['size'] == 0:
        utils.heavyLogging('downloadAttachment: search error')
        sys.exit(-1)
    utils.heavyLogging('downloadAttachment: page {}({})'.format(contents['results'][0]['title'], contents['results'][0]['id']))
    utils.popenWithStdout(['curl', '-k', '-s', '--url', \
                        'https://{}/rest/api/content/{}/child/attachment'.format(configs['wiki_site'], contents['results'][0]['id']), \
                        '-H', 'Accept: application/json', '-o', os.path.join(configs['WORK_DIR'], 'attachment.json')] + authPieces, dict(os.environ))
    with open(os.path.join(configs['WORK_DIR'], 'attachment.json'), 'r', encoding='utf-8') as fpAttachment:
        attachment = json.load(fpAttachment)
    if attachment['size'] == 0:
        utils.heavyLogging('downloadAttachment: attachment error')
        sys.exit(-2)
    if configs['dst'] != '' and os.path.isdir(configs['dst']) == False:
        utils.makeEmptyDirectory(configs['dst'])
    attachments = configs['attachments'].split(',')
    for result in attachment['results']:
        downloadLink = result['_links']['download']
        filename = result['title']
        utils.heavyLogging('downloadAttachment: filename {}'.format(filename))
        match = False
        if len(attachments) > 0:
            for attachment in attachments:
                if fnmatch.fnmatch(filename, attachment):
                    match = True
                    break
        else:
            match = True
        if match == True:
            utils.popenWithStdout(['curl', '-k', '-s', '--url', \
                            'https://{}{}'.format(configs['wiki_site'], downloadLink), \
                            '-o', os.path.join(configs['WORK_DIR'], filename)] + authPieces, dict(os.environ))
            shutil.move(os.path.join(configs['WORK_DIR'], filename), os.path.join(configs['dst'], filename))
        else:
            utils.heavyLogging('downloadAttachment: filename {}(skip)'.format(filename))

def main(argv):
    skipTranslate = False

    try:
        opts, args = getopt.getopt(argv[1:], 'c:w:f:v', ["command", "work_dir=", "config=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-w', '--work_dir'):
            if os.path.isdir(value) == False:
                os.makedirs(value)
            workDir = value
        elif name in ('-c', '--command'):
            command = value

    logging.basicConfig(filename=os.path.join(workDir, 'action.log'), format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, filemode='w')
    if skipTranslate == False:
        utils.translateConfig(configFile)
    configs = utils.loadConfigs(configFile)
    configs['WORK_DIR'] = workDir
    if configs['enable'] == False:
        print('main: skip wiki action')
        sys.exit(0)
    if command == 'DOWNLOAD_ATTACHMENT':
        downloadAttachment(configs)

if __name__ == "__main__":
    main(sys.argv)