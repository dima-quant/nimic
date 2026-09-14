import compiler/idents
var ic = newIdentCache()
var id1 = ic.getIdent("foo")
var id2 = ic.getIdent("Foo")
echo id1.id
echo id2.id
