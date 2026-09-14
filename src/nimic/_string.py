import ctypes

class MutableString:
    """
    A mutable string class using ctypes for managing a contiguous memory buffer.
    The string is stored as UTF-8 encoded bytes.
    Operations like indexing are byte-oriented.
    """
    DEFAULT_MIN_CAPACITY = 16  # Minimum capacity in bytes for the buffer

    def __init__(self, initial_value=""):
        """
        Initializes the MutableString.
        Args:
            initial_value (str): The initial string value.
        Raises:
            TypeError: If initial_value is not a string.
        """
        if not isinstance(initial_value, str):
            raise TypeError("Initial value must be a string.")

        encoded_value = initial_value.encode('utf-8')
        self._length = len(encoded_value)  # Number of bytes for the data

        # Determine initial capacity:
        # Needs space for data + 1 null terminator.
        # Capacity is double this required buffer size, or DEFAULT_MIN_CAPACITY.
        required_buffer_size = self._length + 1
        self._capacity = self.DEFAULT_MIN_CAPACITY
        if self._length > 0 : # If there's initial data, calculate based on its length
             self._capacity = max(self.DEFAULT_MIN_CAPACITY, required_buffer_size * 2)
        else: # For empty string, just use default min capacity
            self._capacity = self.DEFAULT_MIN_CAPACITY


        self._buffer = ctypes.create_string_buffer(self._capacity)

        # Copy initial data to the buffer
        self._buffer.raw[:self._length] = encoded_value
        # Ensure null termination
        self._buffer.raw[self._length] = b'\0'

    def _ensure_capacity(self, required_data_length):
        """
        Ensures the buffer has enough capacity for the required data length (in bytes).
        If not, resizes the buffer. New capacity will be (required_data_length + 1) * 2.
        Args:
            required_data_length (int): The number of bytes needed for string data.
        """
        required_buffer_size = required_data_length + 1  # +1 for null terminator
        if required_buffer_size > self._capacity:
            new_capacity = max(required_buffer_size * 2, self.DEFAULT_MIN_CAPACITY)
            
            # print(f"DEBUG: Resizing - Old Cap: {self._capacity}, Required Data: {required_data_length}, New Cap: {new_capacity}") # For debugging

            new_buffer = ctypes.create_string_buffer(new_capacity)
            # Copy existing content (up to current _length bytes)
            # self._buffer.raw is not directly usable in memmove's first arg if it's not a pointer type.
            # ctypes.addressof(self._buffer) or self._buffer itself (if it's a pointer type array)
            ctypes.memmove(new_buffer, self._buffer, self._length)
            
            self._buffer = new_buffer
            self._capacity = new_capacity

    def __len__(self):
        """Returns the current length of the string in bytes (not characters)."""
        return self._length

    def __str__(self):
        """Returns the string content as a standard Python string (decoded from UTF-8)."""
        return self._buffer.raw[:self._length].decode('utf-8', errors='replace')

    def __repr__(self):
        """Returns a string representation of the MutableString object."""
        return f"MutableString(\"{self.__str__()}\")"

    @property
    def capacity(self):
        """Returns the current allocated capacity of the buffer in bytes."""
        return self._capacity

    @property
    def raw_bytes(self):
        """Returns the raw bytes of the string content (excluding null terminator)."""
        return self._buffer.raw[:self._length]

    def append(self, text_to_append):
        """
        Appends a string to the end of the MutableString.
        Args:
            text_to_append (str): The string to append.
        Raises:
            TypeError: If text_to_append is not a string.
        """
        if not isinstance(text_to_append, str):
            raise TypeError("Can only append strings.")
        
        encoded_text = text_to_append.encode('utf-8')
        append_len = len(encoded_text)
        if append_len == 0:
            return

        new_total_length = self._length + append_len
        self._ensure_capacity(new_total_length)

        # Append new text bytes
        self._buffer.raw[self._length : self._length + append_len] = encoded_text
        self._length = new_total_length
        self._buffer.raw[self._length] = b'\0'  # Ensure null termination

    def insert(self, byte_index, text_to_insert):
        """
        Inserts a string at a specified byte index.
        Args:
            byte_index (int): The byte index at which to insert the text.
            text_to_insert (str): The string to insert.
        Raises:
            TypeError: If arguments are of incorrect types.
            IndexError: If byte_index is out of adjusted bounds.
        """
        if not isinstance(text_to_insert, str):
            raise TypeError("Text to insert must be a string.")
        if not isinstance(byte_index, int):
            raise TypeError("Index must be an integer.")

        encoded_text = text_to_insert.encode('utf-8')
        insert_len = len(encoded_text)
        if insert_len == 0:
            return

        # Adjust negative index and clamp to [0, self._length]
        if byte_index < 0:
            byte_index += self._length
        byte_index = max(0, min(byte_index, self._length)) # Allows insertion at the very end

        new_total_length = self._length + insert_len
        self._ensure_capacity(new_total_length)

        # Shift the part of the string from byte_index to the end to make space
        bytes_to_shift = self._length - byte_index
        if bytes_to_shift > 0:
            source_ptr = ctypes.addressof(self._buffer) + byte_index
            dest_ptr = ctypes.addressof(self._buffer) + byte_index + insert_len
            ctypes.memmove(dest_ptr, source_ptr, bytes_to_shift)

        # Insert the new text bytes
        self._buffer.raw[byte_index : byte_index + insert_len] = encoded_text
        self._length = new_total_length
        self._buffer.raw[self._length] = b'\0' # Ensure null termination

    def __delitem__(self, byte_index_or_slice):
        """
        Deletes a byte or a slice of bytes.
        Args:
            byte_index_or_slice (int or slice): The byte index or slice to delete.
        Raises:
            TypeError: If index is not int or slice.
            IndexError: If int index is out of bounds.
            ValueError: If slice step is not 1.
        """
        if isinstance(byte_index_or_slice, slice):
            start, stop, step = byte_index_or_slice.indices(self._length)
            if step != 1 and step is not None: # Python's list.__delitem__ supports step, but memmove is easier with contiguous blocks
                raise ValueError("Deletion with slice currently only supports step of 1.")
            
            if start >= stop: # Nothing to delete or invalid slice
                return

            num_deleted_bytes = stop - start
            
            # Shift the part of the string after the deleted section
            bytes_to_move = self._length - stop
            if bytes_to_move > 0:
                source_ptr = ctypes.addressof(self._buffer) + stop
                dest_ptr = ctypes.addressof(self._buffer) + start
                ctypes.memmove(dest_ptr, source_ptr, bytes_to_move)

            self._length -= num_deleted_bytes
            self._buffer.raw[self._length] = b'\0'

        elif isinstance(byte_index_or_slice, int):
            index = byte_index_or_slice
            if index < 0:
                index += self._length
            if not (0 <= index < self._length):
                raise IndexError("MutableString index out of range for deletion.")

            # Shift everything after index one byte to the left
            bytes_to_move = self._length - index - 1
            if bytes_to_move > 0:
                source_ptr = ctypes.addressof(self._buffer) + index + 1
                dest_ptr = ctypes.addressof(self._buffer) + index
                ctypes.memmove(dest_ptr, source_ptr, bytes_to_move)

            self._length -= 1
            self._buffer.raw[self._length] = b'\0'
        else:
            raise TypeError("Index for deletion must be an int or slice.")

    def __setitem__(self, byte_index_or_slice, value_str):
        """
        Sets a byte or replaces a slice of bytes.
        If index is int, value_str must encode to a single byte.
        If index is slice, value_str (encoded) replaces the specified byte slice. This can change the string's length.
        Args:
            byte_index_or_slice (int or slice): The byte index or slice to modify.
            value_str (str): The string value to set/insert.
        Raises:
            TypeError: If arguments are of incorrect types.
            IndexError: If int index is out of bounds.
            ValueError: If constraints on value_str (for int index) or slice step are violated.
        """
        if not isinstance(value_str, str):
            raise TypeError("Value for assignment must be a string.")
        encoded_value = value_str.encode('utf-8')

        if isinstance(byte_index_or_slice, int):
            index = byte_index_or_slice
            if index < 0:
                index += self._length
            if not (0 <= index < self._length):
                raise IndexError("MutableString index out of range for assignment.")
            if len(encoded_value) != 1:
                raise ValueError("For single byte index assignment, value_str must encode to exactly one byte.")
            
            self._buffer.raw[index] = encoded_value[0]
            # Length does not change, null terminator remains correct.

        elif isinstance(byte_index_or_slice, slice):
            start, stop, step = byte_index_or_slice.indices(self._length)
            if step != 1 and step is not None:
                raise ValueError("Slice assignment currently only supports step of 1.")

            original_slice_len = stop - start # Number of bytes to be replaced
            new_value_len = len(encoded_value)
            length_diff = new_value_len - original_slice_len

            new_total_length = self._length + length_diff
            self._ensure_capacity(new_total_length)

            # If length changes, shift the tail part of the string
            tail_start_original = stop
            num_tail_bytes = self._length - stop

            if length_diff != 0 and num_tail_bytes > 0:
                source_ptr = ctypes.addressof(self._buffer) + tail_start_original
                dest_ptr = ctypes.addressof(self._buffer) + tail_start_original + length_diff # New position of tail
                ctypes.memmove(dest_ptr, source_ptr, num_tail_bytes)

            # Insert the new value bytes
            self._buffer.raw[start : start + new_value_len] = encoded_value
            self._length = new_total_length
            self._buffer.raw[self._length] = b'\0' # Ensure null termination
        else:
            raise TypeError("Index for assignment must be an int or slice.")

    def __getitem__(self, byte_index_or_slice):
        """
        Gets a character (as string) at a byte index or a substring from a byte slice.
        Decoding is done using UTF-8 (errors replaced).
        Args:
            byte_index_or_slice (int or slice): The byte index or slice.
        Returns:
            str: The character or substring.
        Raises:
            TypeError: If index is not int or slice.
            IndexError: If int index is out of bounds.
        """
        if isinstance(byte_index_or_slice, slice):
            start, stop, step = byte_index_or_slice.indices(self._length)
            return self._buffer.raw[start:stop:step].decode('utf-8', errors='replace')
        elif isinstance(byte_index_or_slice, int):
            index = byte_index_or_slice
            if index < 0:
                index += self._length
            if not (0 <= index < self._length):
                raise IndexError("MutableString index out of range.")
            # This decodes a single byte. For multi-byte UTF-8 chars, this will likely produce ''
            # if this byte is not a complete character itself (e.g. ASCII).
            return bytes([self._buffer.raw[index]]).decode('utf-8', errors='replace')
        else:
            raise TypeError("Index must be an int or slice.")

    def clear(self):
        """Clears the string, setting its length to 0. Capacity is not changed."""
        self._length = 0
        self._buffer.raw[0] = b'\0'

