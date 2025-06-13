from pathlib import Path
from typing import Generator
from tree_sitter import Language, Node, Parser, Tree
import tree_sitter_cpp as ts_cpp
import tree_sitter_c as ts_c
import os
import utils

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

def getSourceFileMap(sourceDir, filename):
    utils.lightLogging('getSourceFileMap: filename {}'.format(filename))
    functions = []

    if filename.endswith('.py'):
        import tree_sitter_python as ts_python
        try:
            language = Language(ts_python.language())
            parser = Parser(language)
        except:
            language = Language(ts_python.language(), 'python')
            parser = Parser()
            parser.set_language(language)
    elif filename.endswith('.c'):
        try:
            language = Language(ts_c.language())
            parser = Parser(language)
        except:
            language = Language(ts_c.language(), 'c')
            parser = Parser()
            parser.set_language(language)
    else:
        try:
            language = Language(ts_cpp.language())
            parser = Parser(language)
        except:
            language = Language(ts_cpp.language(), 'cpp')
            parser = Parser()
            parser.set_language(language)

    tree = parser.parse(Path(os.path.join(sourceDir, filename)).read_bytes())
    hasFunctionDefinition = False
    for node in traverse_tree(tree):
        #popen.lightLogging('getSourceFileMap: node {}'.format(node))
        if node.type == 'function_definition' or node.type == 'class_specifier':
            #print(node.type, node.start_point, node.end_point)
            function = dict()
            function['start_point'] = node.start_point
            function['end_point'] = node.end_point
            function['type'] = node.type
            hasFunctionDefinition = True
        if node.type == 'function_declarator' or node.type == 'class':
            # to avoid pure function declaration
            if hasFunctionDefinition == True:
                function['declarator_start_point'] = node.start_point
                function['declarator_end_point'] = node.end_point
                functions.append(function)
                hasFunctionDefinition = False

    for i in range(len(functions)):
        if functions[i]['type'] == 'function_definition':
            # function_definition
            identifierToCompare = 'identifier'
        else:
            # class_specifier
            identifierToCompare = 'type_identifier'
        for node in traverse_tree(tree):
            if node.type == identifierToCompare and \
                node.start_point[0] >= functions[i]['declarator_start_point'][0] and \
                node.end_point[0] <= functions[i]['declarator_end_point'][0]:
                    functions[i]['identifier_start_point'] = node.start_point
                    functions[i]['identifier_end_point'] = node.end_point
                    break

    for i in range(len(functions)):
        functionRow = functions[i]['identifier_start_point'][0]
        idx = 0
        with open(os.path.join(sourceDir, filename)) as fp:
            while True:
                line = fp.readline()
                if not line:
                    break
                if idx == functionRow:
                    identifier = line[functions[i]['identifier_start_point'][1]:functions[i]['identifier_end_point'][1]]
                    functions[i]['identifier'] = identifier
                    break
                idx = idx + 1

    #popen.lightLogging('getSourceFileMap: {}'.format(functions))
    return functions
