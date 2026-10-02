from enum import Enum

class MyEnum(Enum):
    A = "a"
    B = "b"
    
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, int):
            return list(cls)[value]
        return super()._missing_(value)

print("MyEnum(1):", MyEnum(1))
