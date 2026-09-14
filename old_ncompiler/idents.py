#
#
#           The Nim Compiler
#        (c) Copyright 2012 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# Identifier handling
# An identifier is a shared immutable string that can be compared by its
# id. This module is essential for the compiler's performance.

# import wordrecg
# import std/hashes
from __future__ import annotations
from nkeywords import *
import system
from wordrecg import *

# when defined(nimPreviewSlimSystem):
#   import std/assertions

# type
#   PIdent* = ref TIdent
#   TIdent*{.acyclic.} = object
#     id*: int # unique id; use this for comparisons and not the pointers
#     s*: string
#     next*: PIdent             # for hash-table chaining
#     h*: Hash                 # hash value of s

#   IdentCache* = ref object
#     buckets: array[0..4096 * 2 - 1, PIdent]
#     wordCounter: int
#     idAnon*, idDelegator*, emptyIdent*: PIdent

class TIdent(nobject):
  """{.acyclic.}"""
  id: int # unique id; use this for comparisons and not the pointers
  s: string
  next: PIdent            # for hash-table chaining
  h: Hash                 # hash value of s

@ref
class  PIdent(TIdent):

  def __eq__(a: PIdent, b: PIdent) -> bool:
    """{.inline.}"""
    if a is None or b is None: result = system.__eq__(a, b)
    else: result = a.id == b.id
    return result

@ref
class  IdentCache(nobject):
  buckets: array[0:4096 * 2, PIdent] # numpy.empty(4096 * 2, str)
  wordCounter: int
  idAnon: PIdent
  idDelegator: PIdent
  emptyIdent: PIdent


  def getIdent(self, identifier: cstring, argA=None, argB=None) -> PIdent:
    """dispatch"""
    if argA:
      if argB:
        return getIdent__DefA(self, cstring(identifier), argA, argB)
      else:
        return getIdent__DefC(self, cstring(identifier), argA)
    elif argB:
      return getIdent__DefC(self, cstring(identifier), argB)
    else:
      return getIdent__DefB(self, cstring(identifier))
      

# proc resetIdentCache*() = discard
def resetIdentCache():
  pass

# proc cmpIgnoreStyle*(a, b: cstring, blen: int): int =
#   if a[0] != b[0]: return 1
#   var i = 0
#   var j = 0
#   result = 1
#   while j < blen:
#     while a[i] == '_': inc(i)
#     while b[j] == '_': inc(j)
#     # tolower inlined:
#     var aa = a[i]
#     var bb = b[j]
#     if aa >= 'A' and aa <= 'Z': aa = chr(ord(aa) + (ord('a') - ord('A')))
#     if bb >= 'A' and bb <= 'Z': bb = chr(ord(bb) + (ord('a') - ord('A')))
#     result = ord(aa) - ord(bb)
#     if (result != 0) or (aa == '\0'): break
#     inc(i)
#     inc(j)
#   if result == 0:
#     if a[i] != '\0': result = 1

def cmpIgnoreStyle(a: cstring, b: cstring, blen: int) -> int:
  if a[0] != b[0]: return 1
  i = 0
  j = 0
  result = 1
  while j < blen:
    while a[i] == '_': i += 1
    while b[j] == '_': j += 1
    # tolower inlined:
    aa = a[i]
    bb = b[j]
    if aa >= 'A' and aa <= 'Z': aa = chr(ord(aa) + (ord('a') - ord('A')))
    if bb >= 'A' and bb <= 'Z': bb = chr(ord(bb) + (ord('a') - ord('A')))
    result = ord(aa) - ord(bb)
    if (result != 0) or (aa == '\0'): break
    i += 1
    j += 1
  if result == 0:
    if a[i] != '\0': result = 1
  return result  

# proc cmpExact(a, b: cstring, blen: int): int =
#   var i = 0
#   var j = 0
#   result = 1
#   while j < blen:
#     var aa = a[i]
#     var bb = b[j]
#     result = ord(aa) - ord(bb)
#     if (result != 0) or (aa == '\0'): break
#     inc(i)
#     inc(j)
#   if result == 0:
#     if a[i] != '\0': result = 1

def cmpExact(a: cstring, b: cstring, blen: int) -> int:
  """{.private.}"""
  i = 0
  j = 0
  result = 1
  while j < blen:
    aa = a[i]
    bb = b[j]
    result = ord(aa) - ord(bb)
    if (result != 0) or (aa == '\0'): break
    i += 1
    j += 1
  if result == 0:
    if a[i] != '\0': result = 1
  return result

