#!/usr/bin/python3

import sys
from dataclasses import dataclass
from typing import *
from enum import Enum, auto
from abc import ABC, abstractmethod

# <enums>

class TokenType(Enum):
    STRING=auto()
    ARROW=auto()
    LPAREN=auto()
    RPAREN=auto()

# </enums>

# <classes>

Error = str # TODO: proper error reporting (replace "str" with a custom class "Error" or something)
ParseResult = Tuple[Optional["Node"], Optional[Error]]
RuntimeResult = Tuple[Optional[Any], Optional[Error]]

@dataclass
class Flags:
    debug: bool = False
flags = Flags() # global variable, oh no

@dataclass
class Token:
    type_: TokenType
    value: Union[str, None] = None

    def __repr__(self) -> str:
        result: str = f"{self.type_.name}"
        if self.value is not None:
            return f"{result}:{repr(self.value)}"
        return result

@dataclass
class Node(ABC):
    @abstractmethod
    def __repr__(self) -> str:
        ...

    @abstractmethod
    def visit(self, input_: str) -> RuntimeResult:
        ...

@dataclass
class ReplaceNode(Node):
    query: Node
    replacement: Node

    def __repr__(self) -> str:
        return f"({self.query}) -> ({self.replacement})"
    
    def visit(self, input_: str) -> RuntimeResult:
        val, err = self.query.visit(input_)
        if err is not None: return None, err
        assert val is not None
        if not isinstance(val, str):
            return None, "wrong data type for query; expected string"

        idx: int = input_.find(val)
        idx_end: int = idx + len(val)

        rep, err = self.replacement.visit(input_)
        if err is not None: return None, err
        assert rep is not None
        if not isinstance(rep, str):
            return None, "wrong data type for replacement; expected string"
        
        return input_[:idx] + rep + input_[idx_end:], None

@dataclass
class StringNode(Node):
    tok: Token

    def __new__(cls, tok: Token) -> "StringNode":
        assert tok.type_ == TokenType.STRING, "This could be a bug in the parser"
        assert tok.value is not None, "This could be a bug in the lexer"
        return object.__new__(cls)

    def __repr__(self) -> str:
        assert self.tok.value is not None, "This could be a bug in the StringNode.__new__() method"
        return repr(self.tok)
    
    def visit(self, input_: str) -> RuntimeResult:
        assert isinstance(self.tok.value, str)
        return self.tok.value, None

@dataclass
class ConcatNode(Node):
    nodes: List[Node]

    def __repr__(self) -> str:
        return "(" + " ".join(map(repr, self.nodes)) + ")"
    
    def visit(self, input_: str) -> RuntimeResult:
        res = ""
        for node in self.nodes:
            val, err = node.visit(input_)
            if err is not None: return None, err
            assert val is not None

            res += str(val)
        return res, None

# </classes>

def lex_string(it: Iterator[str]) -> Tuple[Optional[Token], Optional[Error]]:
    string: str = ""
    for char in it:
        assert len(char) == 1, "This could be a bug in the lexer"
        if char == '"': break # TODO: escaping
        string += char
    else: # no break
        return None, "EOF while parsing string, did you forget a '\"'?"
    return Token(TokenType.STRING, string), None

single_char_toks: Dict[str, TokenType] = {
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
}

def lex(code: str) -> Generator[Token, None, Optional[Error]]:
    it = iter(code)
    for char in it:
        if char.isspace():
            pass
        elif char in single_char_toks:
            yield Token(single_char_toks[char])
        elif char == '"':
            tok, err = lex_string(it)
            if err is not None:
                return err
            assert isinstance(tok, Token), "This could be a bug in the lex_string() function"
            yield tok
        elif char == "-":
            char = next(it)
            if char != ">":
                return "Expected '>' (after '-')"
            yield Token(TokenType.ARROW)
        else:
            return f"Unknown character '{char}'"
    return None

TT_NAMES: Dict[TokenType, str] = {
    TokenType.ARROW:  "'->'",
    TokenType.STRING: "string",
    TokenType.LPAREN: "'('",
    TokenType.RPAREN: "')'",
}

