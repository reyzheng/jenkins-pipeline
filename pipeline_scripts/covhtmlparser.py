import os, re, glob, shutil
import utils

from pathlib import Path
from typing import Generator
from tree_sitter import Language, Node, Parser, Tree
import tree_sitter_cpp as ts_cpp
import tree_sitter_c as ts_c

class FileFunction:
    def __init__(self, idx_init, x_init, y_init):
        self.idx = idx_init
        self.filename = x_init
        self.functionname = y_init

class Point:
    def __init__(self, x_init, y_init):
        self.x = x_init
        self.y = y_init

def traverse_tree(tree: Tree) -> Generator[Node, None, None]:
    cursor = tree.walk()

    visited_children = False
    while True:
        if not visited_children:
            if cursor.node:
                yield cursor.node
            if not cursor.goto_first_child():
                visited_children = True
        elif cursor.goto_next_sibling():
            visited_children = False
        elif not cursor.goto_parent():
            break

def getSourceFileMap(filename):
    utils.lightLogging('getSourceFileMap: filename {}'.format(filename))
    functions = []

    if filename.endswith('.py'):
        import tree_sitter_python as ts_py
        language = Language(ts_py.language())
        parser = Parser(language)
    elif filename.endswith('.c'):
        language = Language(ts_c.language())
        parser = Parser(language)
    else:
        language = Language(ts_cpp.language())
        parser = Parser(language)

    tree = parser.parse(Path(filename).read_bytes())
    hasFunctionDefinition = False
    functionDeclaratorType = 'function_declarator'
    if filename.endswith('.py'):
        functionDeclaratorType = 'identifier'
    for node in traverse_tree(tree):
        #popen.lightLogging('getSourceFileMap: node {}'.format(node))
        if node.type == 'function_definition':
            #print(node.type, node.start_point, node.end_point)
            function = dict()
            function['start_point'] = node.start_point
            function['end_point'] = node.end_point
            hasFunctionDefinition = True
        if node.type == functionDeclaratorType:
            # to avoid pure function declaration
            if hasFunctionDefinition == True:
                function['declarator_start_point'] = node.start_point
                function['declarator_end_point'] = node.end_point
                functions.append(function)
                hasFunctionDefinition = False

    for i in range(len(functions)):
        for node in traverse_tree(tree):
            if node.type == 'identifier' and \
                node.start_point[0] >= functions[i]['declarator_start_point'][0] and \
                node.end_point[0] <= functions[i]['declarator_end_point'][0]:
                    functions[i]['identifier_start_point'] = node.start_point
                    functions[i]['identifier_end_point'] = node.end_point
                    break
    #popen.lightLogging('getSourceFileMap: {}'.format(functions))
    return functions

def htmlLineMatch(line):
    if line.startswith('<b><a name='):
        tokens = re.split(' |<|>', line)
        lineNumber = int(tokens[5])
    elif line.startswith('<pre><b><a name='):
        tokens = re.split(' |<|>', line)
        lineNumber = int(tokens[7])
    else:
        return -1
    return lineNumber

def deHtml(line):
    line = line.replace('&gt;', '>')
    line = line.replace('&lt;', '<')
    line = line.replace('&amp;', '&')
    line = line.replace('&quot;', '"')
    return line

