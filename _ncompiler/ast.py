"""
ncompiler/ast.py — AST node types (extensible stub)
Converted from compiler/ast.nim

Only the node types and functions the parser actually needs.
PSym, PType, and NIF/IC features are stubbed for future expansion.
"""
from __future__ import annotations
from nodekinds import TNodeKind, nkCallKinds, routineDefs
from lineinfos import TLineInfo, unknownLineInfo, FileIndex
from idents import PIdent

# Re-export
from nodekinds import TNodeKind as TNodeKind


# --- Node flags ---
class TNodeFlag:
    nfBase2 = 1
    nfBase8 = 2
    nfBase16 = 4
    nfAllConst = 8
    nfHasComment = 16
    nfLazyType = 32


# --- PNode ---
class PNode:
    """AST node — the core data structure the parser builds."""
    __slots__ = ('kind', 'info', 'flags', 'sons', 'comment',
                 'ident', 'intVal', 'floatVal', 'strVal', 'sym')
    def __init__(self, kind: TNodeKind = TNodeKind.nkNone,
                 info: TLineInfo | None = None):
        self.kind = kind
        self.info = info if info is not None else TLineInfo()
        self.flags: int = 0
        self.sons: list[PNode] = []
        self.comment: str = ""
        # Leaf data — only one is valid depending on kind
        self.ident: PIdent | None = None
        self.intVal: int = 0
        self.floatVal: float = 0.0
        self.strVal: str = ""
        self.sym = None  # PSym stub — for future expansion

    def __len__(self) -> int:
        return len(self.sons)

    def __getitem__(self, i: int) -> 'PNode':
        return self.sons[i]

    def __setitem__(self, i: int, val: 'PNode'):
        self.sons[i] = val

    def add(self, son: 'PNode'):
        self.sons.append(son)

    def addAllowNil(self, son: 'PNode | None'):
        self.sons.append(son)

    @property
    def safeLen(self) -> int:
        if self.kind.value >= TNodeKind.nkStrLit.value and self.kind.value <= TNodeKind.nkTripleStrLit.value:
            return len(self.strVal)
        if self.kind.value <= TNodeKind.nkFloat128Lit.value:
            return 0
        return len(self.sons)

    def hasSon(self) -> bool:
        return len(self.sons) > 0

    @property
    def firstSon(self) -> 'PNode':
        return self.sons[0]

    @property
    def lastSon(self) -> 'PNode':
        return self.sons[-1]

    @property
    def secondSon(self) -> 'PNode':
        return self.sons[1]

    def has2Sons(self) -> bool:
        return len(self.sons) >= 2

    def transitionSonsKind(self, newKind: TNodeKind):
        self.kind = newKind

    def replaceFirstSon(self, newSon: 'PNode'):
        if self.sons:
            self.sons[0] = newSon
        else:
            self.sons.append(newSon)

    def replaceSon(self, idx: int, newSon: 'PNode'):
        self.sons[idx] = newSon

    def setLastSon(self, newSon: 'PNode'):
        if self.sons:
            self.sons[-1] = newSon
        else:
            self.sons.append(newSon)


# --- Constructors ---
def newNode(kind: TNodeKind, info: TLineInfo | None = None) -> PNode:
    return PNode(kind, info)

def newNodeI(kind: TNodeKind, info: TLineInfo) -> PNode:
    return PNode(kind, info)

def newNodeIT(kind: TNodeKind, info: TLineInfo, typ=None) -> PNode:
    n = PNode(kind, info)
    # typ field for future expansion
    return n

def newAtom(kind_or_ident, info_or_val=None, info2=None) -> PNode:
    """Overloaded: newAtom(ident, info) or newAtom(kind, val, info)"""
    if isinstance(kind_or_ident, PIdent):
        result = PNode(TNodeKind.nkIdent, info_or_val)
        result.ident = kind_or_ident
        return result
    kind = kind_or_ident
    if isinstance(info_or_val, int) and not isinstance(info_or_val, bool):
        result = PNode(kind, info2)
        result.intVal = info_or_val
        return result
    if isinstance(info_or_val, float):
        result = PNode(kind, info2)
        result.floatVal = info_or_val
        return result
    if isinstance(info_or_val, str):
        result = PNode(kind, info2)
        result.strVal = info_or_val
        return result
    return PNode(kind, info_or_val)

def newTree(kind: TNodeKind, *children, info: TLineInfo | None = None) -> PNode:
    result = PNode(kind, info)
    for c in children:
        result.sons.append(c)
    if result.sons and info is None:
        result.info = result.sons[0].info
    return result

def newTreeI(kind: TNodeKind, info: TLineInfo, *children) -> PNode:
    result = PNode(kind, info)
    for c in children:
        result.sons.append(c)
    return result

def newIntNode(kind: TNodeKind, intVal: int) -> PNode:
    result = PNode(kind)
    result.intVal = intVal
    return result

def newFloatNode(kind: TNodeKind, floatVal: float) -> PNode:
    result = PNode(kind)
    result.floatVal = floatVal
    return result

def newStrNode(kind: TNodeKind, strVal: str) -> PNode:
    result = PNode(kind)
    result.strVal = strVal
    return result

def newIdentNode(ident: PIdent, info: TLineInfo) -> PNode:
    result = PNode(TNodeKind.nkIdent, info)
    result.ident = ident
    return result


# --- Base flags for number literals ---
def setBaseFlags(n: PNode, base: int):
    if base == 2:
        n.flags |= TNodeFlag.nfBase2
    elif base == 8:
        n.flags |= TNodeFlag.nfBase8
    elif base == 16:
        n.flags |= TNodeFlag.nfBase16


# --- Parser slot indices (used by the parser for routine defs) ---
namePos = 0
patternPos = 1
genericParamsPos = 2
paramsPos = 3
pragmasPos = 4
miscPos = 5
bodyPos = 6

# --- Utility ---
def getPIdent(a: PNode) -> PIdent | None:
    if a.kind == TNodeKind.nkIdent:
        return a.ident
    return None

def isCallExpr(n: PNode) -> bool:
    return n.kind in nkCallKinds


def newProcNode(kind: TNodeKind, info: TLineInfo,
                body: PNode, params: PNode,
                name: PNode, pattern: PNode,
                genericParams: PNode, pragmas: PNode,
                exceptions: PNode) -> PNode:
    """Build a routine definition node with the standard slot layout."""
    result = PNode(kind, info)
    result.sons = [name, pattern, genericParams, params,
                   pragmas, exceptions, body]
    return result


def isNewStyleConcept(n: PNode) -> bool:
    """Check if a concept node uses the new-style syntax (no explicit params)."""
    return (n.kind == TNodeKind.nkTypeClassTy and
            n.hasSon() and n.sons[0].kind == TNodeKind.nkEmpty)


# --- Stub types for future expansion ---
class PSym:
    """Symbol stub — to be expanded when sem/codegen are ported."""
    pass

class PType:
    """Type stub — to be expanded when sem/codegen are ported."""
    pass
