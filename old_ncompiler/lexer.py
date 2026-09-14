""" Lexical analyzer for Nim. """
from nkeywords import *
from idents import * #PIdent
from nimlexbase import * #TBaseLexer
from lineinfos import * # TLineInfo
from options import *

# import
#   options, msgs, platform, idents, nimlexbase, llstream,
#   wordrecg, lineinfos, pathutils

# import std/[hashes, parseutils, strutils]

# when defined(nimPreviewSlimSystem):
#   import std/[assertions, formatfloat]

# from enum import IntEnum, StrEnum, auto

# const
#   numChars*: set[char] = {'0'..'9', 'a'..'z', 'A'..'Z'}
#   SymChars*: set[char] = {'a'..'z', 'A'..'Z', '0'..'9', '\x80'..'\xFF'}
#   SymStartChars*: set[char] = {'a'..'z', 'A'..'Z', '\x80'..'\xFF'}
#   OpChars*: set[char] = {'+', '-', '*', '/', '\\', '<', '>', '!', '?', '^', '.',
#     '|', '=', '%', '&', '$', '@', '~', ':'}
#   UnaryMinusWhitelist = {' ', '\t', '\n', '\r', ',', ';', '(', '[', '{'}

with const:
    numChars: set[str] = {chr(i) for i in range(ord('0'), ord('9')+1)}|{chr(i) for i in range(ord('a'), ord('z')+1)}|\
        {chr(i) for i in range(ord('A'), ord('Z')+1)}
    SymChars: set[str] = {chr(i) for i in range(ord('0'), ord('9')+1)}|{chr(i) for i in range(ord('a'), ord('z')+1)}|\
        {chr(i) for i in range(ord('A'), ord('Z')+1)}|{chr(i) for i in range(0x80, 0x100)}
    SymStartChars: set[str] = {chr(i) for i in range(ord('a'), ord('z')+1)}|\
        {chr(i) for i in range(ord('A'), ord('Z')+1)}|{chr(i) for i in range(0x80, 0x100)}
    OpChars: set[str] = {'+', '-', '*', '/', '\\', '<', '>', '!', '?', '^', '.',
         '|', '=', '%', '&', '$', '@', '~', ':'}
    """{. private .}"""
    UnaryMinusWhitelist = {' ', '\t', '\n', '\r', ',', ';', '(', '[', '{'}

# don't forget to update the 'highlite' module if these charsets should change

# type
#   TokType* = enum
#     tkInvalid = "tkInvalid", tkEof = "[EOF]", # order is important here!
#     tkSymbol = "tkSymbol", # keywords:
#     tkAddr = "addr", tkAnd = "and", tkAs = "as", tkAsm = "asm",
#     tkBind = "bind", tkBlock = "block", tkBreak = "break", tkCase = "case", tkCast = "cast",
#     tkConcept = "concept", tkConst = "const", tkContinue = "continue", tkConverter = "converter",
#     tkDefer = "defer", tkDiscard = "discard", tkDistinct = "distinct", tkDiv = "div", tkDo = "do",
#     tkElif = "elif", tkElse = "else", tkEnd = "end", tkEnum = "enum", tkExcept = "except", tkExport = "export",
#     tkFinally = "finally", tkFor = "for", tkFrom = "from", tkFunc = "func",
#     tkIf = "if", tkImport = "import", tkIn = "in", tkInclude = "include", tkInterface = "interface",
#     tkIs = "is", tkIsnot = "isnot", tkIterator = "iterator",
#     tkLet = "let",
#     tkMacro = "macro", tkMethod = "method", tkMixin = "mixin", tkMod = "mod", tkNil = "nil", tkNot = "not", tkNotin = "notin",
#     tkObject = "object", tkOf = "of", tkOr = "or", tkOut = "out",
#     tkProc = "proc", tkPtr = "ptr", tkRaise = "raise", tkRef = "ref", tkReturn = "return",
#     tkShl = "shl", tkShr = "shr", tkStatic = "static",
#     tkTemplate = "template",
#     tkTry = "try", tkTuple = "tuple", tkType = "type", tkUsing = "using",
#     tkVar = "var", tkWhen = "when", tkWhile = "while", tkXor = "xor",
#     tkYield = "yield", # end of keywords

#     tkIntLit = "tkIntLit", tkInt8Lit = "tkInt8Lit", tkInt16Lit = "tkInt16Lit",
#     tkInt32Lit = "tkInt32Lit", tkInt64Lit = "tkInt64Lit",
#     tkUIntLit = "tkUIntLit", tkUInt8Lit = "tkUInt8Lit", tkUInt16Lit = "tkUInt16Lit",
#     tkUInt32Lit = "tkUInt32Lit", tkUInt64Lit = "tkUInt64Lit",
#     tkFloatLit = "tkFloatLit", tkFloat32Lit = "tkFloat32Lit",
#     tkFloat64Lit = "tkFloat64Lit", tkFloat128Lit = "tkFloat128Lit",
#     tkStrLit = "tkStrLit", tkRStrLit = "tkRStrLit", tkTripleStrLit = "tkTripleStrLit",
#     tkGStrLit = "tkGStrLit", tkGTripleStrLit = "tkGTripleStrLit", tkCharLit = "tkCharLit",
#     tkCustomLit = "tkCustomLit",

