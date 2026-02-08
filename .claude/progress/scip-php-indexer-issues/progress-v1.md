# Progress: scip-php-indexer-issues (v1)

<!-- Steps are numbered. Substeps use parent.child notation. -->
<!-- Status markers: [ ] pending, [~] in_progress, [w] waiting, [x] done -->

## 1. [x] Add callee verification guard in find_call_for_usage (Issue 6) [kloc-cli]
- [x] **1.1** Add callee verification in find_call_for_usage() line-matching loop (context.py:167-173)
- [x] **1.2** Add callee verification in fallback container-matching loop (context.py:176-182)
- [x] **1.3** Write unit test: find_call_for_usage returns None when Call callee does not match target_id
- [x] **1.4** Write integration test: OrderRepository::nextId at line 30 shows static_property not instantiation
- [x] **1.5** Write integration test: AbstractOrderProcessor::getName() at line 43 shows method_call not property_access
- [x] **1.6** Write integration test: Order::customerEmail at line 48 does not show method_call with wrong receiver

## 2. [x] Replace global visited set with per-subtree tracking in _build_outgoing_tree (Issue 5) [kloc-cli]
- [x] **2.1** Replace global visited set at line 795 with per-parent deduplication
- [x] **2.2** Preserve cycle prevention -- start_id stays in initial visited set
- [x] **2.3** Write integration test: depth-2 from createOrder includes customerEmail and productId under save()
- [x] **2.4** Write integration test: depth-1 direct query of save() still shows all uses (no regression)
- [x] **2.5** Write integration test: verify no infinite loops with self-referencing methods

## 3. [x] Fix uses edge location accuracy for constructor arguments (Issues 2+4) [scip-php, kloc-mapper]
- [x] **3.1** Investigate SCIP occurrence positions for self::nextId++ at line 30
- [x] **3.2** Fix location source (mapper or scip-php) for symbols inside constructor argument lists
- [x] **3.3** Verify savedOrder->customerEmail at line 48 gets its own separate occurrence position
- [x] **3.4** Rebuild reference project index and verify location accuracy in sot.json

## 4. [x] Fix call_kind for chained method calls (Issue 3) [scip-php]
- [x] **4.1** Investigate calls.json output for getName() call at line 43 -- verify current call_kind
- [x] **4.2** Trace through resolveCallKind() to determine why MethodCall gets wrong kind
- [x] **4.3** Fix node type detection for chained method calls if needed
- [x] **4.4** Rebuild reference project index and verify call_kind accuracy
- [x] **4.5** Verify fix does not break existing contract tests

## 5. [x] Testing and validation
- [x] **5.1** Run full kloc-cli test suite (uv run pytest tests/ -v)
- [x] **5.2** Run full kloc-mapper test suite (uv run pytest tests/ -v)
- [x] **5.3** Run scip-php contract tests from kloc-reference-project-php/contract-tests
- [x] **5.4** End-to-end validation: kloc-cli context createOrder --depth 2 passes all 8 acceptance criteria
- [x] **5.5** Verify no regressions in existing test_usage_flow.py tests

