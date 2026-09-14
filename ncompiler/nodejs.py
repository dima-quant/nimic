# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *

def findNodeJs() -> string:
    """{.inline.}
    Find NodeJS executable and return it as a string.
    """
    result = findExe("nodejs")
    if len(result) == 0:
        result = findExe("node")
    if len(result) == 0:
        echo("Please install NodeJS first, see https://nodejs.org/en/download")
        raise newException(IOError, "NodeJS not found in PATH")
    return result

if comptime(__name__ == "__main__"):
    # Verify findExe behavior
    assert len(findExe("nonexistent_binary_xyz_123")) == 0

    # Test findNodeJs: should either return a valid node executable path or raise IOError
    with let:
        _has_node = (len(findExe("nodejs")) > 0) | (len(findExe("node")) > 0)
    if _has_node:
        with let:
            _node_path = findNodeJs()
        assert len(_node_path) > 0
        echo("NodeJS found: ", _node_path)
    else:
        with var:
            _raised = False
        try:
            _ = findNodeJs()
        except IOError as err:
            _raised = True
            assert err.msg == "NodeJS not found in PATH"
            echo("NodeJS not installed in environment, IOError raised as expected.")
        assert _raised