#     tkParLe = "(", tkParRi = ")", tkBracketLe = "[",
#     tkBracketRi = "]", tkCurlyLe = "{", tkCurlyRi = "}",
#     tkBracketDotLe = "[.", tkBracketDotRi = ".]",
#     tkCurlyDotLe = "{.", tkCurlyDotRi = ".}",
#     tkParDotLe = "(.", tkParDotRi = ".)",
#     tkComma = ",", tkSemiColon = ";",
#     tkColon = ":", tkColonColon = "::", tkEquals = "=",
#     tkDot = ".", tkDotDot = "..", tkBracketLeColon = "[:",
#     tkOpr, tkComment, tkAccent = "`",
#     # these are fake tokens used by renderer.nim
#     tkSpaces, tkInfixOpr, tkPrefixOpr, tkPostfixOpr, tkHideableStart, tkHideableEnd
#  TokTypes* = set[TokType]

# type enum: add hints to recognize (inherit or string)?
class TokType(NStrEnum):    
    tkInvalid = "tkInvalid"
    tkEof = "[EOF]" # order is important here!
    tkSymbol = "tkSymbol", # keywords:
    tkAddr = "addr"
    tkAnd = "and"
    tkAs = "as"
    tkAsm = "asm"
    tkBind = "bind"
    tkBlock = "block"
    tkBreak = "break"
    tkCase = "case"
    tkCast = "cast"
    tkConcept = "concept"
    tkConst = "const"
    tkContinue = "continue"
    tkConverter = "converter"
    tkDefer = "defer"
    tkDiscard = "discard"
    tkDistinct = "distinct"
    tkDiv = "div"
    tkDo = "do"
    tkElif = "elif"
    tkElse = "else"
    tkEnd = "end"
    tkEnum = "enum"
    tkExcept = "except"
    tkExport = "export"
    tkFinally = "finally"
    tkFor = "for"
    tkFrom = "from"
    tkFunc = "func"
    tkIf = "if"
    tkImport = "import"
    tkIn = "in"
    tkInclude = "include"
    tkInterface = "interface"
    tkIs = "is"
    tkIsnot = "isnot"
    tkIterator = "iterator"
    tkLet = "let"
    tkMacro = "macro"
    tkMethod = "method"
    tkMixin = "mixin"
    tkMod = "mod"
    tkNil = "nil"
    tkNot = "not"
    tkNotin = "notin"
    tkObject = "object"
    tkOf = "of"
    tkOr = "or"
    tkOut = "out"
    tkProc = "proc"
    tkPtr = "ptr"
    tkRaise = "raise"
    tkRef = "ref"
    tkReturn = "return"
    tkShl = "shl"
    tkShr = "shr"
    tkStatic = "static"
    tkTemplate = "template"
    tkTry = "try"
    tkTuple = "tuple"
    tkType = "type"
    tkUsing = "using"
    tkVar = "var"
    tkWhen = "when"
    tkWhile = "while"
    tkXor = "xor"
    tkYield = "yield" # end of keywords

    tkIntLit = "tkIntLit"
    tkInt8Lit = "tkInt8Lit"
    tkInt16Lit = "tkInt16Lit"
    tkInt32Lit = "tkInt32Lit"
    tkInt64Lit = "tkInt64Lit"
    tkUIntLit = "tkUIntLit"
    tkUInt8Lit = "tkUInt8Lit"
    tkUInt16Lit = "tkUInt16Lit"
    tkUInt32Lit = "tkUInt32Lit"
    tkUInt64Lit = "tkUInt64Lit"
    tkFloatLit = "tkFloatLit"
    tkFloat32Lit = "tkFloat32Lit"
    tkFloat64Lit = "tkFloat64Lit"
    tkFloat128Lit = "tkFloat128Lit"
    tkStrLit = "tkStrLit"
    tkRStrLit = "tkRStrLit"
    tkTripleStrLit = "tkTripleStrLit"
    tkGStrLit = "tkGStrLit"
    tkGTripleStrLit = "tkGTripleStrLit"
    tkCharLit = "tkCharLit"
    tkCustomLit = "tkCustomLit"

    tkParLe = "("
    tkParRi = ")"
    tkBracketLe = "["
    tkBracketRi = "]"
    tkCurlyLe = "{"
    tkCurlyRi = "}"
    tkBracketDotLe = "[."
    tkBracketDotRi = ".]"
    tkCurlyDotLe = "{."
    tkCurlyDotRi = ".}"
    tkParDotLe = "(."
    tkParDotRi = ".)"
    tkComma = ","
    tkSemiColon = ";"
    tkColon = ":"
    tkColonColon = "::"
    tkEquals = "="
    tkDot = "."
    tkDotDot = ".."
    tkBracketLeColon = "[:"
    tkOpr = auto()
    tkComment = auto()
    tkAccent = "`"
    # these are fake tokens used by renderer.nim
    tkSpaces = auto()
    tkInfixOpr = auto()
    tkPrefixOpr = auto()
    tkPostfixOpr = auto()
    tkHideableStart = auto()
    tkHideableEnd = auto()

