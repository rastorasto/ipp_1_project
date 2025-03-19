# Author: Rastislav Uhliar
# xlogin: xuhliar00
import sys

# Handling command line arguments
if len(sys.argv) > 1:
    if len(sys.argv) > 2:
        sys.stderr.write("Error: Too many arguments\n")
        sys.exit(10)
    
    # Check for help argument
    arg = sys.argv[1]
    if arg not in ['-h', '--help']:
        sys.stderr.write("Error: Invalid argument\n")
        sys.exit(10)
    
    print("Usage: parse.py [-h | --help]")
    print("Parse SOL25 code from standard input and output XML representation of the code")
    sys.exit(0)


from lark import Lark, Transformer, UnexpectedCharacters, UnexpectedToken
import xml.etree.ElementTree as ET
import re
from xml.dom import minidom

grammar = r"""
    start: program
    program: class_def*
    class_def: "class" CID ":" CID "{" method* "}"
    method: selector block
    selector: ID (":" ID)*
    block: "[" params "|" statements "]"
    params: (":" ID)*
    statements: (assignment ".")*
    assignment: ID ":=" expr
    expr: literal | var | cid | block | send | "(" expr ")"    
    literal: INT->int_lit | STR->str_lit | "true"->true_lit | "false"->false_lit | "nil"->nil_lit    
    var: ID | "self" | "super"
    cid: CID
    send: expr selector_part+
    selector_part: ID ":" expr

    CID: /[A-Z][a-zA-Z0-9_]*/
    ID: /[a-z_][a-zA-Z0-9_]*/
    INT: /[+-]?\d+/
    STR: /'((\\[\\'n])|[^'\\\n])*'/s
    
    %ignore /"(.|\n)*?"/s
    %import common.WS
    %ignore WS
    %ignore /'''(.*?)'''/s
"""

# Transforms special characters into their XML variant
def escape_xml(text):
    replacements = [
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ('"', "&quot;"),
        ("'", "&apos;"),
        ("\n", "&#10;"),
        ("\r", "&#13;"),
        ("\t", "&#9;"),
    ]
    for char, replacement in replacements:
        text = text.replace(char, replacement)
    return text

# Transforms parse tree into AST
# Each method corresponds to a rule in the grammar
class SOLTransformer(Transformer):
    def __init__(self):
        self.order_counter = 1

    def program(self, items):
        return {"type": "program", "classes": items}

    # Transforms class definition
    def class_def(self, items):
        return {
            "type": "class",
            "name": items[0].value,
            "parent": items[1].value,
            "methods": items[2:]
        }

    # Transforms method definition
    def method(self, items):
        selector, block = items
        return {
            "type": "method",
            "selector": selector,
            "block": block
        }

    # Transforms selector
    def selector(self, items):
        return ":".join([item.value for item in items])

    # Transforms block
    def block(self, items):
        params, statements = items
        return {
            "type": "block",
            "arity": len(params),
            "params": params,
            "statements": statements
        }

    # Transforms parameters
    def params(self, items):
        return [item.value for item in items if item.type == "ID"]

    # Transforms statements
    def statements(self, items):
        return items[::2] # Skips the . separators

    # Transforms assignment
    def assignment(self, items):
        var_name, expr = items
        return {
            "type": "assignment",
            "var": var_name.value,
            "expr": expr,
            "order": self._get_order()
        }

    # Transforms expression
    def expr(self, items):
        return items[0]

    # Transforms integer literal
    def int_lit(self, items):
        return {"type": "literal", "class": "Integer", "value": items[0].value}

    # Transforms string literal
    def str_lit(self, items):
        s = items[0].value[1:-1] # Remove quotes
        return {"type": "literal", "class": "String", "value": s}

    # Special literals
    def true_lit(self, _):
        return {"type": "literal", "class": "True", "value": "true"}
    def false_lit(self, _):
        return {"type": "literal", "class": "False", "value": "false"}
    def nil_lit(self, _):
        return {"type": "literal", "class": "Nil", "value": "nil"}

    # Transforms variable
    def var(self, items):
        return {"type": "var", "name": items[0].value}

    # Transforms class identifier
    def cid(self, items):
        return {"type": "literal", "class": "class", "value": items[0].value}

    # Transforms send expression
    def send(self, items):
        receiver, *parts = items
        selector_parts = []
        args = []
        for part in parts:
            selector_parts.append(part["selector_part"])
            args.append(part["arg"])
        return {
            "type": "send",
            "receiver": receiver,
            "selector": ":".join(selector_parts),
            "args": args
        }

    # Transforms selector part
    def selector_part(self, items):
        return {"selector_part": items[0].value, "arg": items[1]}

    # Keeps track of the order of statements
    def _get_order(self):
        current = self.order_counter
        self.order_counter += 1
        return str(current)

