import os
import getopt, sys
import json
import base64
import subprocess as sb

configs = dict()

def checkJIRACredentials():
    if "JIRA_TOKEN" not in os.environ:
        sys.exit("Environmental variable JIRA_TOKEN not defined")

def checkGerritEvents():
    requiredVars = ['GERRIT_EVENT_TYPE', 'GERRIT_CHANGE_SUBJECT']
    for requiredVar in requiredVars:
        if requiredVar not in os.environ:
            sys.exit('Environmental variable {} not defined'.format(requiredVar))

def jiraAddComments(message):
    # parse GERRIT_CHANGE_SUBJECT to get jira issue key
    GERRIT_CHANGE_SUBJECT = os.getenv('GERRIT_CHANGE_SUBJECT')
    tokens = GERRIT_CHANGE_SUBJECT.split(":")
    issueId = tokens[0]
    # 
    global configs
    comment = dict()
    comment['body'] = message
    with open('comment.json', 'w') as fp:
        json.dump(comment, fp)
    if "JIRA_USER" in os.environ:
        cmdCurl = sb.Popen(['curl', '-s', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue/{}/comment'.format(configs['jira_site'], issueId), \
                        '-u', '{}:{}'.format(os.getenv('JIRA_USER'), os.getenv('JIRA_TOKEN')), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@comment.json'], stdout=sb.PIPE)
    else:
        cmdCurl = sb.Popen(['curl', '-s', '-X', 'POST', '--url', \
                        'https://{}/rest/api/2/issue/{}/comment'.format(configs['jira_site'], issueId), \
                        '-H', 'Authorization: Bearer {}'.format(os.getenv('JIRA_TOKEN')), \
                        '-H', 'Content-Type: application/json', \
                        '-H', 'Accept: application/json', '--data', '@comment.json'], stdout=sb.PIPE)
    cmdCurl.wait()
    print('ITSJIRA: comment {}, {}'.format(issueId, message))

def addJIRAComments():
    #[rule "open"]
    #    event-type = patchset-created
    #    action = add-standard-comment
    #    action = In Progress
    #[rule "resolve"]
    #    event-type = comment-added
    #    approvalCodeReview = 2
    #    action = add-standard-comment
    #    action = In Review
    #[rule "merged"]
    #    event-type = change-merged
    #    action = add-standard-comment
    #    action = Done
    #[rule "abandoned"]
    #    event-type = change-abandoned
    #    action = add-standard-comment
    #    action = To Do    checkJIRACredentials()
    checkGerritEvents()
    gerritEvent = os.getenv('GERRIT_EVENT_TYPE')
    if len(configs['events']) > 0 and gerritEvent not in configs['events']:
        print('ITSJIRA: ignore GERRIT_EVENT_TYPE {}'.format(gerritEvent))
        return
    print('ITSJIRA: got gerrit event {}'.format(gerritEvent))
    if gerritEvent == 'patchset-created':
        comment = 'Change {} uploaded by {}.\n'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_CHANGE_OWNER_NAME'))
        comment = comment + 'Subject:\n'
        comment = comment + '{}\n'.format(os.getenv('GERRIT_CHANGE_SUBJECT'))
        comment = comment + 'See [here|{}]'.format(os.getenv('GERRIT_CHANGE_URL'))
    elif gerritEvent == 'comment-added':
        text = base64.b64decode(os.getenv('GERRIT_EVENT_COMMENT_TEXT')).decode("utf-8")
        comment = 'Change {} Recieved {}. See [here|{}]'.format(os.getenv('GERRIT_CHANGE_NUMBER'), text, os.getenv('GERRIT_CHANGE_URL'))
    elif gerritEvent == 'change-abandoned':
        comment = 'Change {} Abandoned by {}. See [here|{}]'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_CHANGE_ABANDONER_NAME'), os.getenv('GERRIT_CHANGE_URL'))
    elif gerritEvent == 'change-merged':
        comment = 'Change {} Merged by {}. See [here|{}]'.format(os.getenv('GERRIT_CHANGE_NUMBER'), os.getenv('GERRIT_EVENT_ACCOUNT_NAME'), os.getenv('GERRIT_CHANGE_URL'))
    elif gerritEvent == 'custom-message':
        text = os.getenv('PF_ITSJIRA_CUSTOM_MESSAGE')
        comment = '{}'.format(text)
    jiraAddComments(comment)

def main(argv):
    global configs

    try:
        opts, args = getopt.getopt(argv[1:], 'w:f:c:v', ["work_dir=", "config=", "command=", "version"])
    except getopt.GetoptError:
        sys.exit()

    command = "MAIN"
    configFile = ''
    workDir = os.getcwd()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-c', '--command'):
            # override if --user
            command = value
        elif name in ('-f', '--config'):
            configFile = value
        elif name in ('-d', '--defects_dir'):
            defectsDir = os.path.abspath(value)
        elif name in ('-w', '--work_dir'):
            if os.path.exists(value) == False:
                os.mkdir(value)
            workDir = value

    with open(configFile) as f:
        configs = json.load(f)
    f.close()

    workDir = os.path.abspath(workDir)
    os.chdir(workDir)
    if command == "MAIN":
        addJIRAComments()
        sys.exit(0)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main(sys.argv)