type TokTypes = list[TokType] # shoulbe a type?

# const
#   weakTokens = {tkComma, tkSemiColon, tkColon,
#                 tkParRi, tkParDotRi, tkBracketRi, tkBracketDotRi,
#                 tkCurlyRi} # \
#     # tokens that should not be considered for previousToken
#   tokKeywordLow* = succ(tkSymbol)
#   tokKeywordHigh* = pred(tkIntLit)

with const:
  weakTokens = {TokType.tkComma, TokType.tkSemiColon, TokType.tkColon,
                TokType.tkParRi, TokType.tkParDotRi, TokType.tkBracketRi, TokType.tkBracketDotRi,
                TokType.tkCurlyRi} # \
    # tokens that should not be considered for previousToken
  tokKeywordLow = TokType.succ(TokType.tkSymbol)
  tokKeywordHigh = TokType.pred(TokType.tkIntLit)

# type
#   NumericalBase* = enum
#     base10,                   # base10 is listed as the first element,
#                               # so that it is the correct default value
#     base2, base8, base16

#   TokenSpacing* = enum
#     tsLeading, tsTrailing, tsEof

#   Token* = object                # a Nim token
#     tokType*: TokType            # the type of the token
#     base*: NumericalBase         # the numerical base; only valid for int
#                                  # or float literals
#     spacing*: set[TokenSpacing]  # spaces around token
#     indent*: int                 # the indentation; != -1 if the token has been
#                                  # preceded with indentation
#     ident*: PIdent               # the parsed identifier
#     iNumber*: BiggestInt         # the parsed integer literal
#     fNumber*: BiggestFloat       # the parsed floating point literal
#     literal*: string             # the parsed (string) literal; and
#                                  # documentation comments are here too
#     line*, col*: int
#     when defined(nimpretty):
#       offsetA*, offsetB*: int # used for pretty printing so that literals
#                               # like 0b01 or  r"\L" are unaffected
#       commentOffsetA*, commentOffsetB*: int

#   ErrorHandler* = proc (conf: ConfigRef; info: TLineInfo; msg: TMsgKind; arg: string)
#   Lexer* = object of TBaseLexer
#     fileIdx*: FileIndex
#     indentAhead*: int         # if > 0 an indentation has already been read
#                               # this is needed because scanning comments
#                               # needs so much look-ahead
#     currLineIndent*: int
#     errorHandler*: ErrorHandler
#     cache*: IdentCache
#     when defined(nimsuggest):
#       previousToken: TLineInfo
#       tokenEnd*: TLineInfo
#       previousTokenEnd*: TLineInfo
#     config*: ConfigRef

class  NumericalBase(IntEnum):
    base10 = auto()                 # base10 is listed as the first element,
                                  # so that it is the correct default value
    base2 = auto()
    base8 = auto()
    base16 = auto()


class  TokenSpacing(IntEnum):
    tsLeading = auto()
    tsTrailing = auto()
    tsEof = auto()


class Token:                                   # a Nim token
    def __init__(self):
        self.tokType: TokType                  # the type of the token
        self.base: NumericalBase               # the numerical base; only valid for int
                                               # or float literals
        self.spacing: list[TokenSpacing]       # spaces around token
        self.indent: int                       # the indentation; != -1 if the token has been
                                               # preceded with indentation
        self.ident: PIdent                     # the parsed identifier
        self.iNumber: BiggestInt               # the parsed integer literal
        self.fNumber: BiggestFloat             # the parsed floating point literal
        self.literal: str                      # the parsed (string) literal; and
                                               # documentation comments are here too
        self.line: int
        self.col: int
        if resolve_aot and defined("nimpretty"):
          self.offsetA: int                    # used for pretty printing so that literals
          self.offsetB: int                    # like 0b01 or  r"\L" are unaffected
          self.commentOffsetA: int
          self.commentOffsetB: int


type ErrorHandler = lambda conf: ConfigRef; info: TLineInfo; msg: TMsgKind; arg: str

class Lexer(TBaseLexer):
    def __init__(self):
        super().__init__()
        self.fileIdx: FileIndex
        self.indentAhead: int         # if > 0 an indentation has already been read       
                                      # this is needed because scanning comments
                                      # needs so much look-ahead
        self.currLineIndent: int
        self.errorHandler: ErrorHandler
        self.cache: IdentCache
        if resolve_aot and defined("nimsuggest"):
          self.previousToken: TLineInfo
          self.tokenEnd: TLineInfo
          self.previousTokenEnd: TLineInfo
        self.config: ConfigRef

print('OK')   