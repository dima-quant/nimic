import ncompiler.platform as p
t = p.Target()
print("Before:", t.hostCPU)
t.hostCPU = p.TSystemCPU.cpuArm64
print("After:", t.hostCPU)
