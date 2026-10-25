# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/intrinsics.nim
# ///
#
#           The intrinsic table
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this distribution.
#

## The single source of truth for `{.instruction: "X".}` / `{.intrinsic: "X".}`.
##
## An intrinsic is declared as an ordinary proc prototype, so overload
## resolution, `sigmatch` and `getType` need no special cases. What a proc
## signature *cannot* express — operand roles, two-address ties, target
## availability, purity — lives here, in one row per opcode, and is checked
## **once, at the declaration**: after `sempragmas` has unified the row's shape
## against the declared signature, the symbol is an ordinary typed proc and
## nothing downstream ever consults the shape again.
##
## Two repositories read this file:
##
## * nimony's `sempragmas` resolves the pragma's name to an `IntrinsicOp`,
##   unifies the signature against the row and rejects a mismatch at the
##   declaration site.
## * arkham (`nativenif`) reads `targets` to answer "does this target have that
##   instruction?" and `tie` / `effects` to drive allocation. The per-target
##   *encoding* is not here — that is `doc/instructions.md` plus the backend's
##   `emitInstr`, and nifasm (a typed assembler) is the backstop that catches a
##   row which is wrong or too loose.
##
## The file is deliberately dependency-free (plain data, no NIF API), so both
## the nifstreams-based front end and the nifcore-based back end can use it
## without dragging in the other's cursor type.

from __future__ import annotations
from nimic.ntypes import *


class IntrinsicOp(NIntEnum):
    NoIntrinsicOp = auto()
    # ── portable (`{.intrinsic: "X".}`): a lowering exists on every target,
    #    possibly as several instructions.
    CtzOp = auto()
    ClzOp = auto()
    PopcountOp = auto()
    BswapOp = auto()
    # ── target-pinned (`{.instruction: "X".}`): exactly one machine instruction.
    #    The name is the nifasm instruction tag.
    BsfOp = auto()
    BsrOp = auto()
    PopcntOp = auto()
    BswapPinnedOp = auto()
    RolOp = auto()
    RorOp = auto()
    ClzPinnedOp = auto()
    RbitOp = auto()
    RevOp = auto()
    # ── flags. Two shapes: an instruction that DEFINES flags and returns
    #    nothing, and a zero-operand `bool` that READS one. There is no flag
    #    type and no flag variable — see `doc/intrinsics.md` §6.
    CmpOp = auto()
    TestOp = auto()
    ZfOp = auto()
    NotZfOp = auto()
    CfOp = auto()
    NotCfOp = auto()
    SfOp = auto()
    NotSfOp = auto()
    OfOp = auto()
    NotOfOp = auto()
    PfOp = auto()
    NotPfOp = auto()
    # ── two-address arithmetic: `roInout` on operand 0, no result. These are the
    #    rows the `d = ins(x)` spelling cannot express, so §4.1 gives them the
    #    `ins(var d, x)` form instead.
    AddOp = auto()
    SubOp = auto()
    AndOp = auto()
    OrOp = auto()
    XorOp = auto()
    ShlOp = auto()
    ShrOp = auto()
    SarOp = auto()
    NegOp = auto()
    NotOp = auto()
    IncOp = auto()
    DecOp = auto()
    # ── atomics (`{.intrinsic: "AtomicX".}`). Portable: every target has a
    #    lock-free lowering, though rarely as ONE instruction — x86-64 spells an
    #    RMW `lock xadd` / a `lock cmpxchg` retry loop, AArch64 an LL/SC
    #    `ldaxr`/`stlxr` loop. That is precisely what `icPortable` means, and it
    #    is why these are rows here rather than `importc: "__atomic_*"` calls:
    #    an atomic is an OPCODE, and calling it a call made every consumer treat
    #    an inline instruction sequence as an ABI call point.
    AtomicLoadOp = auto()
    AtomicStoreOp = auto()
    AtomicExchangeOp = auto()
    AtomicCompareExchangeOp = auto()
    AtomicFetchAddOp = auto()
    AtomicFetchSubOp = auto()
    AtomicFetchAndOp = auto()
    AtomicFetchOrOp = auto()
    AtomicFetchXorOp = auto()
    AtomicAddFetchOp = auto()
    AtomicSubFetchOp = auto()
    AtomicTestAndSetOp = auto()
    AtomicClearOp = auto()
    AtomicThreadFenceOp = auto()
    AtomicSignalFenceOp = auto()
    # ── the spin-wait hint (`{.intrinsic: "CpuRelax".}`). Portable in the same
    #    sense the fences are: every target has the mechanism and no two spell it
    #    alike — `pause` on x86-64, `yield` on both Arm profiles, nothing at all
    #    on a target that has neither. Deliberately NOT one of the atomics above
    #    (`isAtomic` is an ordinal range, and this row shares none of their
    #    machinery): it moves no data, touches no cell and orders nothing. It is
    #    a hint to the core that the loop around it is waiting on another core.
    CpuRelaxOp = auto()
    # ── AdvSIMD/NEON vector rows (`{.instruction.}`, AArch64). The shoggoth
    #    vectorizer synthesizes their declarations and emits `(instr …)`
    #    applications; user code can also declare them. The vector VALUE type is
    #    the opaque `(f 128)` (see `ptVec128`); lane meaning rides the opcode
    #    plus its trailing lane-bits literal.
    FldrqOp = auto()  # vec = fldrq(p: pointer; off: int)  — 16-byte load  [p+off]
    FstrqOp = auto()  # fstrq(p: pointer; off: int; v: vec) — 16-byte store [p+off]
    VfaddOp = auto()  # vec = vfadd(a, b: vec; lanebits)   — lane-wise fp add
    VfsubOp = auto()  # vec = vfsub(a, b: vec; lanebits)
    VfmulOp = auto()  # vec = vfmul(a, b: vec; lanebits)
    VfmlaOp = auto()  # vec = vfmla(acc, a, b: vec; lanebits) — fused acc + a*b; the
                 # result is tied to `acc` (the machine op accumulates in place)
    VdupOp = auto()  # vec = vdup(x: F; lanebits)         — broadcast x to every lane
    VaddvOp = auto()  # F = vaddv(v: vec; lanebits)        — horizontal fp add of every
                 # lane into a scalar (the reduction epilogue)
    # ── the machine facts a stack walk needs (`lib/std/stacktraces`). Both are
    #    portable rows: the CONCEPT is target-neutral, the instruction is not.
    StackPointerOp = auto()
    TraceTableOp = auto()
    # ── the size of one thread's thread-local block (`lib/std/rawthreads`). A
    #    thread the runtime creates itself needs storage for every `{.threadvar.}`
    #    in the program, and how many bytes that is is a LINK-time fact: nifasm
    #    lays every module's thread-locals into one block and only then knows how
    #    big it got. So the row answers with the ADDRESS of the number, exactly as
    #    `TraceTable` answers with the address of the table — one `lea` against a
    #    label the assembler owns — rather than an immediate no compilation unit
    #    could have supplied.
    TlsSizeOp = auto()
    # ── the valgrind client request (`lib/std/valgrind`). Portable in the same
    #    sense: every target has the mechanism, none spells it the same way.
    VgClientRequestOp = auto()
    # ── volatile access (`lib/std/volatile`). One load, one store, at exactly
    #    the pointee's width, that no pass may duplicate, elide, reorder against
    #    another volatile, or fold. This is MMIO: reading a status register is
    #    how you learn something changed, and writing a command register is the
    #    something that happens — so the value is beside the point and the ACCESS
    #    is the whole content.
    VolatileLoadOp = auto()
    VolatileStoreOp = auto()
    # ── the heap a bare-metal image was GIVEN (`lib/std/system/osalloc`). Two
    #    link-time facts: a hosted program asks its OS for pages, and a firmware
    #    image has whatever the board layout reserved for it and not one byte
    #    more. The numbers are the image writer's, so the row is how the runtime
    #    reaches them rather than something it can compute.
    HeapStartOp = auto()
    HeapSizeOp = auto()
    # ── the region the startup code was told to LEAVE ALONE. Everything else in
    #    RAM is established at reset — `.data` copied in, `.bss` zeroed — and a
    #    reboot counter or a crash record is exactly the thing that must not be:
    #    it is written by the run that failed and read by the run after it.
    #    Survives a warm reset, not a power cycle.
    NoinitStartOp = auto()
    NoinitSizeOp = auto()
    # ── the debugger trap (`lib/std/semihosting`). ARMv7-M's `bkpt #imm8` is how
    #    a bare-metal image asks a debug agent for anything at all: the ARM
    #    semihosting protocol is `bkpt #0xAB` with an operation number in r0 and
    #    a parameter block address in r1. The ROW is just the instruction — it
    #    has no operands but the immediate the encoding carries, and it names no
    #    register, which is why a semihosting call is written in an
    #    `{.assembler.}` body where r0/r1 can be said out loud. Its result comes
    #    back in r0, which the row cannot describe and the body simply reads.
    BkptOp = auto()
    # ── the same protocol, RISC-V's spelling. A semihosting call there is not one
    #    instruction but a fixed THREE — `slli x0,x0,0x1f`, `ebreak`,
    #    `srai x0,x0,7` — whose outer two are architectural no-ops that exist only
    #    so a debug agent can recognise the middle one as a semihosting request
    #    rather than an ordinary breakpoint. That is why this is its own row and
    #    not `bkpt` with a different encoding: `bkpt` takes the magic number as an
    #    operand, and here the magic is the surrounding instructions.
    #
    #    Nullary and void, for the same reason `bkpt` is: the operation number and
    #    the parameter block live in a0/a1, which an `{.assembler.}` body names out
    #    loud, and the result comes back in a0 where the body reads it.
    SemihostOp = auto()
    # ── the raw kernel entry (`lib/std/rawthreads`). One instruction, and the
    #    ONLY way a libc-free image can create a thread: `clone` is not callable
    #    from compiled code, because the child resumes at the instruction after
    #    the syscall with a DIFFERENT stack pointer — every local the surrounding
    #    proc had is gone, and its epilogue would pop from a stack that never held
    #    a frame. So the sequence has to be written where the stack is said out
    #    loud, i.e. an `{.assembler, naked.}` body, and this row is what lets one
    #    say `syscall`.
    #
    #    Nullary and void for the same reason `bkpt` and `semihost` are: the
    #    number is in rax and the arguments in rdi/rsi/rdx/r10/r8/r9 because the
    #    body put them there, and the result comes back in rax where the body
    #    reads it. No column here can describe that, and in an `.assembler` proc
    #    none needs to — there is no allocator to inform.
    SyscallOp = auto()
    # ── multi-word arithmetic and branch-free selection (x86-64). These are
    #    what constant-time code is MADE of: a carry chain (`adc`/`sbb`) and a
    #    full 64x64->128 product (`mul`) are how a field element wider than a
    #    register is added and multiplied without a data-dependent branch, and a
    #    conditional move (`cmovCC`) is how a secret-dependent choice is made
    #    without one. Every row that READS a flag (`uses != {}`) and `mul`, whose
    #    second result is a fixed register no signature can name, is legal only
    #    inside an `{.assembler.}` proc: anywhere else an instruction the
    #    compiler inserted could sit between the flag's definition and its use.
    AdcOp = auto()
    SbbOp = auto()
    MulOp = auto()  # mul(var lo, var hi, s): rdx:rax = rax * s. `lo` must live in
                 # rax and `hi` in rdx — the instruction has no other form.
    ImulOp = auto()  # imul(var d, s): d = low half of d * s
    CmovzOp = auto()
    CmovnzOp = auto()
    CmovcOp = auto()
    CmovncOp = auto()
    CmovsOp = auto()
    CmovnsOp = auto()
    CmovoOp = auto()
    CmovnoOp = auto()
    CmovaOp = auto()
    CmovbeOp = auto()
    CmovlOp = auto()
    CmovgeOp = auto()
    CmovgOp = auto()
    CmovleOp = auto()
    # ── the same building blocks for the Arm ports (AArch64 and ARMv7-M). Arm
    #    is three-address, and its flag-setting arithmetic is a separate
    #    mnemonic (`adds` versus `add`), so a carry chain is a sequence of
    #    VALUE rows that also define flags. Spelled as nifasm spells them (the
    #    `3` marks the three-operand form). A row claims a target only once a
    #    backend lowers it — claiming one arkham cannot yet emit would turn its
    #    clean "no lowering" rejection into a crash: AArch64 has the carry
    #    chain, `mul3`, `umulh` and the `csel`s; `umull`, `umlal` and `bic3`
    #    wait for the Cortex-M port.
    Adds3Op = auto()  # d = adds3(a, b): a + b, setting NZCV
    Adcs3Op = auto()  # d = adcs3(a, b): a + b + C, setting NZCV
    Subs3Op = auto()  # d = subs3(a, b): a - b, setting NZCV (C = NOT borrow, Arm's sense)
    Sbcs3Op = auto()  # d = sbcs3(a, b): a - b - NOT C, setting NZCV
    Mul3Op = auto()  # d = mul3(a, b): the low half of a * b
    UmulhOp = auto()  # d = umulh(a, b): the high 64 bits of a * b (AArch64)
    UmullOp = auto()  # umull(var lo, var hi, a, b): hi:lo = a * b (ARMv7-M, 32x32->64)
    UmlalOp = auto()  # umlal(var lo, var hi, a, b): hi:lo += a * b (ARMv7-M)
    Bic3Op = auto()  # d = bic3(a, b): a and not b — a mask select in one instruction
    CseleqOp = auto()  # d = cselCC(a, b): a if the condition holds, else b (AArch64)
    CselneOp = auto()
    CselltOp = auto()
    CselleOp = auto()
    CselgtOp = auto()
    CselgeOp = auto()
    CselloOp = auto()
    CsellsOp = auto()
    CselhiOp = auto()
    CselhsOp = auto()

    def isMachineQuery(op: IntrinsicOp) -> bool:
        """{.inline.}"""
        ## A row that reads a machine or link-time fact instead of computing on
        ## operands: no sources, a pointer result, and a lowering that is one
        ## instruction with nothing to place. The back ends need the distinction
        ## because every other zero-operand row is a FLAG read, whose result cannot be
        ## materialised at all — these produce an ordinary register value.
        return op in Tset[IntrinsicOp](IntrinsicOp.StackPointerOp, IntrinsicOp.TraceTableOp, IntrinsicOp.TlsSizeOp)

    def isAtomic(op: IntrinsicOp) -> bool:
        """{.inline.}"""
        ## An atomic row. The back ends lower these as a self-contained instruction
        ## SEQUENCE rather than a transliteration, so they branch on this once instead of
        ## listing the opcodes at every site.
        return ord(op) >= ord(IntrinsicOp.AtomicLoadOp) and ord(op) <= ord(IntrinsicOp.AtomicSignalFenceOp)

    def isVolatile(op: IntrinsicOp) -> bool:
        """{.inline.}"""
        ## A volatile access. Two of them may not be reordered against each other, may
        ## not be merged, and may not be deleted — a rule about the PAIR, so it cannot
        ## live in either row's `effects` and is enforced where ordering is decided.
        return op == IntrinsicOp.VolatileLoadOp or op == IntrinsicOp.VolatileStoreOp