def htmlToCpp(htmlFile):
    fpSource = open(htmlFile, 'r', encoding='utf-8', errors='replace')
    # remove .html suffix
    sourceFilename = htmlFile[:-5]
    if sourceFilename.endswith('.py'):
        tmpFilename = 'tmp.py'
    elif sourceFilename.endswith('.c'):
        tmpFilename = 'tmp.c'
    else:
        tmpFilename = 'tmp.cpp'
    utils.heavyLogging('htmlToCpp: output {}'.format(os.path.join(os.path.dirname(htmlFile), tmpFilename)))
    fpDst = open(os.path.join(os.path.dirname(htmlFile), tmpFilename), 'w', encoding='utf-8')
    while True:
        line = fpSource.readline()
        if not line:
            break
        if htmlLineMatch(line) > 0:
            htmlContent = line[line.find('\t') + 1:]
            htmlContent = deHtml(htmlContent)
            #htmlContent = htmlContent.replace('&gt;', '>')
            #htmlContent = htmlContent.replace('&lt;', '<')
            #htmlContent = htmlContent.replace('&amp;', '&')
            #htmlContent = htmlContent.replace('&quot;', '"')
            fpDst.write(htmlContent)
    fpSource.close()
    fpDst.close()
    sourceMap = getSourceFileMap(os.path.join(os.path.dirname(htmlFile), tmpFilename))
    os.remove(os.path.join(os.path.dirname(htmlFile), tmpFilename))
    return sourceMap

def parseEvents(htmlFile):
    fpHTML = open(htmlFile, 'r', encoding='utf-8', errors='replace')
    events = []
    while True:
        line = fpHTML.readline()
        if not line:
            break
        lineNumber = htmlLineMatch(line)
        if lineNumber > 0:
            exactLineNumber = lineNumber
        if line.startswith('<table summary='):
            events.append(exactLineNumber + 1)
    fpHTML.close()
    return events

def linesFunctionMatch(start, end, lines):
    retMatch = False
    for line in lines:
        if line >= start and line <= end:
            retMatch = True
            break
    return retMatch

# split 1/1_feature-1.c.html
# into 1/1-0_feature-1.c.html
# into 1/1-1_feature-1.c.html
# into 1/1-2_feature-1.c.html
# into 1/1-*_feature-1.c.html
# by events
def pruneHtmlReport(dir, trainingDir, lines):
    #fileFunctions = []
    utils.heavyLogging('pruneHtmlReport: report dir {}'.format(os.path.join(dir)))
    for htmlFile in glob.glob('{}/*'.format(os.path.join(dir))):
        htmlFileBasename = os.path.basename(htmlFile)
        bExpectedPrefix = bool(re.search(r'^([0-9]*[.])?[0-9]+_', htmlFileBasename))
        if bExpectedPrefix == False:
            splitIdx = re.search(r'^([0-9]*[.])?[0-9]+', htmlFileBasename).span()[1]
            htmlFileBasename_ = "{}_{}".format(htmlFileBasename[:splitIdx], htmlFileBasename[splitIdx:])
            htmlFile_ = os.path.join(os.path.dirname(htmlFile), htmlFileBasename_)
            utils.heavyLogging('pruneHtmlReport: normalize {} to {}'.format(htmlFile, htmlFile_))
            shutil.move(htmlFile, htmlFile_)
    utils.heavyLogging('pruneHtmlReport: search files in {}'.format(dir))
    for htmlFile in glob.glob('{}/*'.format(os.path.join(dir))):
        utils.heavyLogging('pruneHtmlReport: htmlFile {}'.format(htmlFile))
        htmlFileBasename = os.path.basename(htmlFile)
        underlineIndex = htmlFileBasename.index('_')
        sourceMap = htmlToCpp(htmlFile)
        # get the event lines
        events = parseEvents(htmlFile)
        utils.lightLogging('pruneHtmlReport: sourceMap {}'.format(sourceMap))
        utils.lightLogging('pruneHtmlReport: events {}'.format(events))

        capturedRows = []
        counter = 0
        for event in events:
            skipEvent = False
            for capturedRow in capturedRows:
                if event >= capturedRow.x and event <= capturedRow.y:
                    utils.heavyLogging('pruneHtmlReport: skip event line {}'.format(event))
                    skipEvent = True
            if skipEvent == True:
                continue
            prunedHtmlFile = os.path.join(trainingDir, '{}-{}_{}'.format(htmlFileBasename[:underlineIndex], counter, htmlFileBasename[underlineIndex + 1:]))
            exactLineNumber = -1
            for function in sourceMap:
                utils.lightLogging('pruneHtmlReport: test event {}, function {}/{}'.format(event, function['start_point'], function['end_point']))
                if event >= (function['start_point'][0] + 1) and event <= (function['end_point'][0] + 1) and \
                        linesFunctionMatch(function['start_point'][0] + 1, function['end_point'][0] + 1, lines):
                    utils.heavyLogging('pruneHtmlReport: prune {} -> {}'.format(htmlFile, prunedHtmlFile))
                    fpHtmlPruned = open(prunedHtmlFile, 'w', encoding='utf-8')
                    fpHtmlPruned.write('<pre>')
                    counter = counter + 1
                    fpHtml = open(htmlFile, 'r', encoding='utf-8', errors='replace')
                    captureLine = False
                    while True:
                        line = fpHtml.readline()
                        if not line:
                            break
                        lineNumber = htmlLineMatch(line)
                        if lineNumber > 0:
                            exactLineNumber = lineNumber
                        if exactLineNumber >= (function['start_point'][0] + 1) and exactLineNumber <= (function['end_point'][0] + 1):
                            captureLine = True
                        else:
                            captureLine = False
                        if captureLine == True:
                            linePruned = re.sub(r'<b><a name="line.*">.*</a></b>', '', line)
                            fpHtmlPruned.write(linePruned)
                        if lineNumber > 0  and \
                                exactLineNumber >= (function['identifier_start_point'][0] + 1) and \
                                exactLineNumber <= (function['identifier_end_point'][0] + 1):
                            # funtion identifier
                            htmlContent = line[line.find('\t') + 1:]
                            htmlContent = deHtml(htmlContent)
                            functionName = htmlContent[function['identifier_start_point'][1]:function['identifier_end_point'][1]]
                            fileName = os.path.basename(htmlFile)
                            # remove leading index, like 1_, 2_, 1.0_ ...
                            # remove ".html"
                            fileName = fileName[:-5]
                            utils.heavyLogging('pruneHtmlReport: fileName {}, functionName {}'.format(fileName, functionName))
                    fpHtmlPruned.write('</pre>')
                    fpHtml.close()
                    fpHtmlPruned.close()
                    row = Point(function['start_point'][0] + 1, function['end_point'][0] + 1)
                    capturedRows.append(row)
                    break
    return

