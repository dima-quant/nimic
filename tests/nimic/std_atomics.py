# /// nimic
#
# ///
## std/atomics in Python (the nimic shim) and in compiled Nim: the default value, load / store / exchange,
## compareExchange (success, and failure loading the value into `expected`), fetchAdd / fetchSub / fetchAnd /
## fetchOr / fetchXor, atomicInc / atomicDec, `+=` / `-=`, wrapping like C11 atomics, AtomicFlag, and Nim's method
## syntax of these procs (vfs's `atomicWriteCounter.fetchAdd(1)`; tests/verify_transpiled.py nimic compares the outputs).
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.atomics import *
from nimic.std.atomics import fetchAdd


if comptime(__name__ == "__main__"):
    def _main():
        with var:
            counter = Atomic[nint]()
        echo(string("default "), load(counter))
        echo(string("fetchAdd "), fetchAdd(counter, 1), string(" "), fetchAdd(counter, 1), string(" now "), load(counter))
        store(counter, 10)
        echo(string("exchange "), exchange(counter, 20), string(" now "), load(counter))
        with var:
            expected = nint(20)
        echo(string("cas hit "), compareExchange(counter, expected, 30), string(" now "), load(counter), string(" expected "), expected)
        expected <<= 5
        echo(string("cas miss "), compareExchange(counter, expected, 40), string(" now "), load(counter), string(" expected "), expected)
        echo(string("cas order "), compareExchange(counter, expected, 41, moRelaxed), string(" now "), load(counter))
        echo(string("cas orders "), compareExchangeWeak(counter, expected, 42, moAcquire, moRelaxed), string(" now "), load(counter))
        echo(string("fetchSub "), fetchSub(counter, 2), string(" now "), load(counter))
        echo(string("fetchAnd "), fetchAnd(counter, 12), string(" now "), load(counter))
        echo(string("fetchOr "), fetchOr(counter, 3), string(" now "), load(counter))
        echo(string("fetchXor "), fetchXor(counter, 5), string(" now "), load(counter))
        atomicInc(counter)
        atomicInc(counter, 10)
        atomicDec(counter, 3)
        echo(string("inc / dec "), load(counter))
        counter += 100
        counter -= 1
        echo(string("+= / -= "), load(counter))
        with var:
            small = Atomic[uint8]()
        store(small, uint8(255))
        echo(string("uint8 wraps "), fetchAdd(small, uint8(1)), string(" now "), load(small))
        with var:
            signed = Atomic[int8]()
        store(signed, int8(127))
        echo(string("int8 wraps "), fetchAdd(signed, int8(1)), string(" now "), load(signed))
        with var:
            flag = AtomicFlag()
        echo(string("flag "), testAndSet(flag), string(" "), testAndSet(flag))
        clear(flag)
        echo(string("cleared "), testAndSet(flag, moAcquire))
        with var:
            seqNo = Atomic[nint]()
        echo(string("method fetchAdd "), seqNo.fetchAdd(1), string(" "), seqNo.fetchAdd(1), string(" now "), seqNo.load())
        seqNo.store(7)
        seqNo.atomicInc()
        echo(string("method exchange "), seqNo.exchange(1), string(" fetchSub "), seqNo.fetchSub(1), string(" now "), seqNo.load())
        flag.clear()
        echo(string("method flag "), flag.testAndSet(), string(" "), flag.testAndSet())
        fence(moSequentiallyConsistent)
        signalFence(moRelease)

    _main()
