# kloc-mapper Known Issues

## 1. Redundant Override Detection Logic

**Status:** Open
**Severity:** Medium
**Location:** `src/mapper.py` - `_build_override_edges()` method (lines 483-534)

**Description:**
kloc-mapper has its own `_build_override_edges()` method that builds override relationships by traversing the inheritance chain. However, scip-php already emits this information via SCIP relationships with `is_implementation: true, is_reference: true`.

**Current Behavior:**
- `_build_override_edges()` manually builds override edges
- Only checks direct parent class (`class_parents.get(class_symbol)`)
- Does NOT check interface method implementations
- Does NOT traverse full inheritance chain (grandparents)

**scip-php Behavior:**
- `getParentMethodSymbols()` in `Types.php` recursively finds all parent methods
- Includes interface method implementations
- Emits proper relationships in SCIP index

**Impact:**
- Override edges may be incomplete (missing grandparent methods)
- Interface method implementations may not have override edges
- Duplicate/conflicting logic between scip-php and kloc-mapper

**Solution Options:**
1. Remove `_build_override_edges()` and parse SCIP relationships instead
2. Build override edges from `doc.symbols[].relationships` where `is_implementation: true`

```python
def _build_override_edges_from_relationships(self):
    """Build overrides edges from SCIP relationship data."""
    for symbol, meta in self.symbol_metadata.items():
        source_id = self.symbol_to_node_id.get(symbol)
        if not source_id:
            continue

        for rel in meta.get("relationships", []):
            if rel.get("is_implementation") and rel.get("is_reference"):
                target_symbol = rel["symbol"]
                target_id = self._resolve_relationship_target(target_symbol)
                if target_id:
                    self.edges.append(Edge(
                        type=EdgeType.OVERRIDES,
                        source=source_id,
                        target=target_id,
                    ))
```

---

## 2. Estimated Symbol Ranges Are Unreliable

**Status:** Open
**Severity:** High
**Location:** `src/mapper.py` - `_estimate_symbol_ranges()` method (lines 224-272)

**Description:**
`_estimate_symbol_ranges()` tries to estimate method/class body extent based on sibling symbols and fixed defaults because SCIP only provides signature line ranges.

**Current Logic:**
```python
if node.range.end_line <= node.range.start_line:
    if i + 1 < len(symbols):
        next_start = symbols[i + 1][0]
        node.range.end_line = max(next_start - 1, node.range.start_line)
    else:
        # Last symbol - use fixed defaults
        if node.kind in (NodeKind.METHOD, NodeKind.FUNCTION):
            node.range.end_line = node.range.start_line + 50  # ← Arbitrary!
        elif node.kind in (NodeKind.CLASS, ...):
            node.range.end_line = node.range.start_line + 500  # ← Arbitrary!
```

**Problems:**
- Methods with 100+ lines get estimated as 50 lines
- Large gaps between siblings cause incorrect attribution
- Last method in file always gets wrong range
- No way to know actual body extent without parsing PHP

**Impact:**
- `_find_enclosing_symbol()` returns wrong symbols
- Reference locations attributed to wrong methods
- Usages tree shows incorrect line numbers (e.g., line 51 instead of line 31)

**Root Cause:**
This is fundamentally a scip-php issue (Issue #1 there). Once scip-php emits proper ranges with `getEndLine()`, this estimation can be removed.

**Temporary Workaround:**
Increase defaults significantly or use file line count as upper bound.

---

## 3. Uses Edge Deduplication Missing

**Status:** Open
**Severity:** Low
**Location:** `src/mapper.py` - `_build_uses_edges()` method

**Description:**
Multiple references to the same symbol from the same source create multiple edges, which may cause duplicate entries in usages queries.

**Example:**
```php
public function foo() {
    $this->bar();  // Creates edge foo -> bar
    $this->bar();  // Creates another edge foo -> bar (duplicate!)
    $this->bar();  // Creates yet another edge
}
```

**Current Code:**
```python
def _build_uses_edges(self):
    for occ in self.occurrences:
        # ... no deduplication check
        self.edges.append(Edge(
            type=EdgeType.USES,
            source=source_id,
            target=target_id,
            location=location,
        ))
```

**Impact:**
- Potentially bloated edge list (3x, 5x, 10x more edges than necessary)
- Query results may contain duplicates
- Larger SoT JSON files

**Solution:**
Track seen (source, target) pairs and only create one edge per pair:
```python
def _build_uses_edges(self):
    seen_edges = set()  # (source_id, target_id)

    for occ in self.occurrences:
        # ...
        edge_key = (source_id, target_id)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)

        self.edges.append(Edge(...))
```

Or keep all edges but deduplicate at query time in kloc-cli.

---

## 4. Enclosing Symbol Detection Can Be Wrong

**Status:** Open
**Severity:** High
**Location:** `src/mapper.py` - `_find_enclosing_symbol()` method (lines 416-440)

**Description:**
The spatial index lookup for finding which method contains a reference depends on estimated ranges (Issue #2), leading to wrong enclosing symbol detection.

**Example:**
```php
class Foo {
    public function methodA() {  // Lines 10-30
        $this->helper();         // Line 25 - reference
    }

    public function methodB() {  // Lines 32-50
        // ...
    }
}
```

If `methodA` range is estimated as `[10, 15]` (too short), the reference at line 25 won't be found inside `methodA` and may fall back to the class or file.

**Impact:**
- Edges have wrong `source` (enclosing symbol)
- Usages show methods that don't actually contain the reference
- Line numbers in output don't match actual usage locations

**Root Cause:**
Depends on Issue #2 (estimated ranges) which depends on scip-php Issue #1 (incomplete ranges).

---

## 5. Interface Implementation Detection Limited

**Status:** Open
**Severity:** Medium
**Location:** `src/mapper.py` - `_build_inheritance_edges()` method

**Description:**
Interface implementation detection relies on parsing PHPDoc `@implements` annotations from documentation strings, which may miss implementations declared in code but not documented.

**Current Approach:**
```python
extends_list, implements_list, uses_traits = extract_extends_implements_from_docs(docs)
```

**Better Approach:**
Use SCIP relationships which are parsed from actual code:
```json
{
  "symbol": "...MyClass#",
  "relationships": [
    {"symbol": "...MyInterface#", "is_implementation": true}
  ]
}
```

---

## 6. Line Number Conversion (Documentation)

**Status:** Documentation
**Severity:** Info

**Note:**
SCIP uses 0-based line numbers. kloc-mapper stores them as-is in SoT JSON.
kloc-cli adds +1 when displaying to users.

**SoT JSON format:**
```json
{
  "range": {
    "start_line": 10,  // 0-based (editor line 11)
    "end_line": 10
  }
}
```

**Edge location format:**
```json
{
  "location": {
    "file": "src/Foo.php",
    "line": 25  // 0-based (editor line 26)
  }
}
```
