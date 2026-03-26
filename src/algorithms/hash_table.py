"""
hash_table.py — custom hash table with open addressing and linear probing.

I built this from scratch to demonstrate O(1) retrieval for citation lookups.
The key design decisions:
  - Open addressing with linear probing: on collision, probe (h+1), (h+2), ...
  - Tombstone deletion: deleted slots are marked so probe chains stay intact
  - Auto-resize at load factor 0.7: doubles capacity and rehashes everything

Keys are normalised citation strings like "410US113".
Values are full CAP case metadata dicts.

I track collision count and probe lengths during inserts so eval_hash.py
can report on performance.
"""

from __future__ import annotations
from typing import Optional


class _Slot:
    """One slot in the internal array. States: EMPTY, OCCUPIED, or DELETED."""
    EMPTY    = 0
    OCCUPIED = 1
    DELETED  = 2

    __slots__ = ("state", "key", "value")

    def __init__(self):
        self.state = _Slot.EMPTY
        self.key   = None
        self.value = None


class HashTable:
    """
    Open-addressing hash table with linear probing and dynamic resizing.

    capacity is rounded up to the next power of two internally.
    load_threshold controls when the table doubles (default 0.7).
    """

    _LOAD_THRESHOLD_DEFAULT = 0.7

    def __init__(self, capacity: int = 64, load_threshold: float = _LOAD_THRESHOLD_DEFAULT):
        if capacity < 8:
            capacity = 8
        self._capacity       = self._next_power_of_two(capacity)
        self._load_threshold = load_threshold
        self._size           = 0
        self._tombstones     = 0
        self._slots: list[_Slot] = [_Slot() for _ in range(self._capacity)]

        # Metrics I expose to eval_hash.py
        self._collision_count = 0
        self._probe_lengths: list[int] = []
        self._insert_count  = 0
        self._lookup_count  = 0

    def insert(self, key: str, value: object) -> None:
        """
        Insert or update a key-value pair.
        If the key already exists it's updated in place (deduplication).
        Triggers a resize if load factor + tombstones would exceed the threshold.
        """
        if key is None:
            raise ValueError("Hash table key must not be None.")

        if (self._size + self._tombstones + 1) / self._capacity > self._load_threshold:
            self._resize()

        slot_index, probe_length = self._find_slot_for_insert(key)
        slot = self._slots[slot_index]

        if slot.state == _Slot.OCCUPIED:
            slot.value = value
        else:
            if slot.state == _Slot.DELETED:
                self._tombstones -= 1
            slot.state = _Slot.OCCUPIED
            slot.key   = key
            slot.value = value
            self._size += 1

        self._probe_lengths.append(probe_length)
        self._insert_count += 1

    def get(self, key: str) -> Optional[object]:
        """Return the value for a key, or None if not found."""
        if key is None:
            return None

        self._lookup_count += 1
        h = self._hash(key)

        for i in range(self._capacity):
            idx  = (h + i) % self._capacity
            slot = self._slots[idx]

            if slot.state == _Slot.EMPTY:
                return None
            if slot.state == _Slot.OCCUPIED and slot.key == key:
                return slot.value

        return None

    def contains(self, key: str) -> bool:
        return self.get(key) is not None

    def delete(self, key: str) -> bool:
        """
        Remove a key by marking its slot as DELETED (tombstone).
        I use tombstones instead of clearing the slot outright because
        clearing would break existing probe chains.
        """
        if key is None:
            return False

        h = self._hash(key)

        for i in range(self._capacity):
            idx  = (h + i) % self._capacity
            slot = self._slots[idx]

            if slot.state == _Slot.EMPTY:
                return False
            if slot.state == _Slot.OCCUPIED and slot.key == key:
                slot.state = _Slot.DELETED
                slot.key   = None
                slot.value = None
                self._size       -= 1
                self._tombstones += 1
                return True

        return False

    def load_factor(self) -> float:
        return self._size / self._capacity if self._capacity > 0 else 0.0

    def size(self) -> int:
        return self._size

    def capacity(self) -> int:
        return self._capacity

    def collision_stats(self) -> dict:
        """Return the performance metrics I collect during inserts."""
        n = len(self._probe_lengths)
        return {
            "total_inserts"    : self._insert_count,
            "total_collisions" : self._collision_count,
            "collision_rate"   : self._collision_count / max(self._insert_count, 1),
            "avg_probe_length" : round(sum(self._probe_lengths) / n if n > 0 else 0.0, 4),
            "max_probe_length" : max(self._probe_lengths) if self._probe_lengths else 0,
            "load_factor"      : round(self.load_factor(), 4),
            "capacity"         : self._capacity,
            "size"             : self._size,
        }

    def keys(self) -> list[str]:
        return [s.key for s in self._slots if s.state == _Slot.OCCUPIED]

    def items(self) -> list[tuple[str, object]]:
        return [(s.key, s.value) for s in self._slots if s.state == _Slot.OCCUPIED]

    def _hash(self, key: str) -> int:
        """
        Map a key to an index using Python's built-in hash plus a
        multiplicative mix (Knuth's method) to reduce clustering.
        """
        h = hash(key)
        h = (h ^ (h >> 16)) * 0x45d9f3b
        h = (h ^ (h >> 16)) * 0x45d9f3b
        h =  h ^ (h >> 16)
        return abs(h) % self._capacity

    def _find_slot_for_insert(self, key: str) -> tuple[int, int]:
        """
        Walk the probe sequence to find where this key should go.
        Returns (slot_index, probe_length). Tracks collisions along the way.
        I reuse the earliest tombstone I find if the key is new.
        """
        h               = self._hash(key)
        first_tombstone = -1
        probe_length    = 1

        for i in range(self._capacity):
            idx  = (h + i) % self._capacity
            slot = self._slots[idx]

            if slot.state == _Slot.EMPTY:
                target = first_tombstone if first_tombstone != -1 else idx
                return target, probe_length

            if slot.state == _Slot.DELETED:
                if first_tombstone == -1:
                    first_tombstone = idx
                probe_length += 1
                self._collision_count += 1
                continue

            if slot.state == _Slot.OCCUPIED and slot.key == key:
                return idx, probe_length

            probe_length += 1
            self._collision_count += 1

        if first_tombstone != -1:
            return first_tombstone, probe_length

        raise RuntimeError("Hash table is completely full — resizing should have prevented this.")

    def _resize(self) -> None:
        """
        Double the capacity and rehash all live entries.
        Tombstones are dropped during rehashing.
        I save and restore the user-visible metrics so the resize
        doesn't inflate the collision/probe stats.
        """
        old_slots = self._slots
        self._capacity   = self._capacity * 2
        self._slots      = [_Slot() for _ in range(self._capacity)]
        self._size       = 0
        self._tombstones = 0

        saved_collisions    = self._collision_count
        saved_probe_lengths = list(self._probe_lengths)
        saved_insert_count  = self._insert_count

        for slot in old_slots:
            if slot.state == _Slot.OCCUPIED:
                idx, _ = self._find_slot_for_insert(slot.key)
                s        = self._slots[idx]
                s.state  = _Slot.OCCUPIED
                s.key    = slot.key
                s.value  = slot.value
                self._size += 1

        self._collision_count = saved_collisions
        self._probe_lengths   = saved_probe_lengths
        self._insert_count    = saved_insert_count

    @staticmethod
    def _next_power_of_two(n: int) -> int:
        p = 1
        while p < n:
            p <<= 1
        return p

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: str) -> bool:
        return self.contains(key)

    def __repr__(self) -> str:
        return f"HashTable(size={self._size}, capacity={self._capacity}, load={self.load_factor():.2f})"


