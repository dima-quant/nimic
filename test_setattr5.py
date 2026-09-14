import ncompiler.platform as p
t = p.Target()
print("Assigning via object.__setattr__:")
object.__setattr__(t, 'hostCPU', p.TSystemCPU.cpuArm64)
print("Dict value:", repr(t.__dict__['hostCPU']))