# --- Example Usage ---
if __name__ == "__main__":
    print("--- MutableString Demo ---")

    # Initialization
    ms = MutableString("Hello")
    print(f"Initial: '{ms}' (len: {len(ms)}, cap: {ms.capacity})")

    # Append
    ms.append(", World!")
    print(f"Appended: '{ms}' (len: {len(ms)}, cap: {ms.capacity})")

    ms.append(" This is a longer string to trigger resizing.")
    print(f"Appended more: '{ms}' (len: {len(ms)}, cap: {ms.capacity})")

    # Length (bytes) vs Character Length
    print(f"Byte length: {len(ms)}, Character length: {len(str(ms))}")

    # Getitem (byte-based)
    print(f"Byte at index 0: '{ms[0]}' (ASCII 'H')")
    print(f"Byte at index 6: '{ms[6]}' (ASCII 'W')")
    print(f"Slice [0:5]: '{ms[0:5]}'")

    # Insert (byte-based index)
    ms.insert(6, "Beautiful ") # Insert before "World"
    print(f"Inserted: '{ms}' (len: {len(ms)}, cap: {ms.capacity})")

    # Setitem (byte-based)
    # Replace 'H' with 'J' (single byte char)
    ms[0] = "J"
    print(f"Setitem [0]='J': '{ms}'")

    # Replace a slice
    ms[6:16] = "Amazing" # Replaces "Beautiful "
    print(f"Setitem slice: '{ms}' (len: {len(ms)}, cap: {ms.capacity})")
    
    # Deletion (byte-based)
    del ms[0] # Delete 'J'
    print(f"Deleted [0]: '{ms}' (len: {len(ms)})")

    del ms[0:4] # Delete "ello"
    print(f"Deleted [0:4]: '{ms}' (len: {len(ms)})")

    # UTF-8 characters
    ms_utf8 = MutableString("你好")
    print(f"UTF-8: '{ms_utf8}' (bytes: {len(ms_utf8)}, chars: {len(str(ms_utf8))}, cap: {ms_utf8.capacity})")
    ms_utf8.append(", 世界") # Append ", World" in Chinese
    print(f"UTF-8 Appended: '{ms_utf8}' (bytes: {len(ms_utf8)}, chars: {len(str(ms_utf8))}, cap: {ms_utf8.capacity})")
    
    # Byte indexing into UTF-8 string (can be problematic)
    print(f"Byte 0 of '{ms_utf8}': '{ms_utf8[0]}' (likely '' as it's part of a multi-byte char)")
    print(f"Slice [0:3] of '{ms_utf8}': '{ms_utf8[0:3]}' (first Chinese char '你')")


    # Clear
    ms.clear()
    print(f"Cleared: '{ms}' (len: {len(ms)}, cap: {ms.capacity})")

    # Edge case: empty string and append
    ms_empty = MutableString()
    print(f"Empty init: '{ms_empty}' (len: {len(ms_empty)}, cap: {ms_empty.capacity})")
    ms_empty.append("test")
    print(f"Appended to empty: '{ms_empty}' (len: {len(ms_empty)}, cap: {ms_empty.capacity})")

    # Test resizing with very small initial capacity (by direct manipulation for test)
    ms_small_test = MutableString("a")
    ms_small_test._capacity = 2 # Force small capacity (1 data + 1 null)
    ms_small_test._buffer = ctypes.create_string_buffer(b"a\0", 2) # Manually set buffer
    print(f"Small test initial: '{ms_small_test}' (len: {len(ms_small_test)}, cap: {ms_small_test.capacity})")
    ms_small_test.append("b") # Should resize
    print(f"Small test append 'b': '{ms_small_test}' (len: {len(ms_small_test)}, cap: {ms_small_test.capacity})") # len=2, cap=(2+1)*2 = 6
    ms_small_test.append("cdefg") # len=7, cap=(7+1)*2 = 16
    print(f"Small test append 'cdefg': '{ms_small_test}' (len: {len(ms_small_test)}, cap: {ms_small_test.capacity})")