def expect(expected: List[TokenType], actual: TokenType) -> str:
    expected_type_names: List[str] = []
    for tt in expected:
        expected_type_names.append(TT_NAMES[tt])
    return f"expected {human_chain(expected_type_names)}, but got {TT_NAMES[actual]}"

def human_chain(elts: List[str], sep: str=", ", last_word: str="or") -> str:
    result: str = ""
    for i, elt in enumerate(elts):
        result += elt
        if i < len(elts) - 2:
            result += sep
        elif i == len(elts) - 2:
            result += f" {last_word} "
    return result

def parse_expr(it: Iterator[Token], tok: Token) -> ParseResult:
    if tok.type_ != TokenType.LPAREN and tok.type_ != TokenType.STRING:
        return None, expect([TokenType.LPAREN, TokenType.STRING], tok.type_)
    elif tok.type_ == TokenType.STRING:
        return StringNode(tok), None
    
    nodes: List[Node] = []
    while (tok := next(it)).type_ != TokenType.RPAREN:
        node, err = parse_expr(it, tok)
        if err is not None: return None, err
        assert isinstance(node, Node)

        nodes.append(node)
    
    return ConcatNode(nodes), None

def parse(tokens: Iterable[Token]) -> ParseResult:
    it = iter(tokens)
    query, err = parse_expr(it, next(it))
    if err: return None, err
    assert isinstance(query, Node)

    try:
        tok = next(it)
    except StopIteration:
        return None, "EOF while parsing replacement"
    if tok.type_ != TokenType.ARROW:
        return None, expect([TokenType.ARROW], tok.type_)

    replacement, err = parse_expr(it, next(it))
    if err: return None, err
    assert isinstance(replacement, Node)

    return ReplaceNode(query, replacement), None

def error(msg: str) -> NoReturn:
    print(f"ERROR: {msg}")
    exit(1)

def usage(program_name: str, error_msg: Optional[str]=None) -> NoReturn:
    file = sys.stderr
    if error_msg is None: file = sys.stdout
    print(f"Usage: {program_name} [flags] <query string filename> [input file]", file=file)
    print("    Flags:", file=file)
    print("       none for now", file=file)
    print("    Input file defaults to stdin")
    if error_msg is not None:
        error(error_msg)
    else:
        exit(0)

def main(argv: List[str]):
    program_name: str
    program_name, *argv = argv
    if len(argv) < 1:
        usage(program_name, "no args provided")
    
    while True:
        if len(argv) < 1:
            usage(program_name, "no filename provided")
        flag, *argv = argv
        if flag == "--debug":
            flags.debug = True
        else:
            argv.insert(0, flag) # flag actually contains the next arg of the program, so this makes sense
            break
    
    if len(argv) < 1:
        usage(program_name, "unknown error while parsing command-line args")
    code_path, *argv = argv

    input_file = sys.stdin
    if len(argv) > 0:
        input_path, *argv = argv
        try:
            input_file = open(input_path, "r")
        except FileNotFoundError:
            error(f"cannot find file {input_path}")
    if input_file == sys.stdin:
        error("reading input from stdin is not implemented yet")
    
    with open(code_path, "r") as f:
        code = f.read()
        assert isinstance(code, str)
    
    with input_file:
        input_ = input_file.read()
    
    tokens: List[Token] = []
    it = lex(code)
    try:
        while True:
            tok = next(it)
            tokens.append(tok)
    except StopIteration as e:
        if e.value is not None:
            error(e.value)
    
    if flags.debug:
        print(f"[DEBUG] Lexer output: {tokens}")
    
    ast, err = parse(tokens)
    if err is not None:
        error(err)
    if flags.debug:
        print(f"[DEBUG] Parser output: {ast}")
    assert isinstance(ast, Node)
    
    res, err = ast.visit(input_)
    if err is not None:
        error(err)
    assert isinstance(res, str)
    
    print(res)

if __name__ == "__main__":
    main(sys.argv)