class IntrinsicClass(NIntEnum):
    ## What kind of NAME the opcode is — fixed when the row is authored, and NOT
    ## derivable from `targets`, which is availability and grows as the backends
    ## do. A pinned row can be available everywhere (`mov`/`add`/`cmp` are both
    ## `X64Inst` and `A64Inst`) and is still pinned: `{.instruction: "add".}` means
    ## the machine's two-address add, not "a portable addition". A portable row
    ## can be missing on a target (`Popcount`, until a64 gets a lowering) and is
    ## still portable. Deriving the class from `targets` would also make a
    ## declaration's legal spelling flip the day a backend gains an expansion.
    icPortable = auto()  ## `{.intrinsic: "X".}` — target-neutral opcode, any expansion
    icPinned = auto()  ## `{.instruction: "X".}` — one named machine instruction


class IntrinsicTarget(NIntEnum):
    tgX64 = auto()  ## x86-64
    tgA64 = auto()  ## AArch64
    tgThumbM = auto()  ## Thumb-2 / Cortex-M. Newer than most of the table: rows that
                 ## predate the target do not claim it, and arkham's Arm emitter
                 ## read `tgA64` for both Arm targets while no row distinguished
                 ## them. It asks for the target it is actually emitting now, so
                 ## a row claims Cortex-M only where the lowering was checked —
                 ## the volatile rows, and the `cmp`/flag-read rows the
                 ## `{.assembler.}` mode needs to branch.
    tgRv32 = auto()  ## RV32IMAFD, bare metal.


class OperandRole(NIntEnum):
    roIn = auto()  ## a pure source
    roOut = auto()  ## a pure destination
    roInout = auto()  ## read *and* written (needs the `var`-first spelling)


