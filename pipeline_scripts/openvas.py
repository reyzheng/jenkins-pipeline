# Reference: https://github.com/greenbone/gvm-tools/tree/main/scripts
#            https://python-gvm.readthedocs.io/en/latest/api/gmpv224.html
from gvm.connections import UnixSocketConnection
from gvm.protocols.gmp import Gmp
from gvm.transforms import EtreeTransform
from gvm.xml import pretty_print
from base64 import b64decode
from pathlib import Path
import gvm
import getopt, sys

def pdfReport(taskName):
    socket = '/k8s/openvas/gvmd-socket-vol/gvmd.sock'
    connection = gvm.connections.UnixSocketConnection(path=socket)
    transform = EtreeTransform()
    with Gmp(connection, transform=transform) as gmp:
        # Login
        gmp.authenticate('admin', 'admin')
        # Retrieve all reports
        reports = gmp.get_reports(filter_string=taskName)
        # Get names, uuid of reports
        report_names = reports.xpath('report/name/text()')
        report_ids = reports.xpath('report/@id')
        if (len(report_names) == 0):
            print('Invalid task: {}'.format(taskName))
            return
        else:
            # get latest report
            reportName = report_names[-1]
            reportId = report_ids[-1]
            pdf_report_format_id = "c402cc3e-b531-11e1-9163-406186ea4fc5"
            response = gmp.get_report(
                report_id=reportId, report_format_id=pdf_report_format_id
            )
            report_element = response.find("report")
            content = report_element.find("report_format").tail
            if not content:
                print(
                    "Requested report is empty. Either the report does not contain any "
                    " results or the necessary tools for creating the report are "
                    "not installed.",
                    file=sys.stderr,
                )
                sys.exit(2)
            # convert content to 8-bit ASCII bytes
            binary_base64_encoded_pdf = content.encode("ascii")
            # decode base64
            binary_pdf = b64decode(binary_base64_encoded_pdf)
            # write to file and support ~ in filename path
            pdf_path = Path(reportId + '.pdf').expanduser()
            pdf_path.write_bytes(binary_pdf)
            print("Done. {} PDF created: {}".format(taskName, pdf_path))
        #gmp.start_task(task_ids[0])
        #print('Start task: {}({})'.format(taskName, task_ids[0]))

def taskStatus(taskName):
    socket = '/k8s/openvas/gvmd-socket-vol/gvmd.sock'
    connection = gvm.connections.UnixSocketConnection(path=socket)
    transform = EtreeTransform()
    with Gmp(connection, transform=transform) as gmp:
        # Login
        gmp.authenticate('admin', 'admin')
        # Retrieve all tasks
        tasks = gmp.get_tasks(filter_string=taskName)
        # Get names, uuid of tasks
        task_names = tasks.xpath('task/name/text()')
        if (len(task_names) == 0):
            print('Invalid task: {}'.format(taskName))
            return
        else:
            taskName = task_names[0]
            taskStatus = tasks.xpath("task/status/text()")
            print('Task {}, status: {}'.format(taskName, taskStatus[0]))

def startTask(taskName):
    socket = '/k8s/openvas/gvmd-socket-vol/gvmd.sock'
    connection = gvm.connections.UnixSocketConnection(path=socket)
    transform = EtreeTransform()
    with Gmp(connection, transform=transform) as gmp:
        # Login
        gmp.authenticate('admin', 'admin')
        # Retrieve all tasks
        tasks = gmp.get_tasks(filter_string=taskName)
        # Get names, uuid of tasks
        task_names = tasks.xpath('task/name/text()')
        if (len(task_names) == 0):
            print('Invalid task: {}'.format(taskName))
            return
        else:
            taskName = task_names[0]
        task_ids = tasks.xpath('task/@id')
        gmp.start_task(task_ids[0])
        print('Start task: {}({})'.format(taskName, task_ids[0]))

def main(argv):
    #workDir = '.pf-covanalyze'
    command = ""
    taskName = ""
    try:
        opts, args = getopt.getopt(argv[1:], 'c:t:v', ["command=", "task=", "version"])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-c', '--command'):
            command = value
        elif name in ('-t', '--task'):
            taskName = value
    if taskName == "":
        print("Please specify task name")
        sys.exit(1)
    if command == "start-task":
        startTask(taskName)
    elif command == "task-status":
        taskStatus(taskName)
    elif command == "pdf-report":
        pdfReport(taskName)
    else:
        print('Invalid command')

if __name__ == "__main__":
    main(sys.argv)