# Transforms the AST into XML format
def ast_to_xml(ast, description=None):
    # Create root program element
    root_attrib = {"language": "SOL25"}

    # If description was provided, add it to the root element
    if description is not None:
        root_attrib["description"] = escape_xml(description)

    root = ET.Element("program", root_attrib)

    # Process classes in the program 
    for classes in ast.get("classes", []):
        class_elem = ET.SubElement(root, "class", {
            "name": classes["name"],
            "parent": classes["parent"]
        })

        # Process methods
        for method in classes.get("methods", []):
            method_element = ET.SubElement(class_elem, "method", {
                "selector": method["selector"]
            })
            block = method["block"]
            
            # Create block element
            block_element = ET.SubElement(method_element, "block", {
                "arity": str(block["arity"])
            })

            # Add parameters
            for index, parameter in enumerate(block["params"], 1):
                ET.SubElement(block_element, "parameter", {
                    "name": parameter,
                    "order": str(index)
                })

            # Process statements
            for statement in block.get("statements", []):
                assign_elem = ET.SubElement(block_element, "assign", {
                    "order": statement["order"]
                })
                ET.SubElement(assign_elem, "var", {"name": statement["var"]})
                expr_elem = ET.SubElement(assign_elem, "expr")

                # Handle expression types
                process_expression(expr_elem, statement["expr"])

    return root

# Helper function that recursively creates expression elements
def process_expression(parent, expr):
    """Helper for recursive XML element creation from expressions."""
    if expr["type"] == "literal":
        ET.SubElement(parent, "literal", {
            "class": expr["class"],
            "value": escape_xml(str(expr["value"]))
        })
    elif expr["type"] == "var":
        ET.SubElement(parent, "var", {"name": expr["name"]})
    elif expr["type"] == "send":
        send_elem = ET.SubElement(parent, "send", {
            "selector": expr["selector"]
        })
        # Receiver
        rcvr_elem = ET.SubElement(send_elem, "expr")
        process_expression(rcvr_elem, expr["receiver"])
        # Arguments
        for idx, arg in enumerate(expr["args"], 1):
            arg_elem = ET.SubElement(send_elem, "arg", {"order": str(idx)})
            process_expression(ET.SubElement(arg_elem, "expr"), arg)