class IntrinsicEffect(NIntEnum):
    efPure = auto()  ## no memory effect, no trap: CSE / fold / DCE eligible
    efReads = auto()  ## reads memory through a pointer operand
    efWrites = auto()  ## writes memory through a pointer operand
    efBarrier = auto()  ## no memory reordering across it


class MachineFlag(NIntEnum):
    ## The condition-code bits both targets expose. x86-64 has all five; AArch64's
    ## NZCV covers the same ground under other names (Z, C, N, V — no parity).
    ## They are named here so a row can say WHICH flag it defines or reads, which
    ## is what makes `zf()` checkable without a flag type: the column carries what
    ## a `bool` return cannot.
    mfZF = auto()
    mfCF = auto()
    mfSF = auto()
    mfOF = auto()
    mfPF = auto()


class PatKind(NIntEnum):
    ## The type-pattern vocabulary. `…W` binds (or matches) the row's single
    ## width variable `W`, so `(u W) -> (u W)` says "same width in and out"
    ## without enumerating widths. This is a first-order pattern language;
    ## unification is the `matchPat` each front end writes over its own cursors.
    ptNone = auto()  ## unused operand slot
    ptVoid = auto()  ## no result
    ptBool = auto()
    ptIntW = auto()  ## `(i W)`
    ptUIntW = auto()  ## `(u W)`
    ptAnyIntW = auto()  ## `(i W)` | `(u W)` | `(c W)`
    ptInt32 = auto()  ## `(i 32)` — fixed width, does not bind `W`
    ptAnyInt = auto()  ## any integer, width unconstrained and unbound
    ptValW = auto()  ## the type an atomic operates ON — an integer (binding `W`) or a
                 ## POINTER, which is a machine word and binds 64. A free-list head
                 ## and an ARC counter are both atomic cells; only one of them is a
                 ## number, so this is deliberately wider than `ptAnyIntW`.
    ptPtrW = auto()  ## `ptr X` where X matches `ptValW` — an atomic's memory operand.
                 ## The pointee is what fixes the ACCESS WIDTH, and getting that
                 ## wrong is not a slow program but a corrupt neighbouring field,
                 ## so the row names the relationship instead of leaving it to the
                 ## back end to guess.
    ptRawPtr = auto()  ## a bare `pointer` — the byte-wide flag cell of `AtomicTestAndSet`
                 ## / `AtomicClear`, which have no pointee type to read a width from
                 ## (C says a flag is a byte, and both back ends agree).
    ptMemOrder = auto()  ## a `__ATOMIC_*` memory-order argument. See `matchPat`: v1 accepts
                 ## any type here because v1 reads none.
    ptWeak = auto()  ## `AtomicCompareExchange`'s `weak` flag: a `bool` that says a
                 ## spurious failure is acceptable. v1 reads none either — both
                 ## lowerings are the strong form, which is always a legal answer.
    ptVec128 = auto()  ## a 128-bit SIMD register value, spelled `(f 128)` in Leng: an
                 ## opaque bag of bits whose LANE interpretation lives entirely in
                 ## the opcode (and its trailing lane-bits operand), exactly as it
                 ## does in the machine's register file. Only the vector rows below
                 ## use it, and only the native back ends lower them.
    ptFloatW = auto()  ## `(f W)` — a scalar float binding the width variable (the lane
                 ## width a `vdup` broadcast replicates).
    ptAnyPtr = auto()  ## any pointer (`ptr`/`aptr` of anything): a vector load/store's
                 ## address operand. The ACCESS width is the instruction's own 16
                 ## bytes — deliberately not derived from the pointee, matching the
                 ## hardware (and `movdqu`'s documented behavior in nifasm).
    ptLaneBits = auto()  ## the trailing lane-width knob of the vector rows: an int LITERAL
                 ## (32 or 64) the back end reads at the call site to pick the
                 ## `.4s`/`.2d` arrangement. Like `ptMemOrder` it is not evaluated —
                 ## see `evaluatedOperands` — but unlike it, the back end DOES read
                 ## its literal value.
    ptImmLit = auto()  ## an operand the INSTRUCTION encodes rather than reads from a
                 ## register: `bkpt #imm8`'s comment field. Like `ptLaneBits` it is
                 ## never evaluated (`evaluatedOperands`) and its literal value is
                 ## read at the call site — the difference is only what it means,
                 ## and a row that shared `ptLaneBits` for it would be telling the
                 ## reader it selects a lane arrangement. A non-literal argument is
                 ## a back-end error naming the operand, because there is no
                 ## register form to fall back to.


with const:
    MaxOperands = 6
      ## `AtomicCompareExchange` is the widest row: pointer, expected, desired,
      ## `weak`, and a memory order for each of the success and failure paths.
      ## Nothing depends on the exact value.


class IntrinsicRow(Object):
    cls: IntrinsicClass
    targets: Tset[IntrinsicTarget]  ## where the opcode exists at all
    arity: nint  ## number of *source* operands (= params)
    params: array[MaxOperands, PatKind]
    roles: array[MaxOperands, OperandRole]
    ret: PatKind
    widths: Tset[uint8]  ## the widths `W` may bind to
    tie: nint  ## source-operand index the destination must
                                    ## alias (a two-address form), or -1. The
                                    ## allocator inserts the copy this needs —
                                    ## the same service the accumulator model
                                    ## already provides for built-in operators.
    effects: Tset[IntrinsicEffect]
    uses: Tset[MachineFlag]  ## flags the row READS. A row with a `ptBool`
                                    ## result and a non-empty `uses` IS a flag
                                    ## read — the only shape that can produce a
                                    ## value with no register behind it.
    defs: Tset[MachineFlag]  ## flags the row WRITES. Documentation in v1
                                    ## (nothing consults it yet), and the column a
                                    ## v2 needs to prove no instruction clobbered
                                    ## a flag between its definition and its read
                                    ## — the check §6 defers.

    def isFlagRead(r: IntrinsicRow) -> bool:
        """{.inline.}"""
        ## A row whose value IS a machine flag rather than a register: `bool` result,
        ## no operands, and a `uses` naming the bit. Such a value cannot be stored,
        ## passed or returned — the instruction that would materialise it (`setcc`) is
        ## itself a flag reader, and anything emitted between the definition and the
        ## read may have clobbered the bit. v1 therefore allows it in exactly one
        ## place: an `if` condition. See `doc/intrinsics.md` §6.
        return r.ret == PatKind.ptBool and r.uses != Tset[MachineFlag]()

    def inoutOperand(r: IntrinsicRow) -> nint:
        ## The index of the row's `inout` operand, or -1. Such a row has no result: it
        ## writes through that operand, which is spelled `var` in the declaration and
        ## arrives as `(haddr d)` at the call site.
        result = nint(-1)
        for i in range(r.arity):
            if r.roles[i] == OperandRole.roInout: return i
        return result

    def isFlagValue(r: IntrinsicRow) -> bool:
        """{.inline.}"""
        ## A row with a VALUE that also defines flags, as a separate instruction from
        ## its non-flag-setting twin: Arm's `adds`/`subs`. The value alone is `+`; the
        ## row exists for the flags, which only an `{.assembler.}` body can read.
        return r.ret not in Tset[PatKind](PatKind.ptVoid, PatKind.ptNone) and r.defs != Tset[MachineFlag]() and r.inoutOperand() < 0

    def isAssemblerOnly(r: IntrinsicRow) -> bool:
        ## A row no compiled code may contain: it READS a flag (`adc`, `cmovz`), so
        ## nothing may run between the instruction that set the flag and this one, it
        ## exists only to SET flags alongside a value (`adds3`), or it writes a result
        ## no signature can place (`mul`'s high half, `umull`'s pair, `umlal`'s
        ## accumulator pair). Only an `{.assembler.}` body, where no instruction is
        ## ever inserted, can use it.
        if r.uses != Tset[MachineFlag]() or r.isFlagValue(): return True
        with var:
            written = nint(0)
        for i in range(r.arity):
            if r.roles[i] == OperandRole.roOut: return True
            if r.roles[i] == OperandRole.roInout: written += 1
        # two results (`umlal`'s register pair) are more than the allocator's
        # one-tied-operand model can place
        result = written > 1
        return result

    def isFlagWrite(r: IntrinsicRow) -> bool:
        """{.inline.}"""
        ## A row whose ONLY output is flags (`cmp`, `test`): it must be a STATEMENT,
        ## since there is no value to bind, and it must not be deleted for having none.
        ## The `inout` exclusion matters: `add` is also void and also sets every flag,
        ## but its result goes to a register, so it is an ordinary instruction that
        ## happens to define flags — not a flag instruction.
        return r.ret == PatKind.ptVoid and r.defs != Tset[MachineFlag]() and r.inoutOperand() < 0

    def isVoidResult(r: IntrinsicRow) -> bool:
        """{.inline.}"""
        ## A row that yields no value AND writes no declared operand: `AtomicStore`,
        ## `AtomicClear`, the fences. Distinct from both neighbours — a flag row's output
        ## IS the flags (`isFlagWrite`) and a two-address row's goes back through operand
        ## 0 (`inoutOperand`), while here there is nothing to read afterwards at all. The
        ## whole content is in `effects`, and it is `effects` that keeps such a row alive.
        ## The back ends need this to know NOT to home a result register for the node.
        return r.ret == PatKind.ptVoid and r.defs == Tset[MachineFlag]() and r.inoutOperand() < 0

    def isNullaryVoid(r: IntrinsicRow) -> bool:
        """{.inline.}"""
        ## A row with no operands AND no output of any kind: `CpuRelax`. The back ends
        ## need it named because their operand machinery is written around
        ## `argCurs[0]` existing — `isMachineQuery` is the same shape with a register
        ## result and gets the same early exit for the same reason. Everything such a
        ## row does is in `effects`, so the lowering is "emit the opcode, bind
        ## nothing".
        return r.arity == 0 and r.isVoidResult()

    def hasInoutOperand(r: IntrinsicRow) -> bool:
        ## A row the `d = ins(x)` spelling cannot express — it needs `ins(var d, x)`,
        ## which v1 rejects at the declaration rather than lowering half-way.
        result = False
        for i in range(r.arity):
            if r.roles[i] == OperandRole.roInout: return True
        return result


