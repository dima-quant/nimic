# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/htmlbuilder.nim
# ///
#       Nif library
# (c) Copyright 2026 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Tag-stream builder that targets either HTML (`<tag>body</tag>`) or NIF
## (`(tag body)`). Dagon emits its rendered output through this so the same
## producer can drive a polished HTML build *or* a structural NIF dump that
## downstream tools can re-process. NIF and HTML happen to share the same
## tree-of-named-nodes shape — this module is the thin adapter that exploits
## that overlap.

from __future__ import annotations
from nimic.ntypes import *

from .nifbuilder import addHeader, addKeyw, addStrLit, addTree, attachedToFile, endTree, extract, open
from . import nifbuilder


class HtmlOutFormat(NIntEnum):
    hofHtml = auto()  ## `<tag>body</tag>`
    hofNif = auto()   ## `(tag body)`


class HtmlBuilder(Object):
    format: HtmlOutFormat
    match format:
        case HtmlOutFormat.hofHtml:
            _buf: string
        case HtmlOutFormat.hofNif:
            _nif: nifbuilder.Builder

    def finalize(b: mut @ HtmlBuilder) -> string:
        ## Consume the builder and return the produced text.
        match b.format:
            case HtmlOutFormat.hofHtml: result = move(b._buf)
            case HtmlOutFormat.hofNif: result = extract(move(b._nif))
        return result

    def emitOpen(b: mut @ HtmlBuilder, tag: string):
        match b.format:
            case HtmlOutFormat.hofHtml:
                b._buf.add(ch('<'))
                b._buf.add(tag)
                b._buf.add(ch('>'))
            case HtmlOutFormat.hofNif:
                addTree(b._nif, tag)

    def emitClose(b: mut @ HtmlBuilder, tag: string):
        match b.format:
            case HtmlOutFormat.hofHtml:
                b._buf.add(string("</"))
                b._buf.add(tag)
                b._buf.add(ch('>'))
            case HtmlOutFormat.hofNif:
                endTree(b._nif)

    @template
    def emitTag(b: mut @ HtmlBuilder, tag: string, body: untyped):
        ## Open `tag`, run `body` (which emits children), close `tag`.
        b.emitOpen(tag)
        body
        b.emitClose(tag)

    def emitText(b: mut @ HtmlBuilder, s: string):
        ## Emit user text. HTML-escapes for hofHtml; intern as a NIF string literal
        ## for hofNif.
        match b.format:
            case HtmlOutFormat.hofHtml:
                for c in s:
                    match c:
                        case _ if c == ch('<'): b._buf.add(string("&lt;"))
                        case _ if c == ch('>'): b._buf.add(string("&gt;"))
                        case _ if c == ch('&'): b._buf.add(string("&amp;"))
                        case _: b._buf.add(c)
            case HtmlOutFormat.hofNif:
                addStrLit(b._nif, s)

    def emitVoid(b: mut @ HtmlBuilder, tag: string):
        ## Self-closing tag (`<br>` / `(br)`).
        match b.format:
            case HtmlOutFormat.hofHtml:
                b._buf.add(ch('<'))
                b._buf.add(tag)
                b._buf.add(ch('>'))
            case HtmlOutFormat.hofNif:
                addKeyw(b._nif, tag)

    def _emitAttrValueHtml(b: mut @ HtmlBuilder, v: string):
        for c in v:
            match c:
                case _ if c == ch('<'): b._buf.add(string("&lt;"))
                case _ if c == ch('>'): b._buf.add(string("&gt;"))
                case _ if c == ch('&'): b._buf.add(string("&amp;"))
                case _ if c == ch('"'): b._buf.add(string("&quot;"))
                case _: b._buf.add(c)

    def emitOpenAttr(b: mut @ HtmlBuilder, tag: string,
                     attrs: openArray[tuple[string, string]]):
        ## Open `tag` with key/value attributes. HTML: `<tag k="v" …>`. NIF:
        ## `(tag (k "v") …)` — each attr becomes a child node whose tag is the
        ## attribute name and whose only child is the value as a string literal.
        match b.format:
            case HtmlOutFormat.hofHtml:
                b._buf.add(ch('<'))
                b._buf.add(tag)
                for (k, v) in attrs:
                    b._buf.add(ch(' '))
                    b._buf.add(k)
                    b._buf.add(string("=\""))
                    b._emitAttrValueHtml(v)
                    b._buf.add(ch('"'))
                b._buf.add(ch('>'))
            case HtmlOutFormat.hofNif:
                addTree(b._nif, tag)
                for (k, v) in attrs:
                    addTree(b._nif, k)
                    addStrLit(b._nif, v)
                    endTree(b._nif)

    @template
    def emitTagAttr(b: mut @ HtmlBuilder, tag: string,
                    attrs: openArray[tuple[string, string]], body: untyped):
        ## Open `tag` with attributes, run body, close tag.
        b.emitOpenAttr(tag, attrs)
        body
        b.emitClose(tag)

    def emitClassOpen(b: mut @ HtmlBuilder, cls: string):
        if b.format == HtmlOutFormat.hofHtml:
            b.emitOpenAttr(string("span"), array[1, tuple[string, string]]([(string("class"), cls)]))
        else:
            b.emitOpen(cls)

    def emitClassClose(b: mut @ HtmlBuilder, cls: string):
        if b.format == HtmlOutFormat.hofHtml:
            b.emitClose(string("span"))
        else:
            b.emitClose(cls)

    @template
    def emitClass(b: mut @ HtmlBuilder, cls: string, body: untyped):
        ## Inline classified span. HTML: `<span class="cls">body</span>`.
        ## NIF: `(cls body)` — the class name *is* the tag, since NIF has no
        ## attribute concept and a tagged subtree carries the same semantic.
        b.emitClassOpen(cls)
        body
        b.emitClassClose(cls)


