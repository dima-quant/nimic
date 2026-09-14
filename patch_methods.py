with open('src/nimic/ntypesystem.py', 'r') as f:
    content = f.read()

methods = """
    def __and__(self, other):
        return string(self.data + str(other))

    def _substitute(self, **kwargs):
        from string import Template
        return string(Template(self.data).substitute(**kwargs))

    def __mod__(self, itr):
        if hasattr(itr, '__iter__') and not isinstance(itr, (str, bytes)):
            return string(self.data % tuple(itr))
        return string(self.data % itr)

    def is_empty(self) -> bool:
        return len(self.data) == 0

    def __truediv__(self, tail) -> 'string':
        tail_str = tail.data if hasattr(tail, 'data') else str(tail)
        return string(f"{self.data}/{tail_str}")

    def splitlines(self):
        return self.data.splitlines()

    def split_whitespace(self):
        return self.data.split()

    @classmethod
"""

content = content.replace("    @classmethod\n", methods, 1)

with open('src/nimic/ntypesystem.py', 'w') as f:
    f.write(content)