if __name__ == "__main__":
    ht = HashTable(capacity=16)

    ht.insert("410US113", {"name": "Roe v. Wade"})
    ht.insert("381US479", {"name": "Griswold v. Connecticut"})
    ht.insert("505US833", {"name": "Planned Parenthood v. Casey"})
    ht.insert("384US436", {"name": "Miranda v. Arizona"})

    tests = [
        ("410US113", "Roe v. Wade"),
        ("381US479", "Griswold v. Connecticut"),
        ("999US000", None),
    ]

    all_pass = True
    print("HashTable basic tests")
    print("-" * 40)
    for key, expected_name in tests:
        result = ht.get(key)
        got    = result["name"] if result else None
        status = "PASS" if got == expected_name else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}]  get({key!r})  ->  {got!r}")

    ht.insert("410US113", {"name": "Roe v. Wade (updated)"})
    assert ht.get("410US113")["name"] == "Roe v. Wade (updated)", "Deduplication failed"
    print("  [PASS]  deduplication check")

    ht.delete("381US479")
    assert ht.get("381US479") is None, "Deletion failed"
    print("  [PASS]  deletion check")

    for i in range(100):
        ht.insert(f"TEST{i}US{i}", {"name": f"Case {i}"})
    assert ht.get("TEST50US50") is not None, "Post-resize lookup failed"
    print("  [PASS]  resize + post-resize lookup")

    print(f"\nCollision stats: {ht.collision_stats()}")
    print("\n" + ("All tests passed ✅" if all_pass else "Some tests FAILED ❌"))
