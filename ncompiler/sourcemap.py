# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import *
from nimic.std.strscans import *
from nimic.std.parseutils import *
from nimic.std.assertions import *

# =============================================================================
# Types
# =============================================================================

class _Segment(Object):
    """Segment refers to a block of something in the JS output.
    This could be a token or an entire line"""
    original: nint = 0  # Column in the Nim source
    generated: nint = 0  # Column in the generated JS
    name: nint = 0  # Index into names list (-1 for no name)


class _Mapping(Object):
    """Mapping refers to a line in the JS output.
    It is made up of segments which refer to the tokens in the line"""
    inSource: bool = False  # Whether the line in JS has Nim equivalent
    match inSource:
        case True:
            file: nint = 0  # Index into files list
            line: nint = 0  # 0 indexed line of code in the Nim source
            segments: seq[_Segment] = seq[_Segment]()
        case False:
            pass


class _SourceInfo(Object):
    mappings: seq[_Mapping] = seq[_Mapping]()
    names: seq[string] = seq[string]()
    files: seq[string] = seq[string]()

    def _add_segment(info: mut@_SourceInfo, original: nint, generated: nint, name: string = string("")) -> None:
        """Adds a new segment into the current line"""
        assert len(info.mappings) > 0, "No lines have been added yet"
        with var:
            segment = _Segment(original=original, generated=generated, name=-1)
        if name != string(""):
            # Make name be index into names list
            segment.name = info.names.find(name)
            if segment.name == -1:
                segment.name = len(info.names)
                info.names.add(name)

        assert info.mappings[len(info.mappings) - 1].inSource, "Current line isn't in Nim source"
        info.mappings[len(info.mappings) - 1].segments.add(segment)

    def _new_line(info: mut@_SourceInfo) -> None:
        """Add new mapping which doesn't appear in the Nim source"""
        info.mappings.add(_Mapping(inSource=False))

    def _new_line(info: mut@_SourceInfo, file: string, line: nint) -> None:
        """Starts a new line in the mappings. Call addSegment after this to add
        segments into the line"""
        with var:
            mapping = _Mapping(inSource=True, line=line, segments=seq[_Segment]())
        # Set file to file position. Add in if needed
        mapping.file = info.files.find(file)
        if mapping.file == -1:
            mapping.file = len(info.files)
            info.files.add(file)
        info.mappings.add(mapping)


class SourceMap(Object):
    version: nint = 0
    sources: seq[string] = seq[string]()
    names: seq[string] = seq[string]()
    mappings: string = string("")
    file: string = string("")


# =============================================================================
# SourceInfo helpers
# =============================================================================

# =============================================================================
# base64_VLQ encoding
# =============================================================================

def encode(values: seq[nint]) -> string:
    """Encodes a series of integers into a VLQ base64 encoded string"""
    # References:
    #   - https://www.lucidchart.com/techblog/2019/08/22/decode-encoding-base64-vlqs-source-maps/
    #   - https://github.com/rails/sprockets/blob/main/guides/source_maps.md#source-map-file
    with const:
        alphabet = string("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")
        shift = 5
        continueBit = 1 << 5
        mask = continueBit - 1
    result = string("")
    for val in values:
        # Sign is stored in first bit
        with var:
            newVal = abs(val) << 1
        if val < 0:
            newVal = newVal | 1
        # Now comes the variable length part
        # This is how we are able to store large numbers
        while True:
            # We only encode 5 bits.
            with var:
                masked = newVal & mask
            newVal = newVal >> shift
            # If there is still something left
            # then signify with the continue bit that the
            # decoder should keep decoding
            if newVal > 0:
                masked = masked | continueBit
            result.add(alphabet[masked])
            # If the value is zero then we have nothing left to encode
            if newVal == 0:
                break
    return result


# =============================================================================
# Tokenization
# =============================================================================

def tokenize(line: string) -> tuple[nint, string]:
    """Goes through a line and splits it into Nim identifiers and
    normal JS code. This allows us to map mangled names back to Nim names.
    Yields (column, name). Doesn't yield anything but identifiers.
    See mangleName in compiler/jsgen.nim for how name mangling is done"""
    with var:
        col: nint = 0
        token = string("")
    while col < len(line):
        with var:
            token = string("")
            name = string("")
        # First we find the next identifier
        col += line.skipWhitespace(col)
        col += line.skipUntil(IdentStartChars, col)
        with let:
            identStart = col.copy()
        col += line.parseIdent(token, col)
        # Idents will either be originalName_randomInt or HEXhexCode_randomInt
        if token.startsWith(string("HEX")):
            with var:
                _hex = nint(0)
            # 3 = "HEX".len and we only want to parse the two integers after it
            _ = token[3:5].parseHex(_hex)
            name = str(chr(_hex))
        elif not token.endsWith(string("_Idx")):  # Ignore address indexes
            # It might be in the form originalName_randomInt
            with let:
                lastUnderscore = token.rfind(ch('_'))
            if lastUnderscore != -1:
                name = token[0:lastUnderscore]
        if name != string(""):
            yield (identStart, name)


# =============================================================================
# Parsing and SourceMap Generation
# =============================================================================

def parse(source: string) -> _SourceInfo:
    """Parses the JS output for embedded line info
    So it can convert those into a series of mappings"""
    result = _SourceInfo()
    with var:
        skipFirstLine = True
        currColumn: nint = 0
        currLine: nint = 0
        currFile = string("")
    # Add each line as a node into the output
    for line in source.splitLines():
        with var:
            lineNumber = nint(0)
            linePath = string("")
            column = nint(0)
        if line.strip().scanf(string("/* line $i:$i \"$+\" */"), lineNumber, column, linePath):
            # When we reach the first line mappinsegmentg then we can assume
            # we can map the rest of the JS lines to Nim lines
            currColumn = column  # Column is already zero indexed
            currLine = lineNumber - 1
            currFile = linePath
            # Lines are zero indexed
            result._new_line(currFile, currLine)
            # Skip whitespace to find the starting column
            result._add_segment(currColumn, line.skipWhitespace())
        elif currFile != string(""):
            result._new_line(currFile, currLine)
            # There mightn't be any tokens so add a starting segment
            result._add_segment(currColumn, line.skipWhitespace())
            for jsColumn, token in tokenize(line):
                result._add_segment(currColumn, jsColumn, token)
        else:
            result._new_line()
    return result


def toSourceMap(info: _SourceInfo, file: string) -> SourceMap:
    """Convert from high level SourceInfo into the required SourceMap object"""
    # Add basic info
    result = SourceMap(version=3, file=file, sources=info.files, names=info.names)
    # Convert nodes into mappings.
    # Mappings are split into blocks where each block referes to a line in the outputted JS.
    # Blocks can be separated into statements which refere to tokens on the line.
    # Since the mappings depend on previous values we need to
    # keep track of previous file, name, etc
    with var:
        prevFile: nint = 0
        prevLine: nint = 0
        prevName: nint = 0
        prevNimCol: nint = 0

    for mapping in info.mappings:
        # We know need to encode segments with the following fields
        # All these fields are relative to their previous values
        # - 0: Column in generated code
        # - 1: Index of Nim file in source list
        # - 2: Line in Nim source
        # - 3: Column in Nim source
        # - 4: Index in names list
        if mapping.inSource:
            # JS Column is special in that it is reset after every line
            with var:
                prevJSCol: nint = 0
            for segment in mapping.segments:
                with var:
                    values = seq[nint]()
                values.add(segment.generated - prevJSCol)
                values.add(mapping.file - prevFile)
                values.add(mapping.line - prevLine)
                values.add(segment.original - prevNimCol)
                # Add name field if needed
                if segment.name != -1:
                    values.add(segment.name - prevName)
                    prevName = segment.name
                prevJSCol = segment.generated
                prevNimCol = segment.original
                prevFile = mapping.file
                prevLine = mapping.line
                result.mappings.add(encode(values) + string(","))
            # Remove trailing ,
            if len(mapping.segments) > 0:
                result.mappings.setLen(len(result.mappings) - 1)

        result.mappings.add(string(";"))
    return result