def initHtmlBuilder(format: HtmlOutFormat, sizeHint=1024) -> HtmlBuilder:
    match format:
        case HtmlOutFormat.hofHtml:
            result = HtmlBuilder(format=HtmlOutFormat.hofHtml, _buf=newStringOfCap(sizeHint))
            result._buf.add(string("<!DOCTYPE html>\n"))
        case HtmlOutFormat.hofNif:
            with var:
                nif = nifbuilder.open(sizeHint)
            addHeader(nif, string("Dagon"), string("doc"))
            result = HtmlBuilder(format=HtmlOutFormat.hofNif, _nif=nif)
    return result


if comptime(__name__ == "__main__"):
    def _build(format: HtmlOutFormat) -> string:
        with var:
            b = initHtmlBuilder(format)
        echo(string("format: "), b.format)
        with b.emitTag(string("html")):
            with b.emitTag(string("body")):
                b.emitText(string("plain text"))
                b.emitVoid(string("br"))
                b.emitText(string("a < b > c & d \"q\""))
                with b.emitTagAttr(string("a"), array[2, tuple[string, string]](
                        [(string("href"), string("x?a=1&b=2")), (string("title"), string("<\"T\">"))])):
                    b.emitText(string("link"))
                with b.emitClass(string("kw")):
                    b.emitText(string("proc"))
                    with b.emitClass(string("inner")):
                        b.emitText(string("x"))
                b.emitOpen(string("p"))
                b.emitText(string("open/close"))
                b.emitClose(string("p"))
                b.emitClassOpen(string("c1"))
                b.emitClassClose(string("c1"))
                b.emitOpenAttr(string("div"), array[1, tuple[string, string]]([(string("id"), string("all4<>&\""))]))
                b.emitClose(string("div"))
                with b.emitTagAttr(string("ul"), array[0, tuple[string, string]]()):  # Nim: `[]`
                    b.emitVoid(string("hr"))
        result = b.finalize()
        return result

    def _addedTests():
        echo(_build(HtmlOutFormat.hofHtml))
        echo(_build(HtmlOutFormat.hofNif))

        # an empty builder of each format
        with var:
            e1 = initHtmlBuilder(HtmlOutFormat.hofHtml, 16)
        echo(e1.finalize())
        with var:
            e2 = initHtmlBuilder(HtmlOutFormat.hofNif, 16)
        echo(e2.finalize())

        # the variant's field check: `nif` of an hofHtml builder, `buf` of an hofNif one
        with var:
            h = initHtmlBuilder(HtmlOutFormat.hofHtml)
        try:
            echo(attachedToFile(h._nif))
        except FieldDefect:
            echo(string("FieldDefect: nif of hofHtml"))
        with var:
            n = initHtmlBuilder(HtmlOutFormat.hofNif)
        try:
            echo(n._buf.len)
        except FieldDefect:
            echo(string("FieldDefect: buf of hofNif"))
        echo(n.finalize())

    _addedTests()
