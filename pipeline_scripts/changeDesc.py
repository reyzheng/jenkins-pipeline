import json
import jira

queryParams = dict()
queryParams['project'] = 'DHCCOVERIT'
queryParams['issuetype'] = 'Issue'
with open("queryParams.json", "w") as outfile:
    json.dump(queryParams, outfile)
#jira.queryIssues('queryParams.json')

with open('issues.json') as f:
    issues = json.load(f)
for issue in issues:
    if issue['fields']['description'].startswith("http://172.21.15.146:8080"):
        print(issue['key'])
        lines = issue['fields']['description'].splitlines()
        cutIdx = lines[0].rfind("=")
        CID = lines[0][cutIdx + 1:]
        print(CID)
        lines[0] = "http://coverity.rtkbf.com:8080/#/project-view/10656/10489?selectedIssue=" + CID
        print(lines[0])
        print()        