def coverityAnalysisAdviseParser(file):
    exception = False
    captureCoverityAnalysisResult = False
    captureAdvise = False
    captureReasoning = False
    coverityAnalysisResult = []
    adviseResult = []
    reasoningResult = []
    fpYaml = open(file, 'r')
    while True:
        line = fpYaml.readline()
        if not line or line.rstrip() == '```':
            # skip ending line ```
            break
        if line.startswith('exception:'):
            # exception, timeout
            exception = True
            break
        elif re.match(r'^ +file:', line):
            filename = line.split(':')[1].strip()
        elif re.match(r'^ +original_analysis:', line):
            captureCoverityAnalysisResult = True
        elif re.match(r'^ +advise:', line):
            captureAdvise = True
        elif re.match(r'^ +reasoning:', line):
            captureReasoning = True
        if captureReasoning == True:
            reasoningResult.append(line)
        elif captureAdvise == True:
            adviseResult.append(line)
        elif captureCoverityAnalysisResult == True:
            coverityAnalysisResult.append(line)
    coverityAnalysisResult.append('</pre>\n')
    fpYaml.close()
    try:
        coverityAnalysisResult.pop(0)
        adviseResult.pop(0)
        reasoningResult.pop(0)
    except:
        # exception result by timeout, maybe
        utils.heavyLogging('coverityAnalysisAdviseParser: yaml parsing failure {}'.format(file))
        pass

    result = dict()
    if exception == True:
        result['status'] = 'failure'
    else:
        result['status'] = 'success'
        result['filename'] = filename
        result['coverityAnalysis'] = ''.join(coverityAnalysisResult)
        result['advise'] = ''.join(adviseResult)
        result['reasoning'] = ''.join(reasoningResult)

    return result