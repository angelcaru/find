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

# </enums>

# <classes>

@dataclass
class Flags:
    pass
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

@dataclass
class ReplaceNode(Node):
    query: Node
    replacement: Node

    def __repr__(self) -> str:
        return f"({self.query}) -> ({self.replacement})"

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

# </classes>

Error = str # TODO: proper error reporting (replace "str" with a custom class "Error" or something)
ParseResult = Tuple[Optional[Node], Optional[Error]]
RuntimeResult = Tuple[Optional[Any], Optional[Error]]

def lex_string(it: Iterator[str]) -> Tuple[Optional[Token], Optional[Error]]:
    string: str = ""
    for char in it:
        assert len(char) == 1, "This could be a bug in the lexer"
        if char == '"': break # TODO: escaping
        string += char
    else: # no break
        return None, "EOF while parsing string, did you forget a '\"'?"
    return Token(TokenType.STRING, string), None

def lex(code: str) -> Generator[Token, None, Optional[Error]]:
    it = iter(code)
    for char in it:
        if char.isspace():
            pass
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

def parse_expr(it: Iterator[Token]) -> ParseResult:
    tok = next(it)
    if tok.type_ != TokenType.STRING:
        return None, "expected string"
    return StringNode(tok), None

def perform_match(query_node: Node, input_: str) -> RuntimeResult:
    assert isinstance(query_node, StringNode)
    value_to_find = query_node.tok.value
    assert isinstance(value_to_find, str)
    idx: int = input_.find(value_to_find)
    return (idx, idx + len(value_to_find)), None

def perform_replacement(replacement_node: Node, input_: str) -> RuntimeResult:
    assert isinstance(replacement_node, StringNode)
    return replacement_node.tok.value, None

def perform_ast(ast: Node, input_: str) -> RuntimeResult:
    assert isinstance(ast, ReplaceNode)
    i = input_

    res, err = perform_match(ast.query, i)
    assert res is not None

    idx, idx_end = res
    if err is not None:
        return None, err
    assert isinstance(idx, int)
    assert isinstance(idx_end, int)

    rep, err = perform_replacement(ast.replacement, input_)
    if err is not None:
        return None, err
    assert isinstance(rep, str)

    res = i[:idx] + rep + i[idx_end:]
    return res, None

def parse(tokens: Iterable[Token]) -> ParseResult:
    it = iter(tokens)
    query, err = parse_expr(it)
    if err: return None, err
    assert isinstance(query, Node)

    try:
        tok = next(it)
    except StopIteration:
        return None, "EOF while parsing replacement"
    if tok.type_ != TokenType.ARROW:
        return None, "Expected '->'"

    replacement, err = parse_expr(it)
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
        if flag == ...: # TODO: create flags
            pass # flags.(...) = True
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
    
    ast, err = parse(tokens)
    if err is not None:
        error(err)
    assert isinstance(ast, Node)
    
    res, err = perform_ast(ast, input_)
    if err is not None:
        error(err)
    assert isinstance(res, str)
    
    print(res)

if __name__ == "__main__":
    main(sys.argv)