def genSourceMap(source: string, outFile: string) -> SourceMap:
    with let:
        node = parse(source)
    result = toSourceMap(node, outFile)
    return result


# =============================================================================
# Standalone Unit Tests
# =============================================================================

if comptime(__name__ == "__main__"):
    echo(string("Testing sourcemap..."))

    # 1. Base64 VLQ encoding tests
    with var:
        v1 = seq[nint]()
    v1.add(0)
    v1.add(0)
    v1.add(0)
    v1.add(0)
    doAssert(encode(v1) == string("AAAA"), string("encode zeros"))

    with var:
        v2 = seq[nint]()
    v2.add(1)
    v2.add(2)
    v2.add(3)
    v2.add(4)
    doAssert(encode(v2) == string("CEGI"), string("encode positive"))

    with var:
        v3 = seq[nint]()
    v3.add(-1)
    v3.add(-2)
    v3.add(-3)
    v3.add(-4)
    doAssert(encode(v3) == string("DFHJ"), string("encode negative"))

    # 2. Tokenize tests
    with var:
        line1 = string("  var myIdent_123 = HEX3F_456; ")
        toks_col = seq[nint]()
        toks_name = seq[string]()
    for c, tok in tokenize(line1):
        toks_col.add(c)
        toks_name.add(tok)
    doAssert(len(toks_col) == 2, string("tokenize count"))
    doAssert(toks_col[0] == 6 and toks_name[0] == string("myIdent"), string("token 0"))
    doAssert(toks_col[1] == 20 and toks_name[1] == string("?"), string("token 1"))

    # Address index ignored
    with var:
        line_idx = string("var addr_Idx = 0;")
        idx_count: nint = 0
    for c, tok in tokenize(line_idx):
        idx_count += 1
    doAssert(idx_count == 0, string("tokenize ignore _Idx"))

    # 3. Full SourceMap generation test
    with let:
        js_source = string("/* line 1:0 \"hello.nim\" */\nvar x_123 = 42;\n/* line 2:5 \"hello.nim\" */\necho(x_123);\n")
        sm = genSourceMap(js_source, string("hello.js.map"))
    doAssert(sm.version == 3, string("version"))
    doAssert(len(sm.sources) == 1 and sm.sources[0] == string("hello.nim"), string("sources"))
    doAssert(len(sm.names) == 1 and sm.names[0] == string("x"), string("names"))
    doAssert(sm.mappings == string("AAAA;AAAA,IAAAA;AACK;AAAA,KAAAA;AAAA;"), string("mappings"))
    doAssert(sm.file == string("hello.js.map"), string("file"))

    # 4. Multi-byte VLQ encoding edge cases (continuation bit)
    with var:
        v4 = seq[nint]()
    v4.add(16)
    v4.add(-16)
    v4.add(100)
    doAssert(encode(v4) == string("gBhBoG"), string("encode multi-byte VLQ"))

    # 5. Tokenize edge cases
    with var:
        line_plain = string("var plain = 1;")
        plain_count: nint = 0
    for c, tok in tokenize(line_plain):
        plain_count += 1
    doAssert(plain_count == 0, string("tokenize ignore plain without underscore"))

    # 6. SourceMap with unmapped preamble and multiple identifiers on a line
    with let:
        js_source2 = string("// preamble comment\n/* line 1:0 \"foo.nim\" */\nvar a_1 = b_2;\n")
        sm2 = genSourceMap(js_source2, string("foo.js.map"))
    doAssert(sm2.version == 3, string("version 2"))
    doAssert(len(sm2.sources) == 1 and sm2.sources[0] == string("foo.nim"), string("sources 2"))
    doAssert(len(sm2.names) == 2, string("names count 2"))
    doAssert(sm2.names[0] == string("a") and sm2.names[1] == string("b"), string("names 2"))
    doAssert(sm2.mappings == string(";AAAA;AAAA,IAAAA,MAAAC;AAAA;"), string("mappings with preamble"))
    doAssert(sm2.file == string("foo.js.map"), string("file 2"))

    echo(string("All sourcemap tests passed successfully!"))
