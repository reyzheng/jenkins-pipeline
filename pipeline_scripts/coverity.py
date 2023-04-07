#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import getopt, sys
import subprocess as sb

def getDiffFiles(src):
    os.chdir(src)
    # git log --format=\"%H\" -n 2
    commitIds = []
    cmdCommitIds = sb.Popen(['git', 'log', '--format=\"%H\"', '-n', '2'], stdout=sb.PIPE)
    while True:
        line = cmdCommitIds.stdout.readline()
        if not line:
            break
        commitIds.append(line.decode("utf-8") .strip()[1:-1])

    cmdDiffs = sb.Popen(['git', 'diff', '--submodule=diff', '{}..{}'.format(commitIds[1], commitIds[0])], stdout=sb.PIPE)
    if os.name == "posix":
        nameDiffs = sb.check_output(('grep', 'diff --git'), stdin=cmdDiffs.stdout)
    else:
        nameDiffs = sb.check_output(('findstr', '/l', 'diff --git'), stdin=cmdDiffs.stdout)
    cmdDiffs.wait()
    lines = nameDiffs.decode("utf-8").splitlines()
    for line in lines:
        tokens = line.split()
        print("file('{}')".format(tokens[3][2:]))

def manageEmitDB(src, idir, covdir):
    os.chdir(src)
    pwd = os.getcwd()
    covCmd = covdir + "cov-manage-emit"
    tuList = sb.Popen([covCmd, '--dir', idir, 'list'], stdout=sb.PIPE)
    while True:
        line = tuList.stdout.readline()
        if not line:
            break
        if line[0].isdigit():
            tokens = line.split()
            dir = os.path.dirname(os.path.abspath(tokens[2]))
            filename = os.path.basename(tokens[2])
            os.chdir(dir)
            cmdLog = sb.Popen(['git', 'log' ,'--committer=realtek', '--committer=realsil', '--format=', '--name-only', '--no-merges', 'HEAD', '{}'.format(filename)], stdout=sb.PIPE)
            if os.name == "posix":
                uniqOutput = sb.check_output(('uniq'), stdin=cmdLog.stdout)
            else:
                uniqOutput = sb.check_output(('sort', '/unique'), stdin=cmdLog.stdout)
            cmdLog.wait()
            uniqLines = uniqOutput.decode("utf-8").splitlines()
            if len(uniqLines) == 0 or uniqLines[0] == "":
                # not realtek/realsil edited
                print("cov-manage-emit delete {}".format(tokens[2]))
                sb.Popen([covCmd, '--dir', idir, '-tp=file(\'{}\')'.format(tokens[2]), 'delete'], stdout=sb.PIPE)
    os.chdir(pwd)

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'e:c:s:i:v', ["coverity=", "command=", "source=", "idir=", "version"])
    except getopt.GetoptError:
        sys.exit()

    COVDIR = ""
    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-c', '--command'):
            COMMAND = value
        elif name in ('-s', '--source'):
            SRC = value
        elif name in ('-i', '--idir'):
            IDIR = value
        elif name in ('-e', '--coverity'):
            COVDIR = value

    if COMMAND == "PF_DIFF_PREV":
        getDiffFiles(SRC)
    elif COMMAND == "PF_RTK_ONLY":
        manageEmitDB(SRC, IDIR, COVDIR)

if __name__ == '__main__':
    main(sys.argv)
