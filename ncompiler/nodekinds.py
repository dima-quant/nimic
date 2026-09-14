"""
ncompiler/nodekinds.py — TNodeKind enum
Converted from compiler/nodekinds.nim
"""
# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *


class TNodeKind(NIntEnum):
    nkNone = auto()               # unknown node kind: indicates an error
    # Expressions:
    # Atoms:
    nkEmpty = auto()              # the node is empty
    nkIdent = auto()              # node is an identifier
    nkSym = auto()                # node is a symbol
    nkType = auto()               # node is used for its typ field

    nkCharLit = auto()            # a character literal ''
    nkIntLit = auto()             # an integer literal
    nkInt8Lit = auto()
    nkInt16Lit = auto()
    nkInt32Lit = auto()
    nkInt64Lit = auto()
    nkUIntLit = auto()            # an unsigned integer literal
    nkUInt8Lit = auto()
    nkUInt16Lit = auto()
    nkUInt32Lit = auto()
    nkUInt64Lit = auto()
    nkFloatLit = auto()           # a floating point literal
    nkFloat32Lit = auto()
    nkFloat64Lit = auto()
    nkFloat128Lit = auto()
    nkStrLit = auto()             # a string literal ""
    nkRStrLit = auto()            # a raw string literal r""
    nkTripleStrLit = auto()       # a triple string literal """
    nkNilLit = auto()             # the nil literal
    # end of atoms
    nkComesFrom = auto()          # "comes from" template/macro information
    nkDotCall = auto()            # used to temporarily flag a nkCall node

    nkCommand = auto()            # a call like ``p 2, 4`` without parenthesis
    nkCall = auto()               # a call like p(x, y)
    nkCallStrLit = auto()         # a call with a string literal
    nkInfix = auto()              # a call like (a + b)
    nkPrefix = auto()             # a call like !a
    nkPostfix = auto()            # something like a! (also used for visibility)
    nkHiddenCallConv = auto()     # an implicit type conversion via a type converter

    nkExprEqExpr = auto()         # a named parameter with equals: ''expr = expr''
    nkExprColonExpr = auto()      # a named parameter with colon: ''expr: expr''
    nkIdentDefs = auto()          # a definition like `a, b: typeDesc = expr`
    nkVarTuple = auto()           # a ``var (a, b) = expr`` construct
    nkPar = auto()                # syntactic (); may be a tuple constructor
    nkObjConstr = auto()          # object constructor: T(a: 1, b: 2)
    nkCurly = auto()              # syntactic {}
    nkCurlyExpr = auto()          # an expression like a{i}
    nkBracket = auto()            # syntactic []
    nkBracketExpr = auto()        # an expression like a[i..j, k]
    nkPragmaExpr = auto()         # an expression like a{.pragmas.}
    nkRange = auto()              # an expression like i..j
    nkDotExpr = auto()            # a.b
    nkCheckedFieldExpr = auto()   # a.b, but b is a field that needs to be checked
    nkDerefExpr = auto()          # a^
    nkIfExpr = auto()             # if as an expression
    nkElifExpr = auto()
    nkElseExpr = auto()
    nkLambda = auto()             # lambda expression
    nkDo = auto()                 # lambda block appering as trailing proc param
    nkAccQuoted = auto()          # `a` as a node

    nkTableConstr = auto()        # a table constructor {expr: expr}
    nkBind = auto()               # ``bind expr`` node
    nkClosedSymChoice = auto()    # symbol choice node; a list of nkSyms (closed)
    nkOpenSymChoice = auto()      # symbol choice node; a list of nkSyms (open)
    nkHiddenStdConv = auto()      # an implicit standard type conversion
    nkHiddenSubConv = auto()      # an implicit type conversion from a subtype
    nkConv = auto()               # a type conversion
    nkCast = auto()               # a type cast
    nkStaticExpr = auto()         # a static expr
    nkAddr = auto()               # a addr expression
    nkHiddenAddr = auto()         # implicit address operator
    nkHiddenDeref = auto()        # implicit ^ operator
    nkObjDownConv = auto()        # down conversion between object types
    nkObjUpConv = auto()          # up conversion between object types
    nkChckRangeF = auto()         # range check for floats
    nkChckRange64 = auto()        # range check for 64 bit ints
    nkChckRange = auto()          # range check for ints
    nkStringToCString = auto()    # string to cstring
    nkCStringToString = auto()    # cstring to string
    # end of expressions

    nkAsgn = auto()               # a = b
    nkFastAsgn = auto()           # internal node for a fast ``a = b``
    nkGenericParams = auto()      # generic parameters
    nkFormalParams = auto()       # formal parameters
    nkOfInherit = auto()          # inherited from symbol

    nkImportAs = auto()           # a 'as' b in an import statement
    nkProcDef = auto()            # a proc
    nkMethodDef = auto()          # a method
    nkConverterDef = auto()       # a converter
    nkMacroDef = auto()           # a macro
    nkTemplateDef = auto()        # a template
    nkIteratorDef = auto()        # an iterator

    nkOfBranch = auto()           # used inside case statements
    nkElifBranch = auto()         # used in if statements
    nkExceptBranch = auto()       # an except section
    nkElse = auto()               # an else part
    nkAsmStmt = auto()            # an assembler block
    nkPragma = auto()             # a pragma statement
    nkPragmaBlock = auto()        # a pragma with a block
    nkIfStmt = auto()             # an if statement
    nkWhenStmt = auto()           # a when expression or statement
    nkForStmt = auto()            # a for statement
    nkParForStmt = auto()         # a parallel for statement
    nkWhileStmt = auto()          # a while statement
    nkCaseStmt = auto()           # a case statement
    nkTypeSection = auto()        # a type section
    nkVarSection = auto()         # a var section
    nkLetSection = auto()         # a let section
    nkConstSection = auto()       # a const section
    nkConstDef = auto()           # a const definition
    nkTypeDef = auto()            # a type definition
    nkYieldStmt = auto()          # the yield statement as a tree
    nkDefer = auto()              # the 'defer' statement
    nkTryStmt = auto()            # a try statement
    nkFinally = auto()            # a finally section
    nkRaiseStmt = auto()          # a raise statement
    nkReturnStmt = auto()         # a return statement
    nkBreakStmt = auto()          # a break statement
    nkContinueStmt = auto()       # a continue statement
    nkBlockStmt = auto()          # a block statement
    nkStaticStmt = auto()         # a static statement
    nkDiscardStmt = auto()        # a discard statement
    nkStmtList = auto()           # a list of statements
    nkImportStmt = auto()         # an import statement
    nkImportExceptStmt = auto()   # an import x except a statement
    nkExportStmt = auto()         # an export statement
    nkExportExceptStmt = auto()   # an 'export except' statement
    nkFromStmt = auto()           # a from * import statement
    nkIncludeStmt = auto()        # an include statement
    nkBindStmt = auto()           # a bind statement
    nkMixinStmt = auto()          # a mixin statement
    nkUsingStmt = auto()          # an using statement
    nkCommentStmt = auto()        # a comment statement
    nkStmtListExpr = auto()       # a statement list followed by an expr
    nkBlockExpr = auto()          # a statement block ending in an expr
    nkStmtListType = auto()       # a statement list ending in a type
    nkBlockType = auto()          # a statement block ending in a type

    nkWith = auto()               # distinct with `foo`
    nkWithout = auto()            # distinct without `foo`

    nkTypeOfExpr = auto()         # type(1+2)
    nkObjectTy = auto()           # object body
    nkTupleTy = auto()            # tuple body
    nkTupleClassTy = auto()       # tuple type class
    nkTypeClassTy = auto()        # user-defined type class
    nkStaticTy = auto()           # ``static[T]``
    nkRecList = auto()            # list of object parts
    nkRecCase = auto()            # case section of object
    nkRecWhen = auto()            # when section of object
    nkRefTy = auto()              # ``ref T``
    nkPtrTy = auto()              # ``ptr T``
    nkVarTy = auto()              # ``var T``
    nkConstTy = auto()            # ``const T``
    nkOutTy = auto()              # ``out T``
    nkDistinctTy = auto()         # distinct type
    nkProcTy = auto()             # proc type
    nkIteratorTy = auto()         # iterator type
    nkSinkAsgn = auto()           # '=sink(x, y)'
    nkEnumTy = auto()             # enum body
    nkEnumFieldDef = auto()       # `ident = expr` in an enumeration
    nkArgList = auto()            # argument list
    nkPattern = auto()            # a special pattern; used for matching
    nkHiddenTryStmt = auto()      # a hidden try statement
    nkClosure = auto()            # (prc, env)-pair (internally used for code gen)
    nkGotoState = auto()          # used for the state machine (for iterators)
    nkState = auto()              # give a label to a code section (for iterators)
    nkBreakState = auto()         # special break statement for easier code generation
    nkFuncDef = auto()            # a func
    nkTupleConstr = auto()        # a tuple constructor
    nkError = auto()              # erroneous AST node
    nkModuleRef = auto()          # for .rod file support: A (moduleId, itemId) pair
    nkReplayAction = auto()       # for .rod file support: A replay action
    nkNilRodNode = auto()         # for .rod file support: a 'nil' PNode
    nkOpenSym = auto()            # container for captured sym


with const:
    nkCallKinds = {TNodeKind.nkCall, TNodeKind.nkInfix, TNodeKind.nkPrefix,
                   TNodeKind.nkPostfix, TNodeKind.nkCommand, TNodeKind.nkCallStrLit,
                   TNodeKind.nkHiddenCallConv}

    # routineDefs = {TNodeKind.nkProcDef, TNodeKind.nkMethodDef, TNodeKind.nkConverterDef,
    #            TNodeKind.nkMacroDef, TNodeKind.nkTemplateDef, TNodeKind.nkIteratorDef,
    #            TNodeKind.nkFuncDef}
