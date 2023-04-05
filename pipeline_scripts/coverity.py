#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import getopt, sys
import subprocess as sb

def getDiffFiles(src):
    os.chdir(src)
    # git log --format=\"%H\" -n 2
    commitIds = []
    cmdCommitIds = sb.Popen(['git', 'log' ,'--format=\"%H\"', '-n', '2'], stdout=sb.PIPE)
    while True:
        line = cmdCommitIds.stdout.readline()
        if not line:
            break
        commitIds.append(line.decode("utf-8") .strip()[1:-1])

    cmdDiffs = sb.Popen(['git', 'diff' ,'--submodule=diff', '{}..{}'.format(commitIds[1], commitIds[0])], stdout=sb.PIPE)
    if os.name == "posix":
        nameDiffs = sb.check_output(('grep', 'diff --git'), stdin=cmdDiffs.stdout)
    else:
        nameDiffs = sb.check_output(('findstr', '/l', 'diff --git'), stdin=cmdDiffs.stdout)
    cmdDiffs.wait()
    lines = nameDiffs.decode("utf-8").splitlines()
    for line in lines:
        tokens = line.split()
        print("file('{}')".format(tokens[3][2:]))

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'c:s:v', ["command=", "source=", "version"])
    except getopt.GetoptError:
        sys.exit()

    for name, value in opts:
        if name in ('-v', '--version'):
            print("0.1")
            sys.exit(0)
        elif name in ('-c', '--command'):
            COMMAND = value
        elif name in ('-s', '--source'):
            SRC = value

    if COMMAND == "PF_DIFF_PREV":
        getDiffFiles(SRC)

if __name__ == '__main__':
    main(sys.argv)