with const:
    IntrinsicNames = array[IntrinsicOp, string]([
      string(""), string("Ctz"), string("Clz"), string("Popcount"), string("Bswap"),
      string("bsf"), string("bsr"), string("popcnt"), string("bswap"), string("rol"), string("ror"), string("clz"), string("rbit"), string("rev"),
      string("cmp"), string("test"),
      # nifasm's own condition tags, verbatim — `of` and `no` included. They were
      # once `ovf`/`novf` because the pragma argument was an IDENT, and a Nim keyword
      # cannot be written where an expression is expected; inside a string literal a
      # keyword is just text, so the cover names are gone.
      string("zf"), string("nz"), string("cf"), string("nc"), string("sf"), string("ns"), string("of"), string("no"), string("pf"), string("np"),
      # The rule, now without exceptions: THE SOURCE NAME IS THE NIFASM TAG. `and`,
      # `or`, `xor`, `shl`, `shr` and `not` needed cover names (`bitand`, `shiftl`, …)
      # for exactly the reason `of` did, and lost them for the same reason. Nothing
      # in this table is a rename any more — so no consumer has two vocabularies to
      # reconcile, and a reader of one file can trust the other.
      string("add"), string("sub"), string("and"), string("or"), string("xor"), string("shl"), string("shr"), string("sar"),
      string("neg"), string("not"), string("inc"), string("dec"),
      # The atomics are PORTABLE rows, so — like `Ctz`/`Bswap` — the name is a
      # capitalised opcode rather than a mnemonic: there is no single instruction to
      # name after. It reads as the C builtin with the `__atomic_` prefix dropped and
      # the words joined, which is the mapping the C back end then undoes.
      string("AtomicLoad"), string("AtomicStore"), string("AtomicExchange"), string("AtomicCompareExchange"),
      string("AtomicFetchAdd"), string("AtomicFetchSub"), string("AtomicFetchAnd"), string("AtomicFetchOr"),
      string("AtomicFetchXor"), string("AtomicAddFetch"), string("AtomicSubFetch"),
      string("AtomicTestAndSet"), string("AtomicClear"), string("AtomicThreadFence"), string("AtomicSignalFence"),
      string("CpuRelax"),
      # The vector rows: THE SOURCE NAME IS THE NIFASM TAG, as everywhere above.
      string("fldrq"), string("fstrq"), string("vfadd"), string("vfsub"), string("vfmul"), string("vfmla"), string("vdup"), string("vaddv"),
      string("StackPointer"), string("TraceTable"), string("TlsSize"), string("VgClientRequest"),
      string("VolatileLoad"), string("VolatileStore"), string("HeapStart"), string("HeapSize"),
      string("NoinitStart"), string("NoinitSize"), string("bkpt"), string("semihost"), string("syscall"),
      string("adc"), string("sbb"), string("mul"), string("imul"),
      string("cmovz"), string("cmovnz"), string("cmovc"), string("cmovnc"), string("cmovs"), string("cmovns"), string("cmovo"), string("cmovno"),
      string("cmova"), string("cmovbe"), string("cmovl"), string("cmovge"), string("cmovg"), string("cmovle"),
      string("adds3"), string("adcs3"), string("subs3"), string("sbcs3"), string("mul3"), string("umulh"), string("umull"), string("umlal"), string("bic3"),
      string("cseleq"), string("cselne"), string("csellt"), string("cselle"), string("cselgt"), string("cselge"), string("csello"),
      string("csells"), string("cselhi"), string("cselhs")])

    _Imm8 = array[MaxOperands, PatKind]([PatKind.ptImmLit, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])
      ## one operand, and the instruction encodes it — see `ptImmLit`.
    _AllIn = array[MaxOperands, OperandRole]([OperandRole.roIn, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn])
    _InoutFirst = array[MaxOperands, OperandRole]([OperandRole.roInout, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn])  ## operand 0 read AND written
    _NoOps = array[MaxOperands, PatKind]([PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])  ## no operands at all
    _Un = array[MaxOperands, PatKind]([PatKind.ptAnyIntW, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])  ## one integer source
    _UnCount = array[MaxOperands, PatKind]([PatKind.ptAnyIntW, PatKind.ptAnyInt, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])  ## a value plus a count
    _Bin = array[MaxOperands, PatKind]([PatKind.ptAnyIntW, PatKind.ptAnyIntW, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])  ## two same-width int sources

    # ── atomic operand shapes ────────────────────────────────────────────────
    # Every one of them ends in a memory order, because the C builtins do and the
    # declarations these rows check are the same declarations the C back end still
    # compiles. v1 IGNORES the order (see `ptMemOrder`), but dropping the operand
    # would fork the source, so the row carries it and the lowering discards it.
    _AtomLoad = array[MaxOperands, PatKind]([PatKind.ptPtrW, PatKind.ptMemOrder, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])
    _AtomRmw = array[MaxOperands, PatKind]([PatKind.ptPtrW, PatKind.ptValW, PatKind.ptMemOrder, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])
      ## `(cell, operand, order)` — store, exchange and every fetch-op form
    _AtomCas = array[MaxOperands, PatKind]([PatKind.ptPtrW, PatKind.ptPtrW, PatKind.ptValW, PatKind.ptWeak, PatKind.ptMemOrder, PatKind.ptMemOrder])
      ## `(cell, expected, desired, weak, success order, failure order)`. `expected`
      ## is a POINTER because a failed compare writes the observed value back through
      ## it — the one atomic with an output that is not the result.
    _AtomFlag = array[MaxOperands, PatKind]([PatKind.ptRawPtr, PatKind.ptMemOrder, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])
    _AtomFence = array[MaxOperands, PatKind]([PatKind.ptMemOrder, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])

    # ── volatile operand shapes ──────────────────────────────────────────────
    # The atomic shapes minus the memory order, which is the whole difference in
    # the signature and most of the difference in meaning: an atomic says how this
    # access is ordered against every other thread's, a volatile says only that the
    # access HAPPENS, exactly once, at exactly this width.
    _VolLoad = array[MaxOperands, PatKind]([PatKind.ptPtrW, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])
    _VolStore = array[MaxOperands, PatKind]([PatKind.ptPtrW, PatKind.ptValW, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])

    # ── vector operand shapes ────────────────────────────────────────────────
    _VecLoad = array[MaxOperands, PatKind]([PatKind.ptAnyPtr, PatKind.ptAnyInt, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])
      ## `(address, byte offset)` — the offset is an int literal folded into the
      ## instruction's addressing mode (a multiple of 16), so an unrolled loop
      ## needs no extra pointer bumps.
    _VecStore = array[MaxOperands, PatKind]([PatKind.ptAnyPtr, PatKind.ptAnyInt, PatKind.ptVec128, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])
    _VecBin = array[MaxOperands, PatKind]([PatKind.ptVec128, PatKind.ptVec128, PatKind.ptLaneBits, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])
    _VecFma = array[MaxOperands, PatKind]([PatKind.ptVec128, PatKind.ptVec128, PatKind.ptVec128, PatKind.ptLaneBits, PatKind.ptNone, PatKind.ptNone])
    _VecDup = array[MaxOperands, PatKind]([PatKind.ptFloatW, PatKind.ptLaneBits, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])
    _VecHAdd = array[MaxOperands, PatKind]([PatKind.ptVec128, PatKind.ptLaneBits, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])

    _MulShape = array[MaxOperands, PatKind]([PatKind.ptAnyIntW, PatKind.ptAnyIntW, PatKind.ptAnyIntW, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone])
      ## `(lo, hi, s)`, all one width
    _MulRoles = array[MaxOperands, OperandRole]([OperandRole.roInout, OperandRole.roOut, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn])
      ## `lo` is read (the multiplicand) and written; `hi` is only written

    _MulLongShape = array[MaxOperands, PatKind]([PatKind.ptAnyIntW, PatKind.ptAnyIntW, PatKind.ptAnyIntW, PatKind.ptAnyIntW, PatKind.ptNone, PatKind.ptNone])
      ## `(lo, hi, a, b)`, all one width
    _UmullRoles = array[MaxOperands, OperandRole]([OperandRole.roOut, OperandRole.roOut, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn])
      ## both halves only written
    _UmlalRoles = array[MaxOperands, OperandRole]([OperandRole.roInout, OperandRole.roInout, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn, OperandRole.roIn])
      ## both halves read (the accumulator) and written
    _Nzcv = Tset[MachineFlag](MachineFlag.mfZF, MachineFlag.mfCF, MachineFlag.mfSF, MachineFlag.mfOF)
      ## what Arm's flag-setting instructions define (there is no parity flag)

    _AllArith = Tset[MachineFlag](MachineFlag.mfZF, MachineFlag.mfCF, MachineFlag.mfSF, MachineFlag.mfOF, MachineFlag.mfPF)
      ## What an x86 arithmetic/compare instruction leaves defined. `test` clears CF
      ## and OF rather than computing them, which is still a definition — the column
      ## says "do not expect the previous value here", and that is what a reader of
      ## `defs` needs to know.
    _AllButCarry = Tset[MachineFlag](MachineFlag.mfZF, MachineFlag.mfSF, MachineFlag.mfOF, MachineFlag.mfPF)
      ## `inc`/`dec` deliberately PRESERVE the carry flag — that is the whole reason
      ## they exist next to `add r, 1`. A row that got this wrong would silently
      ## break a multi-word add loop, so the column records it.
    _IntWidths = Tset[uint8](u8(8), u8(16), u8(32), u8(64))

    # An atomic is never `efPure`: the whole point is the memory traffic, and a
    # "pure" one would be DCE's to delete. `efBarrier` is on all of them including
    # the plain load and store — v1 emits every sequence at sequential-consistency
    # strength on both targets, so the barrier is the truth about what is emitted,
    # not an aspiration. A v2 that honours the order operand relaxes this per call,
    # which is a property of the CALL, not of the row.
    _AtomRead = Tset[IntrinsicEffect](IntrinsicEffect.efReads, IntrinsicEffect.efBarrier)
    _AtomWrite = Tset[IntrinsicEffect](IntrinsicEffect.efWrites, IntrinsicEffect.efBarrier)
    _AtomModify = Tset[IntrinsicEffect](IntrinsicEffect.efReads, IntrinsicEffect.efWrites, IntrinsicEffect.efBarrier)

    # NOT `efBarrier`, and that is the point of having separate rows rather than
    # reusing the atomics. C orders volatile accesses against EACH OTHER and says
    # nothing about their order against ordinary memory, and it is not a fence: a
    # peripheral write does not flush a store buffer. Reading `efBarrier` here
    # would promise both. Where a device genuinely needs ordering against ordinary
    # memory, that is `dmb`/`dsb`, which are their own instructions.
    #
    # `efReads`/`efWrites` are what keeps them from being deleted or duplicated.
    # The volatile-against-volatile order is not in this column at all — it is not
    # a property either row could state about itself — and lives in the pass (see
    # shoggoth's `intrinsicEffects`).
    _VolRead = Tset[IntrinsicEffect](IntrinsicEffect.efReads)
    _VolWrite = Tset[IntrinsicEffect](IntrinsicEffect.efWrites)

    IntrinsicRows = array[IntrinsicOp, IntrinsicRow]([
      # The `NoIntrinsicOp` placeholder. Every field is spelled out: this file also
      # bootstraps under nimony, whose const evaluator has no `default(array[…])`.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptNone,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),

      # ── portable ───────────────────────────────────────────────────────────
      # `Ctz`/`Clz`/`Popcount` count bits, so the result is an `int32` on every
      # target regardless of the operand width — matching `__builtin_ctz` and
      # nimony's `countTrailingZeroBits` family.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptInt32,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptInt32,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # `Popcount` is x86-64 only for now: it lowers to SSE4.2 `POPCNT` there, while
      # AArch64 has no scalar population count (the NEON `cnt`/`addv` pair needs FP
      # register handling nifasm does not model yet, and the scalar SWAR expansion
      # needs a scratch register the operand model cannot request yet). `targets` is
      # exactly the field that says so, and a call on a64 is a compile error naming
      # the target rather than a silent fallback.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptInt32,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # A byte swap preserves the width, so `W` appears on both sides.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),

      # ── x86-64 ─────────────────────────────────────────────────────────────
      # `bsf`/`bsr` leave the destination unmodified when the source is zero, so
      # they are strictly `inout` on the machine. The row declares the result a
      # pure `out` with "src = 0 is undefined", matching `__builtin_ctz`: a
      # per-row judgement recorded once here instead of rediscovered by every
      # caller. (`tzcnt`/`lzcnt` define the zero case but need a CPU-feature gate
      # the target model does not have yet.)
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # x86 `bswap` reverses a register IN PLACE, so the destination must already
      # hold the source: `tie = 0`. The source spelling stays `d = bswap(x)` and
      # the allocator inserts the copy — which it elides whenever `d` and `x`
      # share a home.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=0, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,
                   params=_UnCount, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(8), u8(16), u8(32), u8(64)), tie=0, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # `ror` is also AArch64's (`ror`/`extr` for a literal count, `rorv` for a
      # register one), at 32 and 64 bits only — a narrower rotate there is refused
      # by the back end rather than emulated. Three-address on a64, so the tie is
      # x86-64's alone and costs nothing there.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64), arity=2,
                   params=_UnCount, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(8), u8(16), u8(32), u8(64)), tie=0, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),

      # ── AArch64 ────────────────────────────────────────────────────────────
      # Three-address, so no tie. `clz(rbit(x))` is the a64 `Ctz`.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=1,
                   params=_Un, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),

      # ── flags ──────────────────────────────────────────────────────────────
      # `cmp`/`test` compute nothing and return nothing: their whole output is in
      # `defs`. That is exactly why they are NOT `efPure` — a "pure" row with a void
      # result is dead by definition, and DCE would be right to delete it. The flag
      # columns are what makes a flag-only instruction non-removable.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=2,
                   params=_Bin, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(8), u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](),
                   uses=Tset[MachineFlag](), defs=_AllArith),
      # `test` is x86's and-without-a-destination. Arm spells the same idea `tst`,
      # which is a DIFFERENT instruction under a different tag, so this row stays
      # x86-64: claiming the target and emitting a `cmp` would compute another
      # condition entirely.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,
                   params=_Bin, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(8), u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](),
                   uses=Tset[MachineFlag](), defs=_AllArith),

      # The reads. Zero operands, `bool` result, and a `uses` naming the one bit —
      # the third field is what distinguishes these from an ordinary predicate, and
      # what lets the rule of §6 ("legal only where it needs no materialisation") be
      # checked without a flag type infecting the type system.
      #
      # `targets` here is availability in the ASSEMBLER, not in the silicon: every
      # Arm profile has NZCV, but a row is only true if nifasm can turn it into a
      # branch. Cortex-M maps all eight of Arm's conditions (`condOfFlagM`), so it
      # claims each of them; AArch64's `genIteA64` implements the zero flag alone,
      # so it claims `zf`/`nz` and no more. Parity is x86-64's and stays there —
      # no Arm profile has such a bit to read.
      #
      # RV32 has no condition flags AT ALL, and claims four of these anyway, which
      # is the clearest case for reading this column as "the assembler can turn it
      # into a branch". Its selector fuses `(cmp a b)` into the branch that consumes
      # it — a RISC-V branch IS the comparison — so `zf`/`nz` are equality and
      # `cf`/`nc` are the unsigned `<`/`>=` a borrow denotes. `sf` and `of` are
      # refused by name there rather than approximated: the sign of a difference
      # agrees with `<` only when the subtraction did not overflow, which is why
      # AArch64's `blt` tests `N != V` and not `N`, and no RISC-V comparison
      # produces the overflow itself.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptBool,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfZF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptBool,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfZF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptBool,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptBool,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgThumbM), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptBool,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfSF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgThumbM), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptBool,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfSF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgThumbM), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptBool,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfOF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgThumbM), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptBool,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfOF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptBool,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfPF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=0,
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptBool,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfPF), defs=Tset[MachineFlag]()),

      # ── two-address arithmetic ─────────────────────────────────────────────
      # `roInout` on operand 0 is NOT `tie`. `tie` says the RESULT aliases a source
      # (`d = bswap(x)` — still a value-producing form, and the allocator inserts
      # the copy). Here there is no result at all: the output goes back through
      # operand 0, which is why §4.1 gives these the `ins(var d, x)` spelling. A
      # `var` parameter reaches Leng as `(haddr d)`, and that tag is exactly what
      # tells the back end "bind d's location" rather than "materialise a pointer".
      #
      # `defs` on these rows is x86-64's truth and only x86-64's. Arm has both a
      # flag-setting and a non-flag-setting form of every one of them (`ADDS` vs
      # `ADD`), and which one an assembler picks is an ENCODING decision: nifasm
      # asks for the non-setting form, but Thumb's narrow 16-bit encoding — the one
      # it prefers when every operand is a low register — sets the flags anyway.
      # So on Arm the flags after an `add` depend on which registers the caller
      # pinned, which is no basis for a `defs` column and no basis for reading a
      # flag afterwards. Rather than fork the column, arkham's Arm `.assembler`
      # mode requires a flag read to follow its `cmp` immediately (see
      # `codegen_arm_asm.asmIf`), which is the rule that is true on both.
      #
      # RV32 makes the same column false in the opposite direction — it has no flags
      # at all — and claims `add`/`sub` regardless, because `defs` is not what these
      # rows are FOR. Reading a flag after one is already impossible there: nifasm's
      # RV32 selector fuses `(cmp …)` into the branch that consumes it and CHECKS
      # that nothing was emitted in between, so an `add` between a compare and its
      # read is a named assembly-time error rather than a wrong answer. The
      # destructive `(add D S)` spelling these rows use is what `TwoAddrForms`
      # promises, and RV32's selector encodes it as `add rd, rd, rs`.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=2,  # add
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllArith),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=2,  # sub
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllArith),
      # AND/OR/XOR clear CF and OF and set SF/ZF/PF — all five are DEFINED.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM), arity=2,  # and
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllArith),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM), arity=2,  # or
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllArith),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM), arity=2,  # xor
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllArith),
      # The shifts take a COUNT, not a same-width operand, hence `UnCount`. A
      # variable count must live in `cl`; v1 takes a literal, like `rol`/`ror`.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM), arity=2,  # shl
                   params=_UnCount, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllArith),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM), arity=2,  # shr
                   params=_UnCount, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllArith),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM), arity=2,  # sar
                   params=_UnCount, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllArith),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM), arity=1,  # neg
                   params=_Un, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllArith),
      # x86 NOT touches no flags at all — the one row here whose `defs` is empty.
      # It stays x86-64 while its neighbours gained the Arm targets: Arm spells it
      # `mvn`, a two-OPERAND instruction (`mvn d, s`) in nifasm's Cortex-M tag set
      # and absent from the AArch64 one, so claiming the target would mean claiming
      # a lowering that is a different shape on one profile and missing on the
      # other. `inc`/`dec` stay for a plainer reason: Arm has no such instruction —
      # it writes `add #1`, and inventing that operand is not this row's to do.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=1,  # not
                   params=_Un, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=1,  # inc
                   params=_Un, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllButCarry),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=1,  # dec
                   params=_Un, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllButCarry),

      # ── atomics ────────────────────────────────────────────────────────────
      # `tie` stays -1 throughout even though several x86 lowerings ARE two-address
      # (`lock xadd [p], r` returns the old value in `r`). `tie` names an alias the
      # ALLOCATOR must arrange between a result and a declared operand; here the
      # register that gets destroyed is the sequence's own, seeded from an operand by
      # the back end. Spelling that as a tie would over-constrain AArch64, whose LL/SC
      # loop has no such relationship at all.
      #
      # `widths` is `IntWidths` because the machine sizes the access to the cell —
      # `ldaxrb`/`ldaxrh`, `ldrexb`/`ldrexh` and the 8/16-bit `lock` forms all
      # exist. Cortex-M is the exception at the TOP of the range rather than the
      # bottom: ARMv7-M has no `ldrexd`, so a 64-bit cell is refused by name there
      # (`codegen_arm.emitAtomicInstrM`) — the column cannot say "every width but
      # one on one target", and a per-target width set would be a second place for
      # the same fact to be wrong. Note that `W`
      # usually stays UNBOUND at the declaration: these are generic over the cell
      # type, so the width is the instantiation's and the back end reads it off the
      # pointee at the call site. See `matchPat`.

      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=2,  # AtomicLoad
                   params=_AtomLoad, roles=_AllIn, ret=PatKind.ptValW,
                   widths=_IntWidths, tie=-1, effects=_AtomRead, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=3,  # AtomicStore
                   params=_AtomRmw, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=_AtomWrite, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=3,  # AtomicExchange
                   params=_AtomRmw, roles=_AllIn, ret=PatKind.ptValW,
                   widths=_IntWidths, tie=-1, effects=_AtomModify, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # The result is the SUCCESS FLAG, not the cell's type — so `ptBool`, and the
      # observed value leaves through the `expected` pointer instead.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=6,  # AtomicCompareExchange
                   params=_AtomCas, roles=_AllIn, ret=PatKind.ptBool,
                   widths=_IntWidths, tie=-1, effects=_AtomModify, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # The fetch-ops return the value BEFORE the update, the `*_fetch` forms the
      # value after. Two rows rather than one plus a flag: the difference is which
      # register the sequence ends up reading, which is the lowering's whole shape.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=3,  # AtomicFetchAdd
                   params=_AtomRmw, roles=_AllIn, ret=PatKind.ptValW,
                   widths=_IntWidths, tie=-1, effects=_AtomModify, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=3,  # AtomicFetchSub
                   params=_AtomRmw, roles=_AllIn, ret=PatKind.ptValW,
                   widths=_IntWidths, tie=-1, effects=_AtomModify, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=3,  # AtomicFetchAnd
                   params=_AtomRmw, roles=_AllIn, ret=PatKind.ptValW,
                   widths=_IntWidths, tie=-1, effects=_AtomModify, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=3,  # AtomicFetchOr
                   params=_AtomRmw, roles=_AllIn, ret=PatKind.ptValW,
                   widths=_IntWidths, tie=-1, effects=_AtomModify, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=3,  # AtomicFetchXor
                   params=_AtomRmw, roles=_AllIn, ret=PatKind.ptValW,
                   widths=_IntWidths, tie=-1, effects=_AtomModify, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=3,  # AtomicAddFetch
                   params=_AtomRmw, roles=_AllIn, ret=PatKind.ptValW,
                   widths=_IntWidths, tie=-1, effects=_AtomModify, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=3,  # AtomicSubFetch
                   params=_AtomRmw, roles=_AllIn, ret=PatKind.ptValW,
                   widths=_IntWidths, tie=-1, effects=_AtomModify, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # `targets: {}` — neither back end lowers the flag pair yet, and `targets` is
      # exactly the column that says so: a call is then a compile error naming the
      # target, never a silent fallback. The C back end does not consult `targets`
      # (it has `__atomic_test_and_set`), so the rows are usable there today.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](), arity=2,  # AtomicTestAndSet
                   params=_AtomFlag, roles=_AllIn, ret=PatKind.ptBool,
                   widths=_IntWidths, tie=-1, effects=_AtomModify, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](), arity=2,  # AtomicClear
                   params=_AtomFlag, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=_AtomWrite, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # A fence has no operand but the order and no result at all: its entire content
      # is `efBarrier`, which is what keeps it from being deleted for producing
      # nothing — the same argument `cmp`'s `defs` makes for a flag-only instruction.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=1,  # AtomicThreadFence
                   params=_AtomFence, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efBarrier), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=1,  # AtomicSignalFence
                   params=_AtomFence, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=_IntWidths, tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efBarrier), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),

      # ── the spin-wait hint ─────────────────────────────────────────────────
      # No operands, no result, no flags: the whole content is `effects`, and it is
      # `effects` that has to keep it alive. NOT `efPure` — a pure hint is one CSE
      # is entitled to fold two of into one and DCE is entitled to delete outright,
      # and a deleted `pause` is not a slower program but a spin loop that
      # hammers the bus. `efBarrier` is also the honest description of what the
      # instruction is FOR: it stands inside a loop that re-reads a lock word, and
      # hoisting that read above it would turn the loop into an infinite one.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM), arity=0,  # CpuRelax
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efBarrier), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),

      # ── 128-bit vectors: AdvSIMD (AArch64) and SSE2 (x86-64) ───────────────
      # All pinned: one machine instruction each on AArch64, named by its nifasm
      # tag. The loads/stores carry their memory effect so nothing reorders or
      # deletes them; the arithmetic is pure and CSE-eligible like any other value.
      #
      # `icPinned` is about the ROW, not the instruction count: SSE is
      # two-address, so the x86-64 lowering of a three-register row is a copy plus
      # the op, and `vfmla` is a multiply plus an add because SSE has no FMA (see
      # `codegen_x64.emitVecInstr2`).
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64, IntrinsicTarget.tgX64), arity=2,  # fldrq
                   params=_VecLoad, roles=_AllIn, ret=PatKind.ptVec128,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efReads), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64, IntrinsicTarget.tgX64), arity=3,  # fstrq
                   params=_VecStore, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efWrites), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64, IntrinsicTarget.tgX64), arity=3,  # vfadd
                   params=_VecBin, roles=_AllIn, ret=PatKind.ptVec128,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64, IntrinsicTarget.tgX64), arity=3,  # vfsub
                   params=_VecBin, roles=_AllIn, ret=PatKind.ptVec128,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64, IntrinsicTarget.tgX64), arity=3,  # vfmul
                   params=_VecBin, roles=_AllIn, ret=PatKind.ptVec128,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # `tie: 0` — the machine op accumulates IN PLACE (fmla Vd += Vn*Vm), so the
      # result must land where operand 0 lives. The vectorizer spells every use as
      # `(asgn acc (instr vfmla acc a b bits))`, which satisfies the tie with no
      # copy; the a64 back end asserts it rather than inserting a 128-bit move.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64, IntrinsicTarget.tgX64), arity=4,  # vfmla
                   params=_VecFma, roles=_AllIn, ret=PatKind.ptVec128,
                   widths=Tset[uint8](u8(32), u8(64)), tie=0, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64, IntrinsicTarget.tgX64), arity=2,  # vdup
                   params=_VecDup, roles=_AllIn, ret=PatKind.ptVec128,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64, IntrinsicTarget.tgX64), arity=2,  # vaddv
                   params=_VecHAdd, roles=_AllIn, ret=PatKind.ptFloatW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),

      # ── stack walking ──────────────────────────────────────────────────────
      # `StackPointer` reads SP into a register. `efPure` is not a shrug: SP is
      # CONSTANT between a proc's prologue and its epilogue (`arkham/design.md`),
      # so within one body the value really does not change, and CSE-ing two reads
      # of it is exact rather than merely harmless. The interesting caller is a
      # `{.naked.}` proc, which has no prologue at all — there SP still points at
      # the return address the `call` pushed, and that is the seed of a stack walk.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64), arity=0,  # StackPointer
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptRawPtr,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # `TraceTable` is the address of the per-proc metadata nifasm lays down at the
      # end of `.text` (`nifasm/tracetable.nim`): the same code ranges and CFA
      # offsets `.eh_frame` carries, in a form the running program can read without
      # a DWARF interpreter. A link-time constant, hence `efPure`. x86-64 only for
      # now — the table is emitted on every target, but only the x86-64 walk is
      # written and tested (`lib/std/stacktraces`).
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=0,  # TraceTable
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptRawPtr,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # `TlsSize` is the address of an 8-byte cell holding how many bytes one
      # thread's thread-local block occupies — the same `lea`-against-a-label shape
      # as `TraceTable`, and for the same reason: the number is only settled once
      # every module's `{.threadvar.}`s have been laid out, which is after the last
      # compilation unit is gone. `efPure`: a link-time constant.
      # x86-64 only, which is where the block is a flat FS-relative region; the
      # AArch64/Darwin thread-locals go through per-variable descriptors, where
      # "the size of the block" is not the question a thread creator asks.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=0,  # TlsSize
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptRawPtr,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),

      # ── valgrind ───────────────────────────────────────────────────────────
      # One request to valgrind, made the only way valgrind accepts one: a fixed
      # sequence of instructions that is architecturally a NO-OP, which valgrind's
      # JIT recognizes and replaces. Running natively it does nothing at all — which
      # is why the whole mechanism costs an unvalgrinded program only the handful of
      # bytes it never notices executing.
      #
      # The operand is a pointer to the 6-word request block (`request, arg1..arg5`)
      # valgrind reads; the result is what valgrind hands back, or 0 when nothing
      # intercepted the sequence. So `0` means "not running under valgrind" for every
      # request, and every request that returns nothing interesting simply ignores it.
      # No `default` operand for that reason: the caller-supplied default the C macro
      # takes is always 0 here, and passing it would only add a register to shuffle.
      #
      # NOT `efPure`: pure would make it CSE-able and DCE-able, and a request deleted
      # for having no result is a request not made. The memory effects are real too —
      # valgrind READS the block — and `efBarrier` is what keeps the surrounding
      # allocator stores on the correct side of it, which is the entire point at a
      # `FREELIKE_BLOCK` (the free-list link must not sink past the request that
      # declares the block dead).
      #
      # AArch64 only for now: the sequence is written and tested there (`nimony n` on
      # linux/arm64). x86-64 has the same mechanism — `rol rdi,{3,13,61,51}` +
      # `xchg rbx,rbx`, args in rax — and wants the same row with `tgX64` added once
      # its lowering is written and RUN, exactly as `TraceTable` above is waiting on
      # its AArch64 half.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=1,  # VgClientRequest
                   params=array[MaxOperands, PatKind]([PatKind.ptRawPtr, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone, PatKind.ptNone]),
                   roles=_AllIn, ret=PatKind.ptUIntW,
                   widths=Tset[uint8](u8(64)), tie=-1,
                   effects=Tset[IntrinsicEffect](IntrinsicEffect.efReads, IntrinsicEffect.efWrites, IntrinsicEffect.efBarrier), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # ── volatile ──
      # `W` stays unbound at the declaration exactly as the atomics' does: these are
      # generic over the cell type and the width is read off the POINTEE at the call
      # site. That is also the only width the access may use — a `volatileLoad` of a
      # 64-bit cell on a 32-bit target is two loads, which is two accesses, which is
      # not what was asked for. The back end refuses it rather than lowering it.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=1,
                   params=_VolLoad, roles=_AllIn, ret=PatKind.ptValW,  # VolatileLoad
                   widths=_IntWidths, tie=-1, effects=_VolRead, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64, IntrinsicTarget.tgA64, IntrinsicTarget.tgThumbM, IntrinsicTarget.tgRv32), arity=2,
                   params=_VolStore, roles=_AllIn, ret=PatKind.ptVoid,  # VolatileStore
                   widths=_IntWidths, tie=-1, effects=_VolWrite, uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # ── the reserved heap ──
      # `efPure`: both are constants the link fixed, so hoisting one out of a loop
      # or folding two into one is exactly right. Cortex-M only — every other target
      # here is hosted and gets its pages from an OS.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgThumbM), arity=0,  # HeapStart
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptRawPtr,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgThumbM), arity=0,  # HeapSize
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptUIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # ── the region kept back from the startup code ──
      # `efPure` for the same reason as the heap rows: both are constants the link
      # fixed. What LIVES there is not pure, but these two only name the place.
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgThumbM), arity=0,  # NoinitStart
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptRawPtr,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPortable, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgThumbM), arity=0,  # NoinitSize
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptUIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # ── the debugger trap ──
      # Everything a `bkpt` does is invisible from here: whether a debug agent is
      # attached, what it makes of r0, and — for the semihosting operations that
      # take a parameter block — which memory it reads or writes. So the effects are
      # the widest honest ones. They are what keeps the instruction where the body
      # put it: an `efPure` trap would be DCE's to delete, and one without
      # `efReads`/`efWrites` could have a store sunk past it, which for SYS_WRITE
      # means the agent transmits the buffer before it was filled.
      #
      # `defs` is empty: `bkpt` leaves NZCV alone. What it may change is r0, and no
      # column here can say that — see the enum comment.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgThumbM), arity=1,  # bkpt
                   params=_Imm8, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efReads, IntrinsicEffect.efWrites, IntrinsicEffect.efBarrier),
                   uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # Effects verbatim from `bkpt`, and for the identical reason: what a debug
      # agent does on the other side is invisible from here — whether one is
      # attached at all, what it makes of a0, and which memory it reads or writes
      # for the operations that take a parameter block. So it reads, it writes, and
      # nothing moves across it.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgRv32), arity=0,  # semihost
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efReads, IntrinsicEffect.efWrites, IntrinsicEffect.efBarrier),
                   uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # ── the kernel entry ──
      # Effects as wide as the two rows above, and for a stronger reason: a syscall
      # is every side effect there is. `efBarrier` is what keeps a store the kernel
      # is about to read from being sunk past it, and what stops `clone`'s child
      # from being reached by code hoisted across the instruction that created it.
      #
      # `defs` is empty, which is not the claim that flags survive — x86-64's
      # `syscall` also destroys rcx and r11, and no column here can say that
      # either. An `.assembler` body has no allocator to mislead: what the
      # instruction costs is the author's to know, the same way it is in the
      # asm block of any other language.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=0,  # syscall
                   params=_NoOps, roles=_AllIn, ret=PatKind.ptVoid,
                   widths=Tset[uint8](), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efReads, IntrinsicEffect.efWrites, IntrinsicEffect.efBarrier),
                   uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      # ── multi-word arithmetic. 64-bit only: a limb is a machine word, and a
      #    narrower carry chain is a bug rather than a feature.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # adc
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF), defs=_AllArith),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # sbb
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF), defs=_AllArith),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=3,  # mul
                   params=_MulShape, roles=_MulRoles, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_AllArith),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # imul
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](),
                   defs=_AllArith),
      # ── conditional moves: `d = s` if the condition holds, else `d` is kept, so
      #    `d` is read and written. No branch, whatever the flag says.
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovz
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfZF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovnz
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfZF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovc
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovnc
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovs
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfSF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovns
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfSF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovo
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfOF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovno
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfOF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmova
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF, MachineFlag.mfZF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovbe
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF, MachineFlag.mfZF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovl
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfSF, MachineFlag.mfOF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovge
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfSF, MachineFlag.mfOF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovg
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfZF, MachineFlag.mfSF, MachineFlag.mfOF),
                   defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgX64), arity=2,  # cmovle
                   params=_Bin, roles=_InoutFirst, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(16), u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfZF, MachineFlag.mfSF, MachineFlag.mfOF),
                   defs=Tset[MachineFlag]()),
      # ── Arm: carry chains, products and selects (see the enum) ──
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # adds3
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_Nzcv),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # adcs3
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF), defs=_Nzcv),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # subs3
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=_Nzcv),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # sbcs3
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF), defs=_Nzcv),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # mul3
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # umulh
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](), arity=4,  # umull
                   params=_MulLongShape, roles=_UmullRoles, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(32)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](), arity=4,  # umlal
                   params=_MulLongShape, roles=_UmlalRoles, ret=PatKind.ptVoid,
                   widths=Tset[uint8](u8(32)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](), arity=2,  # bic3
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](IntrinsicEffect.efPure), uses=Tset[MachineFlag](), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # cseleq
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfZF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # cselne
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfZF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # csellt
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfSF, MachineFlag.mfOF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # cselle
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfZF, MachineFlag.mfSF, MachineFlag.mfOF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # cselgt
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfZF, MachineFlag.mfSF, MachineFlag.mfOF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # cselge
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfSF, MachineFlag.mfOF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # csello
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # csells
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF, MachineFlag.mfZF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # cselhi
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF, MachineFlag.mfZF), defs=Tset[MachineFlag]()),
      IntrinsicRow(cls=IntrinsicClass.icPinned, targets=Tset[IntrinsicTarget](IntrinsicTarget.tgA64), arity=2,  # cselhs
                   params=_Bin, roles=_AllIn, ret=PatKind.ptAnyIntW,
                   widths=Tset[uint8](u8(32), u8(64)), tie=-1, effects=Tset[IntrinsicEffect](), uses=Tset[MachineFlag](MachineFlag.mfCF), defs=Tset[MachineFlag]())
    ])