# Check for semantic errors in AST
def check_semantics(ast):
    # Keywords that cannot be used as variable names
    RESERVED_KEYWORDS = {"self", "super", "true", "false", "nil", "class"}

    # Check for Main class
    main_class = None
    for class_def in ast.get("classes", []):
        if class_def["name"] == "Main":
            main_class = class_def
            break

    if not main_class:
        sys.stderr.write("Semantic error: Missing Main class\n")
        sys.exit(31)

    # Check for run method in Main class
    has_run_method = False
    for method in main_class.get("methods", []):
        if method["selector"] == "run":
            has_run_method = True
            break

    if not has_run_method:
        sys.stderr.write("Semantic error: Missing run method in Main class\n")
        sys.exit(31)

    # Check for undefined classes
    defined_classes = {class_def["name"] for class_def in ast.get("classes", [])}
    for class_def in ast.get("classes", []):
        for method in class_def.get("methods", []):
            for statement in method["block"].get("statements", []):
                if statement["expr"]["type"] == "send":
                    receiver = statement["expr"]["receiver"]
                    if receiver["type"] == "literal" and receiver["class"] == "class":
                        if receiver["value"] not in defined_classes:
                            sys.stderr.write("Semantic error: Undefined class\n")
                            sys.exit(32)

    # Check for undefined methods
    defined_methods = {method["selector"] for class_def in ast.get("classes", []) for method in class_def.get("methods", [])}
    for class_def in ast.get("classes", []):
        for method in class_def.get("methods", []):
            for statement in method["block"].get("statements", []):
                if statement["expr"]["type"] == "send":
                    selector = statement["expr"]["selector"]
                    if selector not in defined_methods:
                        sys.stderr.write("Semantic error: Undefined method\n")
                        sys.exit(32)

    # Check for reserved keywords used as variable names
    for class_def in ast.get("classes", []):
        for method in class_def.get("methods", []):
            for statement in method["block"].get("statements", []):
                if statement["var"] in RESERVED_KEYWORDS:
                    sys.stderr.write("Semantic error: Invalid variable name\n")
                    sys.exit(22)

    # Check for reserved keywords used as method names
    for class_def in ast.get("classes", []):
        for method in class_def.get("methods", []):
            if method["selector"] in RESERVED_KEYWORDS:
                sys.stderr.write("Semantic error: Invalid method name\n")
                sys.exit(22)

    # Check for variable collisions (e.g., variable name conflicts with parameter name)
    for class_def in ast.get("classes", []):
        for method in class_def.get("methods", []):
            defined_vars = set(method["block"]["params"])
            for statement in method["block"].get("statements", []):
                if statement["var"] in defined_vars:
                    sys.stderr.write("Semantic error: Variable conflict\n")
                    sys.exit(34)

        # Check for arity mismatches
    for class_def in ast.get("classes", []):
        for method in class_def.get("methods", []):
            expected_arity = method["selector"].count(":")
            actual_arity = method["block"]["arity"]
            if expected_arity != actual_arity:
                sys.stderr.write("Semantic error: Method arity mismatch\n")
                sys.exit(33)

if __name__ == "__main__":
    source = sys.stdin.read()

    description = None

    # Comment regex
    comment_re = re.compile(r'"((?:.|\n)*?)"', re.DOTALL)

    # Look for a comment in the source code
    match = comment_re.search(source)
    if match:
        description = match.group(1)
        description = bytes(description, 'utf-8').decode('unicode_escape') # Transform escape sequences into their ascii value
        start, end = match.start(), match.end()

        # Remove the comment from the source code and save it in the description
        source = source[:start] + source[end:]
   
    # Creating the parser from the grammar and specifying the transformer
    parser = Lark(grammar, start='program', parser='lalr', transformer=SOLTransformer())
    
    try:
        ast = parser.parse(source)

        # Check semantics errors
        check_semantics(ast)

        xml_root = ast_to_xml(ast, description)

        xml_root = ET.tostring(xml_root, encoding='utf-8', method='xml').decode('utf-8')
        xml_root = minidom.parseString(xml_root).toprettyxml(indent="    ")
        xml_root = xml_root.replace('amp;', '') # Temporary fix for double handling of escape sequence in comments that became not temporary
        print(xml_root)

    except UnexpectedCharacters: # Catch lexical errors
        sys.stderr.write("Lexical error\n")
        sys.exit(21)
    except UnexpectedToken: # Catch syntax errors
        sys.stderr.write("Syntax error\n")
        sys.exit(22)
    except Exception: # Catch unknown errors
        sys.stderr.write("Unknown error\n")
        sys.exit(35)

