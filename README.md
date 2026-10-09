# Implementation documentation for 1. assignment of IPP 2024/2025

First name and last name: Rastislav Uhliar
Login: xuhliar00

## Introduction

This document explains the implementation of the parse.py script. The script reads source code written in SOL25 and uses lark library to generate a parser from the grammar. The script then checks the parse tree for semantic errors and converts the parse tree into an Abstract Syntax Tree, that is then transformed into XML representation. The script works for some basic cases but doesn't handle undefined classes and variables as well as inherance.

## Transforming parse tree into Abstract Syntax Tree

The parse tree is transformed using the SOLTransformer class that implements methods that correspond to the grammar rules. It transforms the nodes from the parse tree into nodes in the Abstract Syntax Tree.

## Transforming Abstract Syntax Tree into XML

The AST is transformed into XML using the ast_to_xml function that recursively goes through the AST and generates corresponding XML elements. Comments in the source code are extracted from the source file and then passed to the function as description argument. The escape_xml function handles escape sequences but i had problems with it and implemented a workaround, which is not the best solution and might not work in all the cases. The problem that i had was when there was new line character in the comment, it would first transform the \n into "&#10;" but then it would transform the "&" character in this string into its equivalent "&amp;". So i fixed it by replacing it with "" empty string.

## Handling errors

The script performs basic semantic analysis in check_semantics function. It does not work great with undefined classes and class methods, but i was able to detect at least some of the errors. Lexical and syntax errors are checked with the lark library.

## Conclusion
The scrip parses source code wirrent in SOL25, check for errors and generates XML representation. However there are still some areas that could be improved.