with const:
    LastIntrinsicOp = IntrinsicOp.CselhsOp
      ## The final row. Spelled out rather than `high(IntrinsicOp)` because this file
      ## is also compiled by nimony (it bootstraps `nimsem`), which has no iteration
      ## over an enum *type* — hence the ordinal loop below too.


def intrinsicOpByName(name: string, cls: IntrinsicClass) -> IntrinsicOp:
    ## Resolve a pragma argument to its row. The class is part of the key: the
    ## portable `Bswap` and the x86 instruction `bswap` are different rows, and
    ## `{.instruction: "Bswap".}` must not silently mean the portable one.
    result = IntrinsicOp.NoIntrinsicOp
    for i in inrange(1, ord(LastIntrinsicOp)):
        with let:
            op = IntrinsicOp(i)
        if IntrinsicNames[op] == name and IntrinsicRows[op].cls == cls:
            return op
    return result


with const:
    IgnoredPats = Tset[PatKind](PatKind.ptMemOrder, PatKind.ptWeak, PatKind.ptLaneBits, PatKind.ptImmLit)
      ## Operand patterns the back ends do not EVALUATE into a register. See
      ## `evaluatedOperands`. (`ptLaneBits` is still READ — as a literal, at the
      ## call site — it just never needs a register.)


def evaluatedOperands(r: IntrinsicRow) -> nint:
    ## How many LEADING operands a back end must actually evaluate. Everything past
    ## them is a compile-time knob v1 ignores — the memory orders, and
    ## `AtomicCompareExchange`'s `weak` — and evaluating one is not merely wasted
    ## work: `__ATOMIC_SEQ_CST` and its siblings are `importc` globals with no
    ## definition in a C-runtime-free native program, so a load of one would not
    ## link. Every row is arranged so the ignored operands are the TRAILING ones,
    ## which is what lets a count stand in for a per-operand test.
    ##
    ## The C back end is the exception and evaluates all of them: it hands the
    ## arguments straight to the real `__atomic_*` builtin, which does read them.
    result = r.arity.copy()
    while result > 0 and r.params[result - 1] in IgnoredPats: result -= 1
    return result