# proc getIdent*(ic: IdentCache; identifier: cstring, length: int, h: Hash): PIdent =
#   var idx = h and high(ic.buckets)
#   result = ic.buckets[idx]
#   var last: PIdent = nil
#   var id = 0
#   while result != nil:
#     if cmpExact(cstring(result.s), identifier, length) == 0:
#       if last != nil:
#         # make access to last looked up identifier faster:
#         last.next = result.next
#         result.next = ic.buckets[idx]
#         ic.buckets[idx] = result
#       return
#     elif cmpIgnoreStyle(cstring(result.s), identifier, length) == 0:
#       assert((id == 0) or (id == result.id))
#       id = result.id
#     last = result
#     result = result.next
#   new(result)
#   result.h = h
#   result.s = newString(length)
#   for i in 0..<length: result.s[i] = identifier[i]
#   result.next = ic.buckets[idx]
#   ic.buckets[idx] = result
#   if id == 0:
#     inc(ic.wordCounter)
#     result.id = -ic.wordCounter
#   else:
#     result.id = id


def getIdent__DefA(ic: IdentCache, identifier: cstring, length: int, h: Hash) -> PIdent:
  idx = h and len(ic.buckets)
  result = ic.buckets[idx]
  last: PIdent = None
  id = 0
  while result != None:
    if cmpExact(cstring(result.s), identifier, length) == 0:
      if last != None:
        # make access to last looked up identifier faster:
        last.next = result.next
        result.next = ic.buckets[idx]
        ic.buckets[idx] = result
      return
    elif cmpIgnoreStyle(cstring(result.s), identifier, length) == 0:
      assert((id == 0) or (id == result.id))
      id = result.id
    last = result
    result = result.next
  # result = PIdent()?
  new(result, PIdent)
  result.h = h
  result.s = newString(length)
  for i in range(length): result.s[i] = identifier[i]
  result.next = ic.buckets[idx]
  ic.buckets[idx] = result
  if id == 0:
    ic.wordCounter += 1
    result.id = -ic.wordCounter
  else:
    result.id = id
  return result  


# proc getIdent*(ic: IdentCache; identifier: string): PIdent =
#   result = getIdent(ic, cstring(identifier), identifier.len,
#                     hashIgnoreStyle(identifier))

def getIdent__DefB(ic: IdentCache, identifier: cstring) -> PIdent:
  return getIdent__DefA(ic, cstring(identifier), identifier.len, hashIgnoreStyle(identifier))


# proc getIdent*(ic: IdentCache; identifier: string, h: Hash): PIdent =
#   result = getIdent(ic, cstring(identifier), identifier.len, h)

def getIdent__DefC(ic: IdentCache, identifier: cstring, h: Hash) -> PIdent:
  return getIdent__DefA(ic, cstring(identifier), identifier.len, h)

# proc newIdentCache*(): IdentCache =
#   result = IdentCache()
#   result.idAnon = result.getIdent":anonymous"
#   result.wordCounter = 1
#   result.idDelegator = result.getIdent":delegator"
#   result.emptyIdent = result.getIdent("")
#   # initialize the keywords:
#   for s in succ(low(TSpecialWord))..high(TSpecialWord):
#     result.getIdent($s, hashIgnoreStyle($s)).id = ord(s)


def newIdentCache() -> IdentCache:
  result = IdentCache()
  result.idAnon = result.getIdent(":anonymous")
  result.wordCounter = 1
  result.idDelegator = result.getIdent(":delegator")
  result.emptyIdent = result.getIdent("")
  # initialize the keywords:
  for s in TSpecialWord.range(TSpecialWord.succ(TSpecialWord.low), TSpecialWord.succ(TSpecialWord.high)):
    result.getIdent(string(s), hashIgnoreStyle(string(s))).id = s.ord
  return result

# proc whichKeyword*(id: PIdent): TSpecialWord =
#   if id.id < 0: result = wInvalid
#   else: result = TSpecialWord(id.id)

def whichKeyword(id: PIdent) -> TSpecialWord:
  if id.id < 0: result = TSpecialWord.wInvalid
  else: result = TSpecialWord(id.id)
  return result

# proc hash*(x: PIdent): Hash {.inline.} = x.h


def hash(x: PIdent) -> Hash: 
  """{.inline.}""" 
  return x.h

# proc `==`*(a, b: PIdent): bool {.inline.} =
#   if a.isNil or b.isNil: result = system.`==`(a, b)
#   else: result = a.id == b.id
