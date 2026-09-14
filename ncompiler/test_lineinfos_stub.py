    import nimic.std.assertions

    link = createDocLink(string("foo"))
    assert link == string("https://nim-lang.github.io/Nim/foo")

    link2 = createDocLink(string("/bar"))
    assert link2 == string("https://nim-lang.github.io/Nim/bar")

    msgConfig = initMsgConfig()
    assert msgConfig.lastError == unknownLineInfo
    assert string("???") in msgConfig.filenameToIndexTbl
    assert msgConfig.filenameToIndexTbl[string("???")] == FileIndex(-1)
    
    assert MsgKindToStr[TMsgKind.errUnknown] == string("unknown error")
    
    print("All lineinfos tests passed.")