if comptime(__name__ == "__main__"):
    # every row through every proc that takes a row or an op: a row that differs from the original shows here
    for i in inrange(1, ord(LastIntrinsicOp)):
        with let:
            op = IntrinsicOp(i)
            r = IntrinsicRows[op]
        echo(i, " ", op, " ", IntrinsicNames[op], " ", r.cls, " ", r.targets, " ", r.arity, " ", r.params, " ",
             r.roles, " ", r.ret, " ", r.widths, " ", r.tie, " ", r.effects, " ", r.uses, " ", r.defs)
        echo("  flagRead=", r.isFlagRead(), " inout=", r.inoutOperand(), " flagValue=", r.isFlagValue(),
             " asmOnly=", r.isAssemblerOnly(), " flagWrite=", r.isFlagWrite(), " evaluated=", evaluatedOperands(r),
             " voidResult=", r.isVoidResult(), " machineQuery=", op.isMachineQuery(),
             " nullaryVoid=", r.isNullaryVoid(), " atomic=", op.isAtomic(), " hasInout=", r.hasInoutOperand(),
             " volatile=", op.isVolatile())
    # the placeholder row and the constants
    echo(IntrinsicNames[IntrinsicOp.NoIntrinsicOp].len, " ", IntrinsicRows[IntrinsicOp.NoIntrinsicOp].tie, " ",
         MaxOperands, " ", LastIntrinsicOp, " ", IgnoredPats)
    # by name: portable, instruction, the wrong class, unknown
    echo(intrinsicOpByName(string("Bswap"), IntrinsicClass.icPortable))
    echo(intrinsicOpByName(string("bswap"), IntrinsicClass.icPinned))
    echo(intrinsicOpByName(string("Bswap"), IntrinsicClass.icPinned))
    echo(intrinsicOpByName(string("bswap"), IntrinsicClass.icPortable))
    echo(intrinsicOpByName(string("AtomicFetchAdd"), IntrinsicClass.icPortable))
    echo(intrinsicOpByName(string("of"), IntrinsicClass.icPinned))
    echo(intrinsicOpByName(string("cselhs"), IntrinsicClass.icPinned))
    echo(intrinsicOpByName(string("nosuchop"), IntrinsicClass.icPinned))
    echo(intrinsicOpByName(string(""), IntrinsicClass.icPortable))
