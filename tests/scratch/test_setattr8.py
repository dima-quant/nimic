import sys
import trace
tracer = trace.Trace(count=False, trace=True, ignoredirs=[sys.prefix, sys.exec_prefix])
import ncompiler.platform as p
t = p.Target()
def run():
    t.hostCPU = p.TSystemCPU.cpuArm64
tracer.run